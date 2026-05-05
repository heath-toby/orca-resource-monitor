# Orca Resource Monitor

A customisation add-on for the [Orca screen reader](https://orca.gnome.org/) that provides comprehensive system resource monitoring via keyboard shortcuts.

Replaces Orca's built-in CPU + RAM command with deeper, NVDA-style readouts (per-thread CPU breakdown; physical and swap memory) and adds eight further resource commands covering storage, network, battery, uptime, OS info, audio devices, and system load.

## Keybindings

The instant readouts use **Orca+Shift+number**; the speed test adds Ctrl.

| Shortcut | What you hear |
|---|---|
| Orca+Shift+1 | CPU usage: average load and per-thread breakdown (NVDA-style) |
| Orca+Shift+2 | RAM and swap: physical and swap memory used/total/percent (`free -h`-style) |
| Orca+Shift+3 | Storage volumes with used/total/percent (BTRFS-aware, deduplicates subvolumes) |
| Orca+Shift+4 | Network status: connection name, Wi-Fi/Ethernet, signal, link speed (megabytes per second), IP address |
| Orca+Shift+5 | Battery: percentage, charging state, estimated time remaining |
| Orca+Shift+6 | System uptime |
| Orca+Shift+7 | OS info: distribution, kernel version, architecture |
| Orca+Shift+8 | Audio output: device name, volume, mute state |
| Orca+Shift+9 | Audio input: device name, volume, mute state |
| Orca+Shift+0 | System load (as percentage of capacity), CPU temperature, process count, top process |
| Orca+Ctrl+Shift+4 | Network speed test: ICMP ping, download, upload — runs in the background, ~10 seconds total |

### Speed test

Speed test traffic uses [`speed.cloudflare.com`](https://speed.cloudflare.com)'s public download/upload endpoints (the same ones Cloudflare's own speed-test tool calls). No signup, no per-user tracking beyond standard CF logs. Ping is a normal ICMP echo to `1.1.1.1`. The test runs on a daemon thread so Orca's UI stays responsive — you'll hear "Testing speed. Please wait." immediately, then each result as it completes.

## Requirements

- [Orca](https://orca.gnome.org/) screen reader
- Python 3.10+
- [psutil](https://pypi.org/project/psutil/) (already required by Orca itself)
- [NetworkManager](https://networkmanager.dev/) with `nmcli` (for network status)
- [WirePlumber](https://pipewire.pages.freedesktop.org/wireplumber/) with `wpctl` (for audio device info)

## Installation

```bash
git clone https://github.com/heath-toby/orca-resource-monitor.git
cd orca-resource-monitor
./install.sh
orca --replace
```

The installer copies `resource_monitor.py` into `~/.local/share/orca/` and appends a loader block to `orca-customizations.py`. It does not modify any other add-ons.

## Uninstallation

```bash
./uninstall.sh
orca --replace
```

The uninstaller removes only the resource monitor module and its loader block from `orca-customizations.py`, leaving all other add-ons intact.

## How it works

The add-on registers commands with Orca's `CommandManager` at startup via `orca-customizations.py`. Each command is bound to a keyboard shortcut using Orca's standard keybinding system, so they appear in Orca's keybinding preferences and can be reassigned by the user.

Speech output uses Orca's `presentation_manager` for proper integration with the active speech synthesiser and braille display.

### Speech-friendly output

All output is designed to be clear when spoken:

- Numbers use words: "gigabytes" not "GB", "percent" not "%", "degrees" not a degree symbol
- Storage is rounded to one decimal place, percentages to integers
- Battery time is spoken naturally: "2 hours, 15 minutes remaining"
- System load is presented as a percentage of capacity with a plain-English label (light/moderate/heavy/overloaded) rather than raw load averages

### BTRFS handling

On BTRFS filesystems, multiple subvolumes (/, /home, /var/log, etc.) share the same storage pool. The storage command deduplicates by device, reporting each physical device once rather than repeating identical figures for every subvolume.

## License

MIT
