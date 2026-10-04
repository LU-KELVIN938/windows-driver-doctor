# Boot and post-login performance

Record Windows version/build, last boot time, actual restart versus resume, current update/servicing activity, available disk space and memory pressure. Read Diagnostics-Performance Event 100, `BootTime`/`BootDuration`, `MainPathBootTime`, `BootPostBootTime`; convert milliseconds to seconds. Compare the newest valid boot with up to 20 earlier valid records, labeling sample count and boot mode uncertainty.

Events 101/102/103 identify delayed application/driver/service components recorded by Windows. `DegradationTime` is a comparison against Windows' own baseline; presence does not prove the component caused a crash. Service Control Manager 7000/7009/7011/7023/7031 can give a related failure or timeout. Preserve exact component names locally when needed.

Compare different Event 100 record IDs and times. A later collection with the same event is not a new boot. Hybrid/fast startup and full restart may not be comparable. The generated comparison reports this uncertainty and does not label boot speed improved automatically.

Collect startup commands, selected startup registry entries, automatic services and enabled scheduled tasks with boot/logon triggers. Treat missing files as candidates to verify, not permission to uninstall. Registry startup entries and service paths can contain private arguments; shared reports omit full command lines.

Targeted contexts:

- **Windows Update/Defender:** distinguish servicing or scanning from a persistent driver regression. Do not disable protections to make a benchmark look better.
- **Google Drive/OneDrive:** keep required sync. Correlate active sync, streaming/mirroring and current load; recommend scope/bandwidth changes only against observed contention. Do not delete unsynced caches.
- **Phone Link/cross-device:** service groups may also support clipboard, nearby sharing or connected devices. Determine whether the user needs those functions before proposing a change.
- **TPM/CSME/firmware:** repeated timeouts plus matching events justify checking OEM packages; security services are not optional merely because they were slow.
- **WSL/Docker/creator workloads:** cache files, model weights, shader caches, virtual disks and GPU runtimes may be required. Memory pressure is measured via commit, not just occupied RAM. Do not clean these during driver diagnosis.

Choose one reversible change, record previous state and measure after a genuine restart. Ask the user to restart if needed; do not restart automatically. If the necessary log is absent, explicitly state that boot timing was not verified.
