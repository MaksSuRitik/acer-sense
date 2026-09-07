"""Read-only component diagnostics, including a bounded in-memory stress test."""
from __future__ import annotations

import gc
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Callable

import psutil

from core.sensors import get_battery_info, get_cpu_temp, get_ram_info, get_temperature_readings


GOOD = "good"
WARNING = "warning"
CRITICAL = "critical"
UNKNOWN = "unknown"
ProgressCallback = Callable[[int, str], None]


def _result(status: str, headline: str, details: list[str]) -> dict:
    return {"status": status, "headline": headline, "details": details}


def _cancelled(cancel_event: threading.Event | None) -> bool:
    return bool(cancel_event and cancel_event.is_set())


def _emit(callback: ProgressCallback | None, value: int, text: str) -> None:
    if callback:
        callback(max(0, min(100, value)), text)


def check_battery() -> dict:
    battery = get_battery_info()
    if not battery["present"]:
        return _result(UNKNOWN, "Аккумулятор не обнаружен", ["Проверка недоступна на этом устройстве."])

    details = []
    if battery["percent"] is not None:
        details.append(f"Заряд: {battery['percent']}%")
    if battery["health_percent"] is not None:
        details.append(f"Остаточная ёмкость: {battery['health_percent']}% от заводской")
    if battery["cycles"] is not None:
        details.append(f"Циклы: {battery['cycles']}")
    details.append("Питание подключено" if battery["plugged"] else "Питание от аккумулятора")

    if battery["percent"] is not None and battery["percent"] <= 5 and not battery["plugged"]:
        return _result(CRITICAL, "Низкий заряд", details)
    if battery["health_percent"] is not None and battery["health_percent"] < 60:
        return _result(WARNING, "Ёмкость заметно снижена", details)
    return _result(GOOD, "Хорошее", details)


def _smart_helper_path() -> str | None:
    bundled = Path(__file__).resolve().parents[2] / "scripts" / "smart-status.sh"
    if bundled.exists():
        return str(bundled)
    packaged = Path("/usr/lib/acer-sense/scripts/smart-status.sh")
    return str(packaged) if packaged.exists() else None


