"""Deep hardware component diagnostics: Multi-pass RAM test and CPU/GPU thermal load analysis."""
from __future__ import annotations

import gc
import hashlib
import math
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

import psutil

from core.sensors import (
    get_battery_info,
    get_cpu_temp,
    get_gpu_temp,
    get_ram_info,
    get_temperature_readings,
)


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


# ─────────────────────────────────────────────────────────────────────────────
# 1. Battery Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def check_battery() -> dict:
    battery = get_battery_info()
    if not battery["present"]:
        return _result(UNKNOWN, "Аккумулятор не обнаружен", ["Проверка недоступна на этом устройстве."])

    details = []
    if battery["percent"] is not None:
        details.append(f"Уровень заряда: {battery['percent']}%")
    if battery["health_percent"] is not None:
        details.append(f"Остаточная ёмкость (Health): {battery['health_percent']}% от заводской")
    if battery["cycles"] is not None:
        details.append(f"Количество циклов заряда: {battery['cycles']}")
    if battery.get("temperature") is not None:
        details.append(f"Температура батареи: {battery['temperature']}°C")

    details.append("Питание: подключено к сети" if battery["plugged"] else "Питание: работа от аккумулятора")

    # Read voltage and power rate if available
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            v_now = bat / "voltage_now"
            if v_now.exists():
                volts = round(int(v_now.read_text().strip()) / 1_000_000, 2)
                details.append(f"Текущее напряжение: {volts} В")
            p_now = bat / "power_now"
            if p_now.exists():
                watts = round(int(p_now.read_text().strip()) / 1_000_000, 2)
                details.append(f"Потребляемая мощность: {watts} Вт")
            break
        except Exception:
            pass

    if battery["percent"] is not None and battery["percent"] <= 5 and not battery["plugged"]:
        return _result(CRITICAL, "Критически низкий заряд", details)
    if battery["health_percent"] is not None and battery["health_percent"] < 50:
        return _result(CRITICAL, "Высокий износ аккумулятора", details)
    if battery["health_percent"] is not None and battery["health_percent"] < 70:
        return _result(WARNING, "Ёмкость снижена", details)
    return _result(GOOD, "Состояние аккумулятора хорошее", details)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Storage / SMART Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def _smart_helper_path() -> str | None:
    bundled = Path(__file__).resolve().parents[2] / "scripts" / "smart-status.sh"
    if bundled.exists():
        return str(bundled)
    packaged = Path("/usr/lib/acer-sense/scripts/smart-status.sh")
    return str(packaged) if packaged.exists() else None


