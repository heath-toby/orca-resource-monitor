# Changelog

All notable changes to Orca Resource Monitor are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