def _run_smart(device: str, allow_auth: bool = True) -> tuple[str | None, list[str]]:
    """Collect SMART attributes without waking a sleeping drive or writing to it."""
    smartctl = shutil.which("smartctl")
    if not smartctl:
        return None, ["SMART недоступен: установите smartmontools"]
    try:
        process = subprocess.run([smartctl, "-a", "-n", "standby", device], capture_output=True,
                                 text=True, timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, ["SMART не ответил за 25 секунд"]

    output = f"{process.stdout}\n{process.stderr}"
    lower = output.lower()
    if allow_auth and ("permission denied" in lower or "operation not permitted" in lower):
        helper = _smart_helper_path()
        if helper:
            try:
                process = subprocess.run(["pkexec", helper, device], capture_output=True, text=True,
                                         timeout=35, check=False)
                output = f"{process.stdout}\n{process.stderr}"
                lower = output.lower()
            except (OSError, subprocess.TimeoutExpired):
                return None, ["Для SMART требуется подтверждение доступа"]

    if "standby" in lower:
        return None, ["SMART пропущен: накопитель находится в режиме сна"]
    if "open device" in lower or "no such device" in lower:
        return None, ["SMART недоступен: устройство не открывается"]
    if "permission denied" in lower or "operation not permitted" in lower:
        return None, ["SMART требует разрешения администратора"]

    details: list[str] = []
    status: str | None = None
    if re.search(r"overall-health.*?:\s*passed", output, re.IGNORECASE) or re.search(r"smart status:\s*ok", output, re.IGNORECASE):
        status = GOOD
        details.append("SMART: критических ошибок не обнаружено")
    elif re.search(r"overall-health.*?:\s*failed", output, re.IGNORECASE) or re.search(r"smart status:\s*critical", output, re.IGNORECASE):
        status = CRITICAL
        details.append("SMART сообщает о критической ошибке")

    labels = {
        "Critical Warning": "Критическое предупреждение",
        "Percentage Used": "Износ накопителя",
        "Media and Data Integrity Errors": "Ошибки данных",
        "Unsafe Shutdowns": "Небезопасные выключения",
        "Power Cycles": "Циклы включения",
        "Temperature": "Температура SMART",
    }
    for source, destination in labels.items():
        match = re.search(rf"^{re.escape(source)}\s*:\s*(.+)$", output, re.MULTILINE | re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            details.append(f"{destination}: {value}")
    if not details:
        details.append("SMART не поддерживается этим накопителем")
    return status, details


def check_drive(drive: dict, allow_auth: bool = True) -> dict:
    warnings: list[str] = []
    details: list[str] = []
    status = GOOD
    for partition in drive.get("partitions", []):
        used = partition.get("percent", 0)
        mount = partition.get("mount", "/")
        details.append(f"{mount}: свободно {partition.get('free_gb', 0)} ГБ из {partition.get('total_gb', 0)} ГБ")
        if used >= 97:
            status = CRITICAL
            warnings.append(f"{mount} почти заполнен ({used}%)")
        elif used >= 90 and status != CRITICAL:
            status = WARNING
            warnings.append(f"{mount} заполнен на {used}%")

    block_name = drive.get("block_name")
    if block_name:
        try:
            if Path(f"/sys/block/{block_name}/ro").read_text(encoding="utf-8").strip() == "1":
                status = CRITICAL
                warnings.append("Накопитель перешёл в режим только для чтения")
        except OSError:
            pass

    smart_status, smart_details = _run_smart(drive.get("device", ""), allow_auth)
    details.extend(smart_details)
    if smart_status == CRITICAL:
        status = CRITICAL
    if warnings:
        return _result(status, warnings[0], details)
    if smart_status == CRITICAL:
        return _result(CRITICAL, "SMART сообщает о критической ошибке", details)
    return _result(status, "Хорошее", details)


def _read_ecc_errors() -> tuple[int, bool]:
    total = 0
    counters = list(Path("/sys/devices/system/edac/mc").glob("mc*/**/ue_count"))
    for path in counters:
        try:
            total += int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return total, bool(counters)


def check_memory() -> dict:
    memory = get_ram_info()
    percent = memory["percent"]
    details = [f"Используется: {percent}% ({memory['used_gb']} из {memory['total_gb']} ГБ)"]
    ecc_errors, ecc_available = _read_ecc_errors()
    if ecc_errors:
        details.append(f"Неисправимых ECC-ошибок: {ecc_errors}")
        return _result(CRITICAL, "Обнаружены ошибки памяти", details)
    if percent >= 97:
        return _result(CRITICAL, "Память почти занята", details)
    if percent >= 90:
        return _result(WARNING, "Высокое использование памяти", details)
    details.append("Неисправимых ECC-ошибок не обнаружено" if ecc_available
                   else "ECC-контроллер не предоставляет данные")
    return _result(GOOD, "Хорошее", details)


def check_system_temperature() -> dict:
    readings = get_temperature_readings()
    if not readings:
        return _result(UNKNOWN, "Датчик температуры недоступен", ["Драйвер датчика не предоставил показания."])
    temperature = max(readings.values())
    details = [f"{name}: {value:g}°C" for name, value in readings.items()]
    if temperature >= 95:
        return _result(CRITICAL, "Перегрев системы", details)
    if temperature >= 85:
        return _result(WARNING, "Повышенная температура", details)
    return _result(GOOD, "Температура в норме", details)


def _stress_memory(duration_seconds: int, progress: ProgressCallback | None,
                   cancel_event: threading.Event | None) -> dict:
    """Safely exercise a bounded RAM sample with write/read patterns over minutes."""
    available = psutil.virtual_memory().available
    # Cap the allocation at 512 MiB and reserve at least 92% of currently free RAM.
    target = min(512 * 1024**2, max(32 * 1024**2, int(available * 0.08)))
    target = min(target, max(16 * 1024**2, int(available * 0.15)))
    block_size = 8 * 1024**2
    blocks_needed = max(1, (target + block_size - 1) // block_size)
    blocks: list[bytearray] = []
    deadline = time.monotonic() + max(10, duration_seconds)
    tested = 0
    try:
        for index in range(blocks_needed):
            if _cancelled(cancel_event):
                return _result(UNKNOWN, "Проверка отменена", [f"Проверено {tested // 1024**2} МБ памяти"])
            current_available = psutil.virtual_memory().available
            if current_available < block_size * 3:
                return _result(WARNING, "Проверка памяти остановлена", ["Недостаточно свободной памяти для безопасного продолжения"])
            size = min(block_size, target - tested)
            pattern = 0xA5 if index % 2 == 0 else 0x5A
            block = bytearray(size)
            block[:] = bytes([pattern]) * size
            if block.count(pattern) != size:
                return _result(CRITICAL, "Ошибка чтения/записи ОЗУ", [f"Несовпадение шаблона в блоке {index + 1}"])
            blocks.append(block)
            tested += size
            _emit(progress, 5 + int(80 * (index + 1) / blocks_needed), f"Тест ОЗУ: {tested // 1024**2} МБ")
            remaining_blocks = blocks_needed - index - 1
            if remaining_blocks:
                pause = max(0, (deadline - time.monotonic()) / remaining_blocks)
                if cancel_event and cancel_event.wait(min(pause, 15)):
                    return _result(UNKNOWN, "Проверка отменена", [f"Проверено {tested // 1024**2} МБ памяти"])
                if not cancel_event:
                    time.sleep(min(pause, 15))

        for index, block in enumerate(blocks, start=1):
            pattern = 0xA5 if index % 2 else 0x5A
            if block.count(pattern) != len(block):
                return _result(CRITICAL, "Ошибка повторного чтения ОЗУ", [f"Несовпадение шаблона в блоке {index}"])
        while time.monotonic() < deadline and not _cancelled(cancel_event):
            if cancel_event:
                cancel_event.wait(min(1, deadline - time.monotonic()))
            else:
                time.sleep(min(1, deadline - time.monotonic()))
            _emit(progress, 90, "Финальная проверка ОЗУ")
        if _cancelled(cancel_event):
            return _result(UNKNOWN, "Проверка отменена", [f"Проверено {tested // 1024**2} МБ памяти"])
        return _result(GOOD, "ОЗУ прошло стресс-проверку", [f"Проверено с шаблонами: {tested // 1024**2} МБ", f"Длительность: {duration_seconds // 60} мин."])
    except MemoryError:
        return _result(WARNING, "Недостаточно памяти для стресс-проверки", ["Приложение не стало занимать дополнительную память"])
    finally:
        blocks.clear()
        gc.collect()


def _sample_sensors(progress: ProgressCallback | None, cancel_event: threading.Event | None) -> dict:
    samples: list[float] = []
    for index in range(5):
        if _cancelled(cancel_event):
            return _result(UNKNOWN, "Проверка отменена", [])
        reading = get_cpu_temp()
        if reading:
            samples.append(reading)
        _emit(progress, 15 + index * 15, "Считывание датчиков")
        if cancel_event:
            cancel_event.wait(2)
        else:
            time.sleep(2)
    if not samples:
        return _result(UNKNOWN, "Датчики температуры недоступны", ["За 10 секунд показания не получены"])
    maximum = max(samples)
    minimum = min(samples)
    details = [f"Диапазон за 10 сек.: {minimum}–{maximum}°C", *check_system_temperature()["details"]]
    if maximum >= 95:
        return _result(CRITICAL, "Перегрев системы", details)
    if maximum >= 85:
        return _result(WARNING, "Повышенная температура", details)
    return _result(GOOD, "Датчики работают стабильно", details)


def run_deep_check(component: str, payload: dict | None = None, progress: ProgressCallback | None = None,
                   cancel_event: threading.Event | None = None, memory_duration_seconds: int = 150) -> dict:
    """Run the selected real check. Full run lasts about 3 minutes because of RAM."""
    _emit(progress, 2, "Подготовка проверки")
    if component == "battery":
        _emit(progress, 40, "Считывание состояния аккумулятора")
        result = check_battery()
        _emit(progress, 100, "Проверка завершена")
        return result
    if component.startswith("drive_"):
        _emit(progress, 20, "Чтение SMART-статуса")
        result = check_drive(payload or {}, allow_auth=True)
        _emit(progress, 100, "Проверка завершена")
        return result
    if component == "memory":
        return _stress_memory(memory_duration_seconds, progress, cancel_event)
    return _sample_sensors(progress, cancel_event)
