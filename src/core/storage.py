from __future__ import annotations

import os
from pathlib import Path

import psutil


VIRTUAL_FILESYSTEMS = {"squashfs", "tmpfs", "devtmpfs", "overlay", "iso9660", "efivarfs"}


def _parent_block_device(device_name: str) -> str:
    """Map sda2/nvme0n1p3/mmcblk0p1 to the actual block device."""
    for index in range(len(device_name), 0, -1):
        candidate = device_name[:index]
        if Path(f"/sys/class/block/{candidate}/device").exists():
            return candidate
    return device_name


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _drive_model(device: str) -> str:
    paths = (
        Path(f"/sys/class/block/{device}/device/model"),
        Path(f"/sys/class/block/{device}/device/device/model"),
        Path(f"/sys/class/block/{device}/device/name"),
    )
    return next((value for path in paths if (value := _read_text(path))), f"Локальный диск {device}")

def get_physical_drives() -> list:
    drives_info = []
    disks = {}
    seen_partition_sources = set()

    for part in psutil.disk_partitions(all=False):
        # Ігноруємо системні віртуальні файлові системи та snap-пакети
        if part.fstype in VIRTUAL_FILESYSTEMS or '/snap' in part.mountpoint or '/boot' in part.mountpoint:
            continue
        # Containers and sandboxed environments often bind-mount the same partition
        # many times. One capacity reading is enough for a physical-drive overview.
        if part.device in seen_partition_sources:
            continue
        seen_partition_sources.add(part.device)

        dev_name = part.device.split('/')[-1]
        parent_dev = _parent_block_device(dev_name)
        model = _drive_model(parent_dev)

        try:
            usage = psutil.disk_usage(part.mountpoint)

            if parent_dev not in disks:
                disks[parent_dev] = {
                    'device': f'/dev/{parent_dev}',
                    'block_name': parent_dev,
                    'model': model,
                    'partitions': [],
                }

            disks[parent_dev]['partitions'].append({
                'mount': part.mountpoint,
                'total_gb': round(usage.total / (1024**3), 1),
                'free_gb': round(usage.free / (1024**3), 1),
                'percent': usage.percent
            })
        except PermissionError:
            continue

    # Формуємо фінальний список
    for disk_data in disks.values():
        if disk_data['partitions']:
            drives_info.append(disk_data)

    return drives_info
