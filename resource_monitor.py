"""Orca Resource Monitor Add-on

Provides system resource monitoring commands bound to Orca+Shift+number keys:
  1: CPU usage          2: RAM and swap       3: Storage volumes
  4: Network status     5: Battery info       6: Uptime
  7: OS info            8: Audio output       9: Audio input
  0: System load + temps
"""

from __future__ import annotations

import logging
import platform
import subprocess
import time

import psutil

from orca import command_manager, keybindings, presentation_manager

_log = logging.getLogger("orca-resource-monitor")


def _speak(msg: str) -> None:
    presentation_manager.get_manager().present_message(msg)


def _run_cmd(args: list[str], timeout: int = 3) -> str | None:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("Command %s failed: %s", args, e)
    return None


def _format_size(bytes_val: float) -> str:
    if bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.1f} gigabytes"
    elif bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} megabytes"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} kilobytes"
    else:
        return f"{int(bytes_val)} bytes"


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)

    parts = []
    if days == 1:
        parts.append("1 day")
    elif days > 1:
        parts.append(f"{days} days")
    if hours == 1:
        parts.append("1 hour")
    elif hours > 1:
        parts.append(f"{hours} hours")
    if minutes == 1:
        parts.append("1 minute")
    elif minutes > 1:
        parts.append(f"{minutes} minutes")

    return ", ".join(parts) if parts else "less than a minute"


# --- Mountpoint to friendly name ---

_MOUNT_LABELS = {
    "/": "Root filesystem",
    "/boot": "Boot",
    "/boot/efi": "EFI",
    "/home": "Home",
}

_REAL_FS_TYPES = {"btrfs", "ext4", "ext3", "ext2", "xfs", "f2fs", "ntfs", "vfat", "exfat", "zfs"}


def handle_cpu(script, event=None):
    """Present overall and per-thread CPU usage."""
    try:
        # interval=0.1 blocks ~100ms and gives an accurate snapshot;
        # we derive the average from the per-cpu list so the average
        # and the per-thread numbers are from the same window.
        per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        if not per_cpu:
            _speak("CPU information unavailable")
            return True
        avg = sum(per_cpu) / len(per_cpu)
        parts = [f"Average CPU load {avg:.1f} percent"]
        for i, pct in enumerate(per_cpu, start=1):
            parts.append(f"Thread {i}: {pct:.1f} percent")
        _speak(". ".join(parts))
    except Exception as e:
        _log.error("CPU info failed: %s", e)
        _speak("CPU information unavailable")
    return True


def handle_ram(script, event=None):
    """Present physical and swap memory usage."""
    try:
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        physical = (
            f"Physical RAM: {_format_size(vm.used)} of "
            f"{_format_size(vm.total)} used, {vm.percent:.1f} percent"
        )
        if sm.total > 0:
            swap = (
                f"Swap: {_format_size(sm.used)} of "
                f"{_format_size(sm.total)} used, {sm.percent:.1f} percent"
            )
            _speak(f"{physical}. {swap}")
        else:
            _speak(f"{physical}. No swap configured")
    except Exception as e:
        _log.error("RAM info failed: %s", e)
        _speak("RAM information unavailable")
    return True


def handle_storage(script, event=None):
    """Present storage volume information."""
    try:
        partitions = psutil.disk_partitions(all=False)

        # Group by device to deduplicate BTRFS subvolumes
        seen_devices: dict[str, tuple[str, psutil._common.sdiskusage]] = {}
        for part in partitions:
            if part.fstype.lower() not in _REAL_FS_TYPES:
                continue
            if part.device in seen_devices:
                existing_mount = seen_devices[part.device][0]
                if part.mountpoint == "/" or (
                    part.mountpoint in _MOUNT_LABELS
                    and existing_mount not in _MOUNT_LABELS
                ):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        seen_devices[part.device] = (part.mountpoint, usage)
                    except OSError:
                        pass
            else:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    seen_devices[part.device] = (part.mountpoint, usage)
                except OSError:
                    continue

        if not seen_devices:
            _speak("No storage volumes found")
            return True

        parts = []
        for _dev, (mountpoint, usage) in seen_devices.items():
            label = _MOUNT_LABELS.get(mountpoint, mountpoint)
            used = _format_size(usage.used)
            total = _format_size(usage.total)
            pct = round(usage.percent)
            parts.append(f"{label}: {used} of {total} used, {pct} percent")

        _speak(". ".join(parts))
    except Exception as e:
        _log.error("Storage info error: %s", e, exc_info=True)
        _speak("Storage information unavailable")
    return True


