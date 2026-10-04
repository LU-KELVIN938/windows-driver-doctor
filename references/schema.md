# Data contracts

Snapshots use `schema_version: 1`, an ISO-8601 `captured_at` with timezone offset, a hashed `machine_id`, `synthetic`, `collection` metadata and `sections`.

Each section is `{ "status": "ok|partial|not_verified", "reason": "...", "data": [...] }`. An unavailable provider, insufficient permission or unsupported platform is `not_verified`, not an empty pass. Data is always a list, including single system records. Some sources can report `partial` if per-device queries fail. Input file size is limited to 20 MiB.

Important section fields:

- `devices`: `device_key`, `name`, `class`, `present` (boolean or null), `problem_code` (integer or null), `status`.
- `drivers`: `device_key`, `device_name`, `version`, `provider`, `date`, `inf`, `signed`, `driver_file`.
- `events`: `log`, `provider`, `id`, `record_id`, `time`, `level`, `bugcheck_code` (integer or null), optional sanitized `data` fields. Raw localized messages are not included.
- `driver_events`: Kernel-PnP configuration `id`, `time`, `record_id`, hashed `device_key`, `inf` and observed `version`. These are configuration records, not proof of installation or the driver file's compile date.
- `boot`: `record_id`, `time`, `boot_ms`, `main_path_ms`, `post_boot_ms`, optional `boot_start`, `is_degradation`.
- `dumps`: `name`, `kind` (`minidump|kernel|live`), `bytes`, `modified`; no memory content.
- `disks`: `name`, `health`, `operational`, `bytes`; `disk_reliability` supplies observed counters separately.
- `resource`: `total_memory_kb`, `free_memory_kb`, `commit_percent`, plus best-effort CPU fields.

Other section names: `system`, `gpu`, `audio`, `usb`, `network`, `battery`, `startup`, `services`, `tasks`, `boot_components`, `security`. Original source state is preserved where supported.

Reports include a `findings` list with stable `id`, `severity` (`warning|info`), `confidence` (`observed|hypothesis|incomplete`), English/Chinese `title`, `detail` and `next_step` maps, plus bounded `evidence`. Findings don't represent a health score. `debugger` and `comparison` are optional. HTML displays selected inventory; detailed sanitized evidence remains in `findings.json`/`snapshot.json`.

## Local vendor advisory list

Optional `analyze --advisories advisories.json` or `collect --advisories advisories.json`:

```json
{
  "schema_version": 1,
  "advisories": [
    {
      "id": "vendor-bulletin-id",
      "driver_file": "example.sys",
      "provider_contains": "Example Vendor",
      "min_version": "1.0.0.0",
      "max_version": "1.2.9.9",
      "title": "User-reviewed advisory title",
      "source_url": "https://vendor.example/support/bulletin",
      "reviewed_on": "2026-10-04"
    }
  ]
}
```

Both endpoints are inclusive. Versions must be dot-separated nonnegative integers with at most eight parts; matching pads missing parts with zero. Required identity is the exact `.sys` basename plus an optional provider substring. Missing or unparseable inventory versions do not match silently: they are reported as unverified candidates. The URL must use HTTPS; this validates syntax only. Source credibility, authenticity and current applicability need human/agent verification. Advisories never supply executable commands.
