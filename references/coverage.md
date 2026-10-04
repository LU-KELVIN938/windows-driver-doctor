# Capability map

This table maps reviewed projects to capabilities; it is not a claim of equivalent accuracy or a redistribution of their implementations.

| Inspiration | Implemented here | Boundary |
| --- | --- | --- |
| claude-windows-health-check | PnP codes, signed-driver inventory, GPU/network/audio/USB, storage, resource/security/startup context | Numeric PnP codes replace status-only guessing; no arbitrary health score or automatic cleanup |
| windows-boot-diagnostics | Event 100 baseline, component events, service timeouts, startup/services/tasks, targeted sync/TPM/servicing guidance | A separate real boot is required; detailed component remediation is agent-guided |
| windbgskill | Dump/kernel/user debugging guidance, existing bridge integration instructions, saved-log interpretation and headless CDB analysis | Does not redistribute its DLL, expose a network server or attach live targets automatically |
| bsod-analyzer | Layered evidence, permission fallback, bugcheck interpretation, local advisory matching, repair/observation workflow | No unverified blacklist, destructive cleanup or privilege bypass |
| bsod-diagnostic-skill | Provider-aware BugCheck/Kernel-Power correlation, minidump metadata, symbol/IRP workflow, English/Chinese reports | No universal hardware exclusion or automatic sleep/hibernate workaround |
| windows-health-audit | Read-only collection, best-effort redaction, unavailable checks, creator-workload preservation | Screen access remains explicitly authorized; no scheduled mutation |
| bsod-forensics | Real dump analysis and module/function evidence, offline log input | Stack/module repetition is not proof of root cause |

## Additional capabilities

- English-first self-contained report viewer with Chinese switching, print styling, severity filters and collapsible inventory.
- Standard-library Python CLI, explicit JSON contract and safe output-overwrite behavior.
- Snapshot comparison: driver added/removed/version changes, device problem transitions, new captured events, distinct boot records and cross-machine warnings.
- Privacy-aware collector plus imported-data sanitation, stable hashed device keys and no remote report assets.
- Optional local vendor advisory feed: bounded numeric version matching and explicit source-validation limits.
- Offline operation from existing snapshots/debugger logs, including non-Windows analysis.
- Synthetic demo and behavioral tests for false positives, privacy, HTML injection, chronology, missing permissions, version ranges and comparison.
- Windows/PowerShell compatibility checks and bounded collection in CI.

The collector gathers supported evidence; the agent performs symptom-specific judgment and approved repair planning. A feature being listed does not mean this project has validated diagnosis accuracy across all Windows hardware.
