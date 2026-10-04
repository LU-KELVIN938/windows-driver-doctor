# Windows Driver Doctor

**Evidence-based Windows driver, device, boot and crash diagnostics for AI agents.**

[![Validate](https://github.com/LU-KELVIN938/windows-driver-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/LU-KELVIN938/windows-driver-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-126f69.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)](#run-without-an-agent)
[![English / 中文](https://img.shields.io/badge/Language-English%20%2F%20中文-126f69.svg)](README.zh-CN.md)

![Evidence pipeline](docs/architecture.svg)

English is the default. [简体中文说明](README.zh-CN.md) · [Skill instructions](SKILL.md) · [Feature map](references/coverage.md)

Investigate device errors, GPU/audio/network/USB problems, blue screens, sleep/wake failures and slow boot with a native read-only collector, offline analysis and before/after comparison. Results separate facts, hypotheses and missing evidence. No automatic driver update, cleanup, reboot or security change.

## Install the skill

Copy this repository, excluding `.git`, into your agent's skill directory:

| Agent | Directory |
| --- | --- |
| Codex | `~/.codex/skills/windows-driver-doctor/` |
| Claude Code | `~/.claude/skills/windows-driver-doctor/` |
| Cursor | `.cursor/skills/windows-driver-doctor/` |
| Other compatible agents | `.agents/skills/windows-driver-doctor/` |

Ask: “Use windows-driver-doctor to investigate why my Wi-Fi drops after sleep.” The agent can collect relevant evidence, interpret it, then propose a targeted next step. Permissions for system changes and screen operations remain separate.

## Run without an agent

Requires Windows 10/11, Windows PowerShell 5.1 or PowerShell 7, and Python 3.10+. No third-party Python packages. Start **without** administrator elevation.

```powershell
python scripts/doctor.py collect --out work\audit
python scripts/doctor.py collect --out work\audit-zh --lang zh
python scripts/doctor.py analyze --input work\audit\snapshot.json --out work\report
python scripts/doctor.py analyze --input work\audit\snapshot.json --debugger-log work\analyze.txt --out work\crash-report
python scripts/doctor.py compare --before work\before\snapshot.json --after work\after\snapshot.json --out work\comparison
```

Each command writes an English-first HTML report with an English/Chinese switch. `--lang zh` changes the initial viewer language and Markdown output. Open the HTML file yourself when ready; the command does not launch a browser. Existing output files are refused unless you pass `--overwrite`.

### Demo: no inspection of your computer

```powershell
python scripts/doctor.py analyze --input examples\demo-snapshot.json --out work\demo
```

The bundled sample is synthetic and clearly labeled in its reports. It illustrates a device error, a recorded bugcheck and incomplete evidence; it is not a real machine diagnosis.

## What you get

- Present-device problem codes; disconnected devices kept separate.
- Signed-driver versions, providers, dates, INF names and device association.
- GPU, audio, USB, network, disk health, battery and firmware inventory.
- Boot timings, slow startup components, startup entries and automatic-service state.
- BugCheck, display, WHEA, service-timeout and application-crash timelines.
- Local dump metadata and optional interpretation of saved WinDbg output.
- Security context: Defender, firewall, BitLocker, Secure Boot and TPM availability.
- Before/after driver and device changes, new events, comparable boot records.
- Offline bilingual reports with best-effort redaction and no external dependencies.

The report is an evidence summary, not a guarantee that a particular driver caused the symptom. The JSON marks inaccessible sections explicitly. Collection is bounded by the event window and maximum event counts; an empty bounded result does not establish lifetime absence.

## Privacy and operation boundaries

The collector reads relevant local evidence and writes requested report files. It does not upload dumps, contact driver download sites, install tools or change settings. Device identity is hashed by default; usernames, common user-directory paths, serial fields and private IPv4 addresses are redacted where detected. This is **best-effort redaction**, not anonymization. Review before publishing a report. Do not commit real machine snapshots or dump files to this repository.

No invented “health score”, driver-age alarm, automatic registry cleanup, bulk DriverStore removal or hardcoded blacklist of allegedly bad drivers. Exact version advisories must be verified against an OEM/vendor bulletin. Driver Verifier, DDU and firmware changes need a separate, explicitly authorized plan.

## Testing

```powershell
python -m unittest discover -s tests -v
```

CI checks the offline analyzer on Linux and Windows and parses the collector with Windows PowerShell 5.1 and PowerShell 7. Windows CI also exercises a bounded live read-only collection. Neither CI nor the demo demonstrates root-cause accuracy on every device. Real incident validation remains necessary.

## Origins

Independently implemented after reviewing several public skills. See [ATTRIBUTION.md](ATTRIBUTION.md) for links and the functionality reference map. Their code, driver blacklists, case studies and diagnosis claims are not bundled. No affiliation with those authors or Microsoft is implied.

Licensed under MIT. Windows, WinDbg, Codex and other product names belong to their respective owners.

## Why use a skill instead of an ad hoc Codex conversation?

Codex can already write good diagnostic commands. This project adds reusable engineering around that reasoning: a consistent collector, machine-readable evidence, explicit missing-check states, stable device identities, reproducible comparisons and bounded model handoffs. It makes the workflow easier to repeat and review; it does not claim to make the underlying model smarter.

| Need | What this project provides |
| --- | --- |
| Repeat the same check after a repair | The same collector and versioned JSON schema |
| Explain which driver belongs to a problem device | Device → signed-driver → configuration-event association |
| Avoid drowning the agent in hundreds of drivers/events | Focused `summary.json` and bounded evidence retrieval |
| Distinguish power loss, app failure and a bugcheck | Provider-aware event classification and honest uncertainty |
| Audit the result later | Code/settings/input/output hashes in `manifest.json` |
| Share with a nontechnical user | English/Chinese HTML and Markdown reports |
| Avoid repeating plausible but wrong shortcuts | Behavioral tests for common false conclusions |

These are concrete workflow capabilities. A fair claim of greater diagnostic accuracy or lower total token cost than plain Codex still needs real incident evaluation; see [validation](docs/VALIDATION.md).

## Diagnosis workflow

1. **Frame the symptom.** Identify the affected function, occurrence time, workload and recent Windows/driver/hardware change.
2. **Collect without repairing.** Run bounded native queries as the current user. Mark inaccessible sources and preserve local crash artifacts.
3. **Associate evidence.** Connect a present device's numeric problem code with its signed-driver records and recent configuration events. Center a timeline on the incident when a timezone-aware time is provided.
4. **Reason from a compact handoff.** Start with the summary. Fetch only rows that can change the diagnosis; separate observed facts from potential explanations.
5. **Propose one targeted step.** Check an exact OEM package, correlate a dump, obtain missing evidence or plan a reversible repair.
6. **Verify after an approved change.** Compare a later snapshot from the same computer. For intermittent problems, agree on an observation window.

### Incident-centered example

```powershell
python scripts/doctor.py collect --out work\wifi-incident --focus drivers `
  --incident-time "2026-10-04T09:00:00+08:00" --days 7 --max-events 100
```

The timeline shows events within ±30 minutes and device-configuration records from the preceding seven days. A temporal match is a lead, not a causal verdict. Driver file dates are never relabeled as installation dates.

## Designed to reduce model context

Full inventory stays on disk. The agent starts with a compact JSON handoff and retrieves evidence only when it needs it:

```powershell
python scripts/doctor.py brief --input work\audit\findings.json --focus crash --max-chars 1800
python scripts/doctor.py evidence --input work\audit\snapshot.json --section drivers `
  --device-key aabbccdd00112233 --limit 5 --max-chars 2500
```

- Default summary budget: **2,400 characters of compact JSON**, adjustable from 800 characters.
- Symptom focus: `drivers`, `crash`, `boot` or `all`.
- Factual anchors: device codes/identities or event fields, plus confidence and evidence counts.
- Missing checks and synthetic-data markers survive the handoff.
- `truncated` tells the agent when it needs targeted follow-up.
- Full evidence remains available; compression does not erase alternative causes.

The cap applies to compact JSON, not indentation in the saved file. `brief` emits compact JSON directly. It limits input payload, not reasoning/output tokens or the total size of an entire diagnosis session.

### Reproducible payload experiment

```powershell
python scripts/benchmark-context.py
python scripts/benchmark-context.py --lang zh
```

See [English results](docs/context-benchmark.en.json) and [Chinese results](docs/context-benchmark.zh.json). The fixture contains 400 additional healthy devices/drivers and 600 application events. Results compare a full compact snapshot with one crash-focused handoff.

| Synthetic payload | Characters | Reduction in this experiment |
| --- | ---: | ---: |
| Full compact snapshot | 227,325 | — |
| English crash-focused handoff | 1,034 | 99.55% |
| Chinese crash-focused handoff | 710 | 99.69% |

**This is a synthetic character-payload experiment. It does not measure actual model tokens, billed cost, diagnostic accuracy, total-session saving or a plain-Codex baseline.** Follow-up retrieval, tokenizer, language, prompt caching and reference loading all affect real usage.

## Report contents

| File | Purpose |
| --- | --- |
| `summary.json` | Bounded model handoff; read this first |
| `snapshot.json` | Full sanitized source evidence and collection coverage |
| `findings.json` | Findings, evidence references, confidence and bilingual wording |
| `report.html` | Offline English/Chinese viewer, filtering, search and printing |
| `report.md` | Human-readable explanation in the selected language |
| `manifest.json` | Tool version, code hash, settings, input/output hashes and payload measurements |
| `comparison.json` | Present only for before/after comparisons |
| `debugger.txt` | Present only for explicitly invoked headless CDB analysis |

[Downloadable synthetic viewer](docs/demo-report.html): save the file and open it locally. GitHub's normal file viewer displays its source rather than running HTML. It has no external assets and its demo marker is visible in both languages.

## Diagnosis modes

| Mode | Typical question | Useful evidence |
| --- | --- | --- |
| Devices/drivers | “Why is this device showing an error?” | Presence, numeric PnP code, exact driver/INF, configuration records |
| GPU | “Why did my display freeze or recover?” | Controller version, display recovery, WHEA, workload and dump clues |
| USB/audio/network | “Why is the device missing or disconnecting?” | Device class, endpoint/link status, sleep/wake and package association |
| BSOD/restart | “Why did Windows crash or reboot?” | Provider-specific bugcheck, dump metadata, WinDbg text, alternative hardware signals |
| Boot | “Why is startup or login slow?” | Genuine Event 100 records, slow components, services, startup/logon tasks |
| Verification | “Did the repair help?” | Later snapshot, changed driver/device state, new captured events, distinct boot records |

### Optional headless debugger

```powershell
python scripts/doctor.py dump --dump "D:\evidence\crash.dmp" `
  --debugger "C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe" --out work\dump
```

This explicitly runs an existing Microsoft CDB, reads the provided local dump and writes a symbol cache. Microsoft symbol lookup uses the network. It does not install a debugger, copy/upload the dump, open a visible window or attach a live process. Saved text import requires none of those effects. An existing user-authorized WinDbg HTTP bridge is covered in [crash guidance](references/crashes.md); its DLL is not bundled.

### Optional local vendor advisories

Pass `--advisories advisories.json` to `collect` or `analyze`. Exact `.sys` names, optional provider text and inclusive numeric version ranges can be matched locally. Matches remain hypotheses pending vendor verification. See the [JSON contract](references/schema.md). No blacklist or network-loaded instruction is treated as truth.

## CLI reference

| Command | Reads | Produces / effect |
| --- | --- | --- |
| `collect` | Live native Windows evidence | Local reports; no elevation or repairs |
| `analyze` | Existing snapshot and optional debugger/advisory text | Offline reports |
| `compare` | Two ordered snapshots of the same machine | Change report; never treats a missing inventory as removals |
| `dump` | User-provided dump and existing CDB | Local analysis text and symbol cache; Microsoft symbol network lookup |
| `brief` | `findings.json` | Bounded compact JSON on stdout |
| `evidence` | Snapshot section, optional device filter | Bounded compact rows on stdout |

Run `python scripts/doctor.py COMMAND --help` for exact options. Collection supports a 1–90 day event window and 1–2,000 events per queried log. `--focus` changes the model handoff, not what the native collector attempts to capture. Missing fields/logs depend on Windows edition, OEM, permissions and provider support.

## Frequently asked questions

**Does it automatically fix drivers?** No. It collects and explains evidence. The agent can plan a narrow repair after separate authorization, recording rollback and verification.

**Is it a driver download/updater app?** No. It avoids bulk-update recommendations and third-party package mirrors. OEM matching still requires the exact model/hardware and supported package.

**Does Event 41 prove my PSU or GPU is bad?** No. It means an unclean restart. A nonzero bugcheck code and matching artifacts help distinguish a blue screen; they still do not prove a component is defective.

**Why not update every old driver?** Dates can be deliberate, especially for inbox drivers. Supported versions and exact hardware matter more than apparent age.

**Can I use it without a connected Windows machine?** Yes. Analyze existing snapshots and saved debugger text on other platforms. Live collection and running CDB require Windows.

**Does it need administrator privileges?** Not for the default workflow. Some evidence may be unavailable. The agent should request only the specific elevated check that matters, rather than rerunning everything elevated.

**Can I publish its reports?** Review them first. Best-effort redaction is not complete anonymization. Do not upload actual memory dumps or commit real machine evidence to this repository.

**Does it guarantee fewer Codex tokens or better accuracy?** No blanket guarantee. It provides bounded input, reusable collection and tested interpretation boundaries. Actual total cost and accuracy need real-case evaluation.

## Project status and contributions

This project is an early implementation with synthetic behavior tests and a Windows CI workflow. Real-world compatibility and diagnostic accuracy need more incident feedback. Useful contributions include a minimal synthetic reproducer, a provider-specific parser, bilingual improvements or verified advisory matching. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [validation details](docs/VALIDATION.md).

If the workflow helps you, a star makes the project easier to discover. Redacted reproducible issues and focused pull requests are especially useful for improving its reliability.
