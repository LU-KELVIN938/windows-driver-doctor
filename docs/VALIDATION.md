# Validation and evaluation

## What is checked

The local standard-library test suite checks 32 behaviors:

- Detached/code-45 devices are not active failures.
- Presence uncertainty remains incomplete evidence.
- Device problems link to matching driver and configuration evidence.
- Event 41 without a nonzero code is not a blue-screen verdict.
- Application Event 1001 is not confused with a kernel bugcheck.
- Event provider identity is used, not just event numbers.
- Inaccessible checks are not passes; a missing snapshot is not healthy.
- Old driver dates do not produce update alarms.
- Named crash modules remain hypotheses; symbol failures are disclosed.
- Incident correlation requires timezone-aware timestamps and bounded windows.
- Before/after comparison rejects different computers and reversed timestamps.
- Same boot records are not presented as improvement.
- Inaccessible inventory is not presented as mass driver removal.
- Driver-version changes and new event windows are detected.
- Private fields are redacted while numeric driver versions survive.
- HTML evidence is escaped, with no external scripts/fonts/styles.
- English and Chinese viewers retain the synthetic marker.
- Compact summaries and evidence exports obey context limits.
- Vendor ranges are inclusive, malformed versions are incomplete and non-HTTPS URLs are rejected.
- Offline CLI writes hash-verifiable manifests and refuses accidental overwrite.

Run `python -m unittest discover -s tests -v`. See the exact cases in [tests/test_doctor.py](../tests/test_doctor.py). As tests grow, the runner output is the authoritative count.

CI executes the offline suite on Windows/Linux and Python 3.10/3.13. Windows CI checks PowerShell 5.1/7 syntax and bounded live collection on a disposable runner. CI output deliberately avoids uploading machine inventories as public artifacts.

## Context payload experiment

`scripts/benchmark-context.py` constructs the bundled synthetic incident with 400 additional healthy devices/drivers and 600 application events. It compares the entire compact JSON snapshot with a 2,400-character crash-focused handoff. Machine-readable results are in `docs/context-benchmark.en.json` and `docs/context-benchmark.zh.json`.

This measures a controlled payload reduction. It does **not** measure model tokens, actual cost, total-session saving, diagnosis accuracy or performance against a plain-Codex session. The same-sized fixture is an illustrative benchmark, not a representative Windows population.

## What remains unproven

- Correct root-cause identification across real heterogeneous Windows incidents.
- Accuracy superiority or lower total token cost compared with unassisted Codex.
- Compatibility of every WMI provider and protected log on managed/OEM/Insider systems.
- Headless CDB behavior with every dump format, debugger build and symbol environment.

For a fair real-case evaluation, give both approaches identical de-identified artifacts and model/tool settings. Use blinded reviewer scoring for supported conclusions, missed alternative causes, actionable next steps and unnecessary changes. Record total input/output tokens and time. Do not convert a synthetic payload reduction into a blanket performance claim.
