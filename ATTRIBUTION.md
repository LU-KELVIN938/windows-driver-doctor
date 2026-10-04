# References and independent implementation

These projects informed the capability design. Source files were reviewed on 2026-10-04. This repository contains a new implementation and newly written guidance; it does not redistribute their source, case-study data, knowledge-base JSON or binaries. Repository license metadata can change; verify upstream before reusing code.

| Reference | Design inspiration | License metadata at review |
| --- | --- | --- |
| [codepros100-dev/claude-windows-health-check](https://github.com/codepros100-dev/claude-windows-health-check) | Broad system audit, PnP/GPU/network/storage checks | MIT |
| [littleyi22/windows-boot-diagnostics](https://github.com/littleyi22/windows-boot-diagnostics) | Genuine-boot baselines, event timelines, services and startup evidence | No explicit license identified |
| [Kwansy98/windbgskill](https://github.com/Kwansy98/windbgskill) | Separate dump, kernel and user-process debugging modes | MIT |
| [sitabanubanu/bsod-analyzer](https://github.com/sitabanubanu/bsod-analyzer) | Evidence layers, permission fallback, driver audit and observation windows | No explicit license identified |
| [itwxb/bsod-diagnostic-skill](https://github.com/itwxb/bsod-diagnostic-skill) | Bugcheck/event/dump correlation and power-IRP investigation | MIT |
| [Kang23K/windows-health-audit](https://github.com/Kang23K/windows-health-audit) | Read-only audit, redaction, unavailable-check reporting | No explicit license identified |
| [varelaia/bsod-forensics](https://github.com/varelaia/bsod-forensics) | Analyze crash artifacts rather than guessing from a stop code | MIT |

Upstream functionality is not evidence that its diagnosis claims are correct. Here, repeated crash offsets and named modules remain clues, not proof excluding physical faults. Inaccessible checks do not become passes. Neither Event 41 nor an old driver date proves a driver problem.

## Authoritative documentation

Use these Microsoft references to validate commands and interpretation:

- [Get-PnpDevice](https://learn.microsoft.com/en-us/powershell/module/pnpdevice/get-pnpdevice)
- [Get-PnpDeviceProperty](https://learn.microsoft.com/en-us/powershell/module/pnpdevice/get-pnpdeviceproperty)
- [PnPUtil syntax](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax)
- [Bug check analysis](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-code-reference2)
- [Analyzing a kernel-mode dump with WinDbg](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/analyzing-a-kernel-mode-dump-file-with-windbg)
- [Event ID 41 troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart)
- [Driver Verifier](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/driver-verifier)

## Optional external tools

[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) can supply sensor evidence if already installed or separately authorized. [DDU](https://github.com/Wagnard/display-drivers-uninstaller) is a graphics-driver removal tool, not a diagnostic dependency. Neither is bundled, installed or launched automatically.