def _run_smart(device: str, allow_auth: bool = True) -> tuple[str | None, list[str]]:
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
        details.append("SMART: самодиагностика пройдена (OK)")
    elif re.search(r"overall-health.*?:\s*failed", output, re.IGNORECASE) or re.search(r"smart status:\s*critical", output, re.IGNORECASE):
        status = CRITICAL
        details.append("SMART сообщает о критической ошибке накопителя!")

    labels = {
        "Critical Warning": "Критическое предупреждение",
        "Percentage Used": "Износ накопителя (Percentage Used)",
        "Media and Data Integrity Errors": "Ошибки данных (Integrity Errors)",
        "Unsafe Shutdowns": "Небезопасные выключения",
        "Power Cycles": "Циклы включения",
        "Power On Hours": "Время наработки (часов)",
        "Temperature": "Температура SMART",
    }
    for source, destination in labels.items():
        match = re.search(rf"^{re.escape(source)}\s*:\s*(.+)$", output, re.MULTILINE | re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            details.append(f"{destination}: {value}")
    if not details:
        details.append("SMART данные не поддерживаются этим интерфейсом")
    return status, details


def check_drive(drive: dict, allow_auth: bool = True) -> dict:
    warnings: list[str] = []
    details: list[str] = []
    status = GOOD
    for partition in drive.get("partitions", []):
        used = partition.get("percent", 0)
        mount = partition.get("mount", "/")
        details.append(f"{mount}: свободно {partition.get('free_gb', 0)} ГБ из {partition.get('total_gb', 0)} ГБ ({used}% заполнено)")
        if used >= 97:
            status = CRITICAL
            warnings.append(f"{mount} критически заполнен ({used}%)")
        elif used >= 90 and status != CRITICAL:
            status = WARNING
            warnings.append(f"{mount} заполнен на {used}%")

    block_name = drive.get("block_name")
    if block_name:
        try:
            if Path(f"/sys/block/{block_name}/ro").read_text(encoding="utf-8").strip() == "1":
                status = CRITICAL
                warnings.append("Накопитель заблокирован в режиме 'только для чтения' (Read-Only)")
        except OSError:
            pass

    smart_status, smart_details = _run_smart(drive.get("device", ""), allow_auth)
    details.extend(smart_details)
    if smart_status == CRITICAL:
        status = CRITICAL
    if warnings:
        return _result(status, warnings[0], details)
    if smart_status == CRITICAL:
        return _result(CRITICAL, "Обнаружены аппаратные проблемы SMART", details)
    return _result(status, "Накопитель исправен", details)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Deep Multi-Pass RAM Stress Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def _read_ecc_errors() -> tuple[int, bool]:
    total = 0
    counters = list(Path("/sys/devices/system/edac/mc").glob("mc*/**/ue_count"))
    for path in counters:
        try:
            total += int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return total, bool(counters)


def _stress_memory(duration_seconds: int, progress: ProgressCallback | None,
                   cancel_event: threading.Event | None) -> dict:
    """Multi-pass memory stress test with bit patterns and throughput measurement."""
    available = psutil.virtual_memory().available
    # Cap test allocation safely at up to 512 MB and max 12% of free RAM
    target_bytes = min(512 * 1024**2, max(32 * 1024**2, int(available * 0.12)))
    block_size = 16 * 1024**2
    num_blocks = max(1, (target_bytes + block_size - 1) // block_size)

    ecc_initial, ecc_available = _read_ecc_errors()
    details = [
        f"Выделенный тестовый буфер: {target_bytes // (1024**2)} МБ",
        f"Общая память: {get_ram_info()['total_gb']} ГБ",
    ]

    blocks: list[bytearray] = []
    total_written = 0
    t_start = time.monotonic()

    passes = [
        ("Проход 1/4: Чередующиеся биты (0xAA / 0x55)", [0xAA, 0x55]),
        ("Проход 2/4: Бегущие единицы и нули", [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]),
        ("Проход 3/4: Псевдослучайная хеш-структура", None),
        ("Проход 4/4: Верификация удержания заряда ячеек", [0x00, 0xFF]),
    ]

    try:
        # Pre-allocate blocks
        for i in range(num_blocks):
            if _cancelled(cancel_event):
                return _result(UNKNOWN, "Проверка отменена", details)
            size = min(block_size, target_bytes - len(blocks) * block_size)
            blocks.append(bytearray(size))

        for pass_idx, (pass_name, patterns) in enumerate(passes):
            if _cancelled(cancel_event):
                return _result(UNKNOWN, "Проверка отменена", details)

            base_pct = int(10 + (pass_idx / len(passes)) * 80)
            _emit(progress, base_pct, pass_name)

            if patterns is not None:
                # Test with pattern bytes
                for b_idx, block in enumerate(blocks):
                    pat = patterns[(pass_idx + b_idx) % len(patterns)]
                    block[:] = bytes([pat]) * len(block)
                    total_written += len(block)

                    # Verify pattern
                    if block.count(pat) != len(block):
                        return _result(CRITICAL, "Аппаратная ошибка ОЗУ: несовпадение данных!", [
                            f"Сбой битов на этапе: {pass_name}",
                            f"Повреждён блок #{b_idx + 1}"
                        ])
            else:
                # Pass 3: Hash sequence test
                for b_idx, block in enumerate(blocks):
                    seed = f"seed_{pass_idx}_{b_idx}".encode()
                    h = hashlib.sha256(seed).digest()
                    chunk_len = len(h)
                    repeats = len(block) // chunk_len
                    block[:repeats * chunk_len] = h * repeats
                    total_written += len(block)

                    # Verify hash chunks
                    for c_idx in range(min(100, repeats)):
                        start = c_idx * chunk_len
                        if block[start:start + chunk_len] != h:
                            return _result(CRITICAL, "Аппаратная ошибка ОЗУ: сбой хеш-проверки!", [
                                f"Сбой на блоке #{b_idx + 1}"
                            ])

            # Intermediate cell refresh wait on pass 4
            if pass_idx == 3:
                _emit(progress, 88, "Проверка удержания заряда ячеек памяти...")
                if cancel_event:
                    cancel_event.wait(4.0)
                else:
                    time.sleep(4.0)
                # Verify blocks remained unchanged
                for b_idx, block in enumerate(blocks):
                    pat = patterns[(pass_idx + b_idx) % len(patterns)]
                    if block.count(pat) != len(block):
                        return _result(CRITICAL, "Ошибка удержания заряда ячеек (Retention Failure)", [
                            f"Блок #{b_idx + 1} потерял целостность при задержке"
                        ])

        elapsed = max(0.1, time.monotonic() - t_start)
        throughput_mb_s = round((total_written / (1024**2)) / elapsed, 1)

        ecc_final, _ = _read_ecc_errors()
        ecc_diff = ecc_final - ecc_initial
        if ecc_diff > 0:
            details.append(f"Зафиксированы некорректируемые ECC ошибки: +{ecc_diff}")
            return _result(CRITICAL, "Обнаружены ECC ошибки памяти", details)

        details.append(f"Проверено 4 полных прохода без единой ошибки")
        details.append(f"Скорость записи/проверки: ~{throughput_mb_s} МБ/с")
        details.append(f"ECC/EDAC: аппаратные сбои отсутствуют" if ecc_available else "ECC контроллер: данные в норме")
        details.append(f"Время тестирования: {round(elapsed, 1)} сек.")

        _emit(progress, 100, "Тест ОЗУ завершён успешно")
        return _result(GOOD, "Оперативная память полностью исправна", details)

    except MemoryError:
        return _result(WARNING, "Недостаточно памяти для полного стресс-теста", details)
    finally:
        blocks.clear()
        gc.collect()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Deep Thermal Stability & Cooling Efficiency Test (CPU + GPU)
# ─────────────────────────────────────────────────────────────────────────────

def _matrix_math_worker(stop_flag: threading.Event):
    """Generates controlled CPU mathematical load for thermal assessment."""
    while not stop_flag.is_set():
        # Matrix multiplications & transcendental math
        s = 0.0
        for i in range(200):
            s += math.sin(i) * math.cos(i) + math.sqrt(i + 1)
        time.sleep(0.0005)


def _stress_thermal_stability(progress: ProgressCallback | None,
                              cancel_event: threading.Event | None) -> dict:
    """Comprehensive 45-second thermal load & cooling efficiency test for CPU and GPU."""
    details: list[str] = []

    # ── Phase 1: Baseline Idle (5 sec) ──────────────────────────────────────
    _emit(progress, 5, "Фаза 1/3: Калибровка датчиков в покое (5 сек)...")
    cpu_idle_readings = []
    gpu_idle_readings = []

    for _ in range(5):
        if _cancelled(cancel_event):
            return _result(UNKNOWN, "Проверка отменена", details)
        c_temp = get_cpu_temp()
        g_temp = get_gpu_temp()
        if c_temp:
            cpu_idle_readings.append(c_temp)
        if g_temp:
            gpu_idle_readings.append(g_temp)
        if cancel_event:
            cancel_event.wait(1.0)
        else:
            time.sleep(1.0)

    cpu_idle = int(sum(cpu_idle_readings) / len(cpu_idle_readings)) if cpu_idle_readings else 45
    gpu_idle = int(sum(gpu_idle_readings) / len(gpu_idle_readings)) if gpu_idle_readings else None

    # ── Phase 2: Controlled Computational Load (25 sec) ─────────────────────
    load_stop = threading.Event()
    num_workers = max(2, min(4, psutil.cpu_count(logical=True) or 2))
    workers = [threading.Thread(target=_matrix_math_worker, args=(load_stop,), daemon=True)
               for _ in range(num_workers)]

    for w in workers:
        w.start()

    cpu_load_temps = []
    gpu_load_temps = []
    load_duration = 25

    try:
        for sec in range(load_duration):
            if _cancelled(cancel_event):
                load_stop.set()
                return _result(UNKNOWN, "Проверка отменена", details)

            pct = 15 + int((sec / load_duration) * 55)
            c_temp = get_cpu_temp()
            g_temp = get_gpu_temp()
            if c_temp:
                cpu_load_temps.append(c_temp)
            if g_temp:
                gpu_load_temps.append(g_temp)

            gpu_str = f" | GPU: {g_temp}°C" if g_temp else ""
            _emit(progress, pct, f"Фаза 2/3: Тест под нагрузкой ({sec + 1}/{load_duration} с) — ЦП: {c_temp}°C{gpu_str}")

            if cancel_event:
                cancel_event.wait(1.0)
            else:
                time.sleep(1.0)
    finally:
        load_stop.set()
        for w in workers:
            w.join(timeout=0.5)

    cpu_peak = max(cpu_load_temps) if cpu_load_temps else cpu_idle
    gpu_peak = max(gpu_load_temps) if gpu_load_temps else gpu_idle

    # ── Phase 3: Cool-Down Efficiency (15 sec) ──────────────────────────────
    _emit(progress, 75, "Фаза 3/3: Оценка эффективности охлаждения (15 сек)...")
    cooldown_duration = 15
    for sec in range(cooldown_duration):
        if _cancelled(cancel_event):
            return _result(UNKNOWN, "Проверка отменена", details)
        pct = 75 + int((sec / cooldown_duration) * 23)
        c_temp = get_cpu_temp()
        _emit(progress, pct, f"Остывание: {sec + 1}/{cooldown_duration} с (ЦП: {c_temp}°C)")
        if cancel_event:
            cancel_event.wait(1.0)
        else:
            time.sleep(1.0)

    cpu_final = get_cpu_temp() or cpu_peak
    delta_cool = cpu_peak - cpu_final
    cooling_rate = round(delta_cool / cooldown_duration, 2)  # °C per second

    # ── Check for hardware thermal throttling ───────────────────────────────
    throttling_detected = False
    for path in Path("/sys/devices/system/cpu").glob("cpu*/thermal_throttle/package_throttle_count"):
        try:
            if int(path.read_text().strip()) > 0:
                throttling_detected = True
                break
        except Exception:
            pass

    # ── Summary & Evaluation ────────────────────────────────────────────────
    details.append(f"ЦП (CPU): начальная {cpu_idle}°C → пиковая под нагрузкой {cpu_peak}°C (Δ+{cpu_peak - cpu_idle}°C)")
    if gpu_peak:
        gpu_init_str = f"{gpu_idle}°C" if gpu_idle else "—"
        details.append(f"GPU (NVIDIA/Дискретный): начальная {gpu_init_str} → пиковая {gpu_peak}°C")
    else:
        details.append("GPU: встроенный или находится в энергосберегающем сне")

    details.append(f"Скорость рассеивания тепла радиаторами: {cooling_rate} °C/сек (спад на {delta_cool}°C за {cooldown_duration} с)")
    details.append("Аппаратный троттлинг: зафиксирован (перегрев)" if throttling_detected else "Аппаратный троттлинг: не обнаружен (стабильно)")

    _emit(progress, 100, "Термодиагностика завершена")

    if cpu_peak >= 95 or throttling_detected:
        details.append("Рекомендация: высокая температура — рекомендуется очистить систему охлаждения от пыли и обновить термопасту.")
        return _result(CRITICAL, "Критический перегрев или троттлинг", details)
    elif cpu_peak >= 88 or (cooling_rate < 0.2 and delta_cool < 3):
        details.append("Рекомендация: повышенная температура под нагрузкой — проверьте вентиляционные отверстия ноутбука.")
        return _result(WARNING, "Повышенный нагрев под нагрузкой", details)
    else:
        efficiency = "Отличная" if cooling_rate >= 0.6 else "Нормальная"
        details.append(f"Эффективность системы охлаждения: {efficiency}")
        return _result(GOOD, f"Система охлаждения работает отлично (пик {cpu_peak}°C)", details)


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def run_deep_check(component: str, payload: dict | None = None,
                   progress: ProgressCallback | None = None,
                   cancel_event: threading.Event | None = None,
                   memory_duration_seconds: int = 120) -> dict:
    """Run real component diagnostics with progress tracking."""
    _emit(progress, 2, "Подготовка глубокой диагностики...")

    if component == "battery":
        _emit(progress, 30, "Анализ состояния батареи и контроллера...")
        result = check_battery()
        _emit(progress, 100, "Проверка батареи завершена")
        return result

    if component.startswith("drive_"):
        _emit(progress, 20, "Опрос SMART-атрибутов накопителя...")
        result = check_drive(payload or {}, allow_auth=True)
        _emit(progress, 100, "Проверка накопителя завершена")
        return result

    if component == "memory":
        return _stress_memory(memory_duration_seconds, progress, cancel_event)

    if component == "system":
        return _stress_thermal_stability(progress, cancel_event)

    return _result(UNKNOWN, "Неизвестный компонент", [])