def handle_network(script, event=None):
    """Present network connection status."""
    try:
        output = _run_cmd(
            ["nmcli", "-t", "-f", "TYPE,NAME,DEVICE", "connection", "show", "--active"]
        )
        if output is None:
            _speak("Network information unavailable. NetworkManager not responding.")
            return True

        connections = []
        for line in output.splitlines():
            fields = line.split(":")
            if len(fields) < 3:
                continue
            conn_type, name, device = fields[0], fields[1], fields[2]
            if device == "lo" or conn_type == "loopback":
                continue
            connections.append((conn_type, name, device))

        if not connections:
            _speak("No network connections active")
            return True

        parts = []
        for conn_type, name, device in connections:
            if "wireless" in conn_type:
                msg = f"Wi-Fi: connected to {name}"
                # --rescan no: read the cached scan instead of triggering a
                # fresh radio scan, which can take several seconds and would
                # block Orca's main thread for the whole timeout.
                # RATE is the current link bitrate (varies dynamically on
                # wireless); psutil's net_if_stats.speed always reports -1
                # for WiFi because the kernel doesn't expose a fixed value.
                wifi_out = _run_cmd(
                    ["nmcli", "-t", "-f", "IN-USE,SIGNAL,RATE",
                     "device", "wifi", "list", "--rescan", "no"]
                )
                if wifi_out:
                    for wline in wifi_out.splitlines():
                        wfields = wline.split(":")
                        if len(wfields) >= 2 and wfields[0] == "*":
                            msg += f". Signal: {wfields[1]} percent"
                            if len(wfields) >= 3:
                                # nmcli prints e.g. "1170 Mbit/s" or "0 Mbit/s"
                                rate_str = wfields[2].strip()
                                try:
                                    mbps = int(rate_str.split()[0])
                                    if mbps > 0:
                                        msg += (
                                            f". Speed: {mbps / 8:.1f} "
                                            "megabytes per second"
                                        )
                                except (ValueError, IndexError):
                                    pass
                            break
            elif "ethernet" in conn_type:
                msg = f"Ethernet: connected via {name}"
                stats = psutil.net_if_stats().get(device)
                if stats and stats.speed > 0:
                    # psutil exposes the negotiated link speed (max
                    # theoretical bandwidth) in Mbit/s. Convert to
                    # megabytes per second (divide by 8, base-10).
                    msg += (
                        f". Speed: {stats.speed / 8:.1f} megabytes per second"
                    )
            else:
                msg = f"{name}: connected on {device}"

            addrs = psutil.net_if_addrs().get(device, [])
            for addr in addrs:
                if addr.family.name == "AF_INET":
                    msg += f". IP: {addr.address}"
                    break

            parts.append(msg)

        _speak(". ".join(parts))
    except Exception as e:
        _log.error("Network info error: %s", e, exc_info=True)
        _speak("Network information unavailable")
    return True


def _read_sysfs_int(path: str) -> int | None:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _estimate_battery_time(battery) -> str | None:
    """Estimate battery time from psutil or sysfs when psutil doesn't provide it."""
    if battery.secsleft not in (
        psutil.POWER_TIME_UNLIMITED,
        psutil.POWER_TIME_UNKNOWN,
    ) and battery.secsleft > 0:
        return _format_duration(battery.secsleft)

    bat_path = "/sys/class/power_supply/BAT0"
    current = _read_sysfs_int(f"{bat_path}/current_now")
    if not current or current == 0:
        return None

    if battery.power_plugged:
        charge_full = _read_sysfs_int(f"{bat_path}/charge_full")
        charge_now = _read_sysfs_int(f"{bat_path}/charge_now")
        if charge_full is not None and charge_now is not None:
            remaining = charge_full - charge_now
            if remaining > 0:
                return _format_duration(remaining / current * 3600)
    else:
        charge_now = _read_sysfs_int(f"{bat_path}/charge_now")
        if charge_now is not None and charge_now > 0:
            return _format_duration(charge_now / current * 3600)

    return None


def handle_battery(script, event=None):
    """Present battery status with time remaining."""
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            _speak("No battery detected")
            return True

        pct = round(battery.percent)
        if battery.power_plugged:
            state = "charging" if pct < 100 else "fully charged"
        else:
            state = "discharging"

        msg = f"Battery: {pct} percent, {state}"

        time_est = _estimate_battery_time(battery)
        if time_est:
            if battery.power_plugged:
                msg += f". {time_est} until full"
            else:
                msg += f". {time_est} remaining"

        _speak(msg)
    except Exception as e:
        _log.error("Battery info error: %s", e, exc_info=True)
        _speak("Battery information unavailable")
    return True


def handle_uptime(script, event=None):
    """Present system uptime."""
    try:
        uptime_secs = time.time() - psutil.boot_time()
        _speak(f"Uptime: {_format_duration(uptime_secs)}")
    except Exception as e:
        _log.error("Uptime info error: %s", e, exc_info=True)
        _speak("Uptime information unavailable")
    return True


def _read_os_release() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "Unknown distribution"


def handle_os_info(script, event=None):
    """Present operating system information."""
    try:
        distro = _read_os_release()
        uname = platform.uname()
        msg = (
            f"{distro}. "
            f"Kernel {uname.release}. "
            f"Architecture {uname.machine}"
        )
        _speak(msg)
    except Exception as e:
        _log.error("OS info error: %s", e, exc_info=True)
        _speak("Operating system information unavailable")
    return True


