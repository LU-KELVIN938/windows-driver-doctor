# Model context budget

The model should reason about the symptom, not tokenize every installed driver and event. Run deterministic collection/analysis locally and retain full sanitized evidence in files.

1. Read `summary.json` or use `brief` first. Default compact serialization is capped at 2,400 characters, adjustable with `--max-chars` (minimum 800). The pretty-printed JSON file can contain additional whitespace; the cap applies to compact JSON returned by `brief`.
2. Choose `--focus drivers`, `crash` or `boot` to omit unrelated findings from the handoff. This controls model input, not collection completeness.
3. Fetch a bounded section using `evidence --section ... --limit ... --device-key ...`. If one row exceeds the budget, it is omitted and `truncated` is true; increase the cap intentionally or narrow the query.
4. For a large report, fetch the specific finding from `findings.json` by ID instead of reading the whole file. Its evidence is associated with devices/driver packages where the data allows it.
5. Read only the relevant procedural reference. Reuse an existing valid snapshot; do not recollect because a new chat turn arrived.
6. After a repair, use `compare`; inspect changes rather than rereading both inventories. New captured events are limited to the time between the two snapshots.

Important facts, missing-evidence flags and a synthetic marker must survive compression. `truncated: true` requires targeted follow-up when omitted evidence might change the answer. Saving context must not mean discarding contrary evidence or ending diagnosis prematurely.

`manifest.json` records serialized snapshot characters, summary characters and their ratio. These are payload measurements. They are not token counts: tokenizer, language, prompt/cache use, reference loading, agent reasoning and follow-up queries affect actual billing.

```powershell
python scripts/benchmark-context.py
python scripts/benchmark-context.py --lang zh --out work\context-benchmark-zh.json
```

The synthetic benchmark compares dumping a full fixture with one focused handoff. It does not compare accuracy or cost against an actual plain-Codex session. A fair real evaluation needs the same incident artifacts, model/settings, allowed tools and outcome rubric for both arms, recording total input/output tokens, elapsed time, number of evidence retrievals, unsupported conclusions and diagnostic usefulness.
