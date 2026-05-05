# Changelog

All notable changes to Orca Resource Monitor are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.2] — 2026-05-05

Both items deferred from the v1.0.1 audit, addressed by a single
change to the upower call.

### Changed

- **UPower time-remaining now queries the synthetic
  `DisplayDevice`** (`/org/freedesktop/UPower/devices/DisplayDevice`)
  rather than enumerating devices with `upower -e` and string-matching
  battery names. Two benefits:
  - Avoids accidentally picking up a Bluetooth / HID peripheral
    battery (e.g. a wireless mouse's `battery_hidpp_battery_0` that
    happens to enumerate before the laptop's `battery_BAT0`) on
    systems with paired peripherals.
  - One subprocess call instead of two — halves the worst-case
    main-thread block from ~4 s to ~2 s when the upower daemon is
    hung.

## [1.0.1] — 2026-05-05

A polish release. The four items deferred from the v1.0 audit, plus a
new battery-time backend.

### Changed

- **Battery time-remaining now prefers `upower`** when available. UPower
  runs as a system service on most modern Linux desktops and synthesises
  a smoothed energy-rate even on AMD systems that only expose
  `current_now`/`charge_now` — matching the number GNOME's own battery
  applet reports. Falls back through psutil's reported value, then raw
  sysfs (charge-based, then energy-based), keeping older / minimal
  systems working.
- Top-process readout in `Orca+Shift+0` now samples over **300 ms
  instead of 100 ms**. Many-core systems were producing jittery results
  in the shorter window — bursty processes blipped in and out of the
  sample.
- Battery time estimation gained an **energy-based sysfs path**
  (`energy_now` / `power_now`) for newer Intel laptops that don't
  expose `charge_now` / `current_now`. AMD machines (which expose
  charge-based fields) now also get the upower-derived estimate.

### Fixed

- **UPower output is now invoked with `LC_ALL=C`** so the decimal
  parser doesn't silently fall through on non-English locales.
  Previously, `upower` in (e.g.) de_DE printed `3,6 hours` and
  `float("3,6")` raised `ValueError`, disabling the entire upower path
  for any user in a comma-decimal locale (most of Europe and LATAM).

### Internal

- `_run_cmd` gained an optional `env` parameter for callers that need
  to override the inherited environment.
- `urllib.request` import moved to module top (out of the speedtest
  hot path).
- Redundant `Content-Length` header dropped from `_measure_upload` —
  `urllib.request` sets it automatically when `data=` is bytes.
- New `_ratio_to_duration` helper extracted from
  `_estimate_battery_time` so the charge-based and energy-based sysfs
  paths share their arithmetic.
- `__version__` constant added at module top.

## [1.0.0] — 2026-05-05

First tagged release. The repository had been in pre-1.0 churn —
keybindings shifted as new handlers landed, with no public version to
break compatibility from. v1.0 is the line in the sand: anything that
moves a binding or removes a handler from here on will be a major bump.

### Features

- Ten resource readouts on **Orca+Shift+digit**:
  - **1: CPU** — average load and per-thread breakdown (NVDA-style).
  - **2: RAM and swap** — physical and swap memory used / total /
    percent (`free -h`-style; "No swap configured" when none).
  - **3: Storage** — volumes with used/total/percent. BTRFS-aware:
    deduplicates subvolumes that share a pool.
  - **4: Network status** — connection name, Wi-Fi/Ethernet, signal
    (Wi-Fi), link speed in megabytes per second, IP address.
  - **5: Battery** — percentage, charging state, estimated time
    remaining.
  - **6: Uptime** — system uptime in days/hours/minutes.
  - **7: OS info** — distribution, kernel version, architecture.
  - **8: Audio output** — device name, volume, mute state.
  - **9: Audio input** — device name, volume, mute state.
  - **0: System load** — load as percentage of capacity, CPU
    temperature, process count, top process by CPU.
- **Orca+Ctrl+Shift+4: network speed test** — ICMP ping, download,
  upload against [`speed.cloudflare.com`](https://speed.cloudflare.com)
  endpoints. Runs on a daemon thread so Orca's UI stays responsive;
  speaks each result as it completes (~10 seconds total).
- All speech uses full words and decimal units ("megabytes per
  second", not "MB/s"; "percent", not "%") to be cleanly TTS-friendly.
- Self-contained loader block in `orca-customizations.py` — sets up
  `sys.path` itself so it can be the only plugin or appear in any
  position alongside other Orca customizations.

### Fixed (during the pre-release cycle)

The following bugs were caught during pre-1.0 audits and fixed before
this tag:

- `nmcli device wifi list` now passes `--rescan no` to read the cached
  scan instead of triggering a fresh radio scan that blocked Orca's
  main thread for the full timeout.
- Top-process readout primes `cpu_percent` with a sample-sleep-read
  pattern so the very first `Orca+Shift+0` press in a session reports
  a top process instead of silently dropping the line.
- `_REAL_FS_TYPES` typo `"f2s"` → `"f2fs"` (users with f2fs partitions
  no longer lose them from the storage readout).
- Temperature lookup falls through to the next preferred sensor when
  the first matching key has an empty list.
- `nmcli -t` field parsing now respects backslash-escaped colons, so a
  connection name like `Home: 5G` parses as one field, not three.
- `handle_speedtest` rejects re-entry while a test is already running
  ("Speed test already in progress") — prevents concurrent threads
  from competing for bandwidth and interleaving speech.
- Download speed test bails after five consecutive empty responses to
  avoid spinning on a degenerate proxy/CDN that 200-OKs zero-byte
  bodies.
- `_format_duration` returns "less than a minute" for negative input
  (clock skew safety).
- Loader block now ships a defensive `sys.path` setup of its own
  rather than depending on a sibling addon (e.g. an old
  `orca_autoswitch` block) to have set it.

### Known limitations

- Battery time-remaining estimation uses sysfs `charge_now`/`current_now`
  only. Some newer Intel laptops only expose `energy_now`/`power_now`;
  on those, time-remaining is omitted from the readout.
- Network speed test speaks only after each phase completes (no
  mid-phase progress). The "please wait" announcement is the only
  feedback during the ~5-second download/upload windows.
