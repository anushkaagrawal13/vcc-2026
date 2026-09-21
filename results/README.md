# Experiment record

Track metrics tables, small plots, configs and provenance in git; keep matrices in
gitignored `data/`. Never label synthetic tests or local schema checks as a
challenge score.

| Experiment | Data | Status | Official score |
|---|---|---|---|
| Synthetic schema fixture | 3 genes, 2 targets, A/B/C, 4 cells each | Official CLI packaging test passed | Not applicable |
| `000_zero_delta` | Official `vcc2026-val-1` controls | Stopped: local disk too small; incomplete output removed | Not submitted |
| K562 → RPE1 ridge | Public Replogle | Deferred until Session 1 completes | Not applicable |

For each real experiment commit its config, seed, git revision, input hashes,
package/scorer versions, raw/scaled metric distinction, per-context metrics,
cohort coverage, runtime and memory where measured. Official results also require
entry ID, partition, panel and anchor bundle identifiers.

Ten synthetic tests passed. Actual controls and schema were inspected, but the
full prediction was not completed, officially packaged or submitted. Generation
reached more than 4.5 GiB while free space fell below 1 GiB on an 8 GiB RAM Mac.
See `000_zero_delta_status.json`. A conservative disk preflight now prevents this
failure before starting another full run. Keep Session 2 deferred until this gate
is completed on a suitable machine.
