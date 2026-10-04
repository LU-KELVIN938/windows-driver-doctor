# Crash, blue-screen and debugger workflow

## Establish what happened

Distinguish an app closing, a hang, a blue screen and a forced/power-loss restart. Correlate the user's time with:

- WER-SystemErrorReporting 1001: bugcheck record and dump location.
- Kernel-Power 41: unclean restart; a nonzero BugcheckCode is useful corroboration, not a complete cause.
- EventLog 6008: unexpected shutdown, not a driver diagnosis.
- WHEA-Logger: severity and event payload matter. Event numbers alone do not establish failing hardware.
- Display 4101: driver recovery, possibly related to GPU/driver/power/workload issues.
- Application Error 1000, Application Hang 1002, WER 1001: use the provider and log, not just the numeric ID.

Do not intentionally reproduce a blue screen. Crash artifacts are sufficient to start. Preserve dumps until analyzed. Minidump, full dump and live-kernel dump are different evidence types; do not relabel a live dump as a BSOD dump.

## Dump analysis

Check existing `cdb.exe`/`kd.exe` from Microsoft Debugging Tools. Do not copy Store installation internals, weaken ACLs or download debugger binaries from mirrors. Installing WinDbg/SDK or launching a visible WinDbg window requires its own authorization.

The CLI can run an existing headless `cdb.exe` against an agreed local dump:

```powershell
python scripts/doctor.py dump --dump "D:\evidence\crash.dmp" --debugger "C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe" --out work\dump
```

This reads the dump, writes a local symbol cache/report and contacts Microsoft's symbol server. Explain these effects first. It does not copy/upload the dump, install a debugger or enable live kernel debugging. A timeout is an incomplete analysis, not a clean result. To avoid running any debugger, import saved text using `analyze --debugger-log`.

Inspect `BUGCHECK_CODE`, arguments, `IMAGE_NAME`, `MODULE_NAME`, `FAILURE_BUCKET_ID`, symbol quality and stack. A named module may be where corruption became visible. Confirm the relevant device, driver version and alternative hardware/software explanations.

For 0x9F parameter 1=3, inspect the blocked IRP and device stack (`!irp <P4>`, `!devobj <P2>`); record whether the dump contains enough pages. Other parameter values require a different interpretation. Do not blindly call P4 an IRP for every 0x9F.

## Existing authorized WinDbg HTTP bridge

For a user-provided local bridge (such as windbgskill), confirm the target is an offline dump, not a live process/kernel. Query its status/help first. Restrict to the specifically authorized endpoint; prefer loopback. Command execution on a live target, break/resume, attach, extension loading and exposing a server to another host change the scope and need explicit authorization. The skill does not install or expose a bridge automatically.

## Verification and escalation

No-dump fallback uses event logs, device/driver inventory and hardware signals, with reduced confidence. Do not fabricate a stack. A repeated crash/module increases suspicion but cannot rule out RAM, storage, firmware or power faults.

Driver Verifier can trigger crashes or boot loops. Consider it only after cheaper evidence is exhausted and the user approves selected third-party drivers, recovery steps, BitLocker recovery preparedness and a reset route. Never verify all drivers indiscriminately.

After an approved repair, compare snapshots and agree on a 24–72 hour or workload-specific observation window. A lack of crashes in a short idle session is insufficient to call the incident resolved.