def _get_wpctl_device_info(target: str) -> tuple[str, str]:
    """Returns (device_name, volume_string) for a wpctl target."""
    device_name = "Unknown device"
    volume_str = ""

    vol_output = _run_cmd(["wpctl", "get-volume", target])
    if vol_output:
        parts = vol_output.split()
        if len(parts) >= 2:
            try:
                vol_pct = round(float(parts[1]) * 100)
                volume_str = f"Volume: {vol_pct} percent"
                if "[MUTED]" in vol_output:
                    volume_str += ", muted"
            except ValueError:
                pass

    inspect_output = _run_cmd(["wpctl", "inspect", target])
    if inspect_output:
        for line in inspect_output.splitlines():
            line = line.strip()
            # wpctl marks some lines with "* " prefix
            if line.startswith("* "):
                line = line[2:]
            if line.startswith("node.description"):
                eq_pos = line.find("=")
                if eq_pos != -1:
                    device_name = line[eq_pos + 1:].strip().strip('"')
                break

    return device_name, volume_str


def handle_audio_output(script, event=None):
    """Present audio output device and volume."""
    try:
        name, volume = _get_wpctl_device_info("@DEFAULT_AUDIO_SINK@")
        msg = f"Audio output: {name}"
        if volume:
            msg += f". {volume}"
        _speak(msg)
    except Exception as e:
        _log.error("Audio output info error: %s", e, exc_info=True)
        _speak("Audio output information unavailable")
    return True


def handle_audio_input(script, event=None):
    """Present audio input device and volume."""
    try:
        name, volume = _get_wpctl_device_info("@DEFAULT_AUDIO_SOURCE@")
        msg = f"Audio input: {name}"
        if volume:
            msg += f". {volume}"
        _speak(msg)
    except Exception as e:
        _log.error("Audio input info error: %s", e, exc_info=True)
        _speak("Audio input information unavailable")
    return True


def handle_system_load(script, event=None):
    """Present system load, temperatures, and top process."""
    try:
        parts = []

        load1, load5, load15 = psutil.getloadavg()
        threads = psutil.cpu_count() or 1
        load_pct = round(load1 / threads * 100)
        if load_pct <= 50:
            pressure = "light"
        elif load_pct <= 90:
            pressure = "moderate"
        elif load_pct <= 100:
            pressure = "heavy"
        else:
            pressure = "overloaded"
        parts.append(f"System load: {pressure}, {load_pct} percent of {threads} threads")

        temps = psutil.sensors_temperatures()
        if temps:
            for sensor_name in ("k10temp", "coretemp", "cpu_thermal", "acpitz"):
                if sensor_name in temps:
                    entries = temps[sensor_name]
                    if entries:
                        temp = round(entries[0].current)
                        parts.append(f"CPU temperature: {temp} degrees")
                        break

        pids = psutil.pids()
        parts.append(f"{len(pids)} processes running")

        try:
            # psutil's per-process cpu_percent returns 0.0 the first time
            # it's called for a given PID — there's no baseline to compare
            # against. Prime by sampling once, sleeping briefly, then
            # reading the real values, so the first invocation of this
            # handler in a session reports a top process like the rest.
            procs = []
            sampled = []
            for p in psutil.process_iter(["name"]):
                try:
                    p.cpu_percent(interval=None)
                    sampled.append(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(0.1)
            for p in sampled:
                try:
                    name = p.info.get("name")
                    pct = p.cpu_percent(interval=None)
                    if name and pct is not None:
                        procs.append({"name": name, "cpu_percent": pct})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if procs:
                top = max(procs, key=lambda p: p["cpu_percent"])
                if top["cpu_percent"] > 0:
                    parts.append(
                        f"Top: {top['name']} at {round(top['cpu_percent'])} percent"
                    )
        except Exception:
            pass

        _speak(". ".join(parts))
    except Exception as e:
        _log.error("System load info error: %s", e, exc_info=True)
        _speak("System load information unavailable")
    return True


def register() -> None:
    """Register all resource monitor commands with Orca."""

    manager = command_manager.get_manager()
    group = "Resource Monitor"

    commands = [
        ("resmon_cpu", handle_cpu, "Present CPU usage", "1"),
        ("resmon_ram", handle_ram, "Present RAM and swap usage", "2"),
        ("resmon_storage", handle_storage, "Present storage volumes", "3"),
        ("resmon_network", handle_network, "Present network status", "4"),
        ("resmon_battery", handle_battery, "Present battery with time remaining", "5"),
        ("resmon_uptime", handle_uptime, "Present system uptime", "6"),
        ("resmon_os_info", handle_os_info, "Present operating system info", "7"),
        ("resmon_audio_output", handle_audio_output, "Present audio output device and volume", "8"),
        ("resmon_audio_input", handle_audio_input, "Present audio input device and volume", "9"),
        ("resmon_system_load", handle_system_load, "Present system load and temperatures", "0"),
    ]

    for name, func, desc, key in commands:
        kb = keybindings.KeyBinding(key, keybindings.ORCA_SHIFT_MODIFIER_MASK)
        manager.add_command(
            command_manager.KeyboardCommand(
                name=name,
                function=func,
                group_label=group,
                description=desc,
                desktop_keybinding=kb,
                laptop_keybinding=kb,
            )
        )

    _log.info("Resource monitor: %d commands registered", len(commands))
