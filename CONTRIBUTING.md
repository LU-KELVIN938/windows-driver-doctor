# Contributing

Useful contributions include a redacted real-case failure mode, a provider-specific event parser, bilingual wording, a focused regression test or an OEM advisory integration with a verifiable source.

Before opening a pull request:

1. Keep collection read-only and non-elevated by default. No automatic repair, browser launch or privilege workaround.
2. Do not include real dumps, hardware IDs, serials, names, IPs, recovery material or private command lines. Prefer small synthetic fixtures.
3. Distinguish facts, temporal correlations and causes. Modules and event numbers alone do not establish root cause.
4. Add a behavior test for a demonstrated failure. Keep English and Chinese report strings paired.
5. Run `python -m unittest discover -s tests -v`. If changing PowerShell, check both 5.1 and 7 compatibility.
6. Update the data contract and English/Chinese documentation when changing observable behavior.

Check [docs/VALIDATION.md](docs/VALIDATION.md) before adding a performance claim. Vendor issue data needs a source, exact affected range and review date; unsupported driver blacklists are not accepted as diagnostic truth.
