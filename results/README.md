# Experiment record

Track metrics tables, small plots, configs and provenance in git; keep matrices in
gitignored `data/`. Never label synthetic tests or local schema checks as a
challenge score.

| Experiment | Data | Status | Official score |
|---|---|---|---|
| Synthetic schema fixture | 3 genes, 2 targets, A/B/C, 4 cells each | Official CLI packaging test passed | Not applicable |
| `000_zero_delta` | Official `vcc2026-val-1` controls | Generation started; see JSON report when complete | Not yet recorded |
| K562 → RPE1 ridge | Public Replogle | Deferred until Session 1 completes | Not applicable |

For each real experiment commit its config, seed, git revision, input hashes,
package/scorer versions, raw/scaled metric distinction, per-context metrics,
cohort coverage, runtime and memory where measured. Official results also require
entry ID, partition, panel and anchor bundle identifiers.
