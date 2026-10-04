# Repair planning and rollback

Collect and interpret first. Every repair proposal should include the exact target, intended effect, evidence, side effects, previous state, rollback and a verification step. Match authorization to the actual action; diagnosis does not imply remediation. User approval already given for the same explicit action should not be requested again.

Use this order where evidence supports it:

1. Resolve an obvious connection/routing or completed-update issue.
2. Check the computer manufacturer's support page for the exact model/hardware ID. Prefer OEM-supported chipset/USB/audio/network packages on laptops; evaluate GPU vendor packages against OEM requirements.
3. For a temporal regression, consider rolling back the specific driver rather than updating every driver. Preserve the current package/version and a recovery route first.
4. Reinstall or remove only the identified package/software when authorized. `pnputil /enum-drivers` is inventory; deletion flags are a different operation.
5. Escalate to firmware, hardware testing or Driver Verifier only with evidence and a recovery plan.

DDU, BIOS/UEFI updates, TPM operations, signature-enforcement changes, bulk ghost-device removal and DriverStore deletion are never default fixes. Do not clean registry keys, CloudStore, caches or temp files as a generic blue-screen remedy. Display-driver recovery or a module name alone does not justify DDU.

System repair commands (`sfc`, repairing DISM modes, CHKDSK repair), Defender scans, Windows Update, `winget`, device enable/disable, power changes and task creation have side effects. Explain and authorize each necessary logical group before executing. A documented user-approved exception is scope-specific, not a global permission.

No automatic UAC retry, SYSTEM-task workaround or privilege escalation. If an action is blocked, report the reason and a supported alternative. Never hide a reboot inside another command.

After a change, record result and compare a fresh snapshot; `compare` identifies driver/device changes and new captured events. Verify the user's actual workload/symptom, not just command exit code. Restore the old setting if it did not help or introduced a regression.

## Monitoring when requested

Agree on cadence, output retention, privacy, alert conditions and observation window. A scheduled monitor may run only the collector/comparison and notify on meaningful change; it must never repair, delete, install, disable or reboot. Use the agent's scheduler if available, otherwise a user-approved Task Scheduler plan. Never create a monitor just because the skill supports one. Real reports stay outside this repository.
