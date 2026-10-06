# Experiment record

Track metrics tables, small plots, configs and provenance in git; keep matrices in
gitignored `data/`. Never label synthetic tests or local schema checks as a
challenge score.

| Experiment | Data | Status | Official score |
|---|---|---|---|
| Synthetic schema fixture | 3 genes, 2 targets, A/B/C, 4 cells each | Official CLI packaging test passed | Not applicable |
| `000_zero_delta` | Official `vcc2026-val-1` controls | Submitted as `Axby4yc5z8rw49HHPjz7`; compute terminated and working disk deleted | Pending (launching) |
| K562 → RPE1 ridge | Public Replogle | Deferred until Session 1 completes | Not applicable |

For each real experiment commit its config, seed, git revision, input hashes,
package/scorer versions, raw/scaled metric distinction, per-context metrics,
cohort coverage, runtime and memory where measured. Official results also require
entry ID, partition, panel and anchor bundle identifiers.

On October 6, all 14 Linux rehearsal tests passed and the full EC2 pipeline
completed. It generated 360,000 cells across 18,533 genes, passed official CLI
validation, and produced a 3.86-GB `.vcc` package. The prediction SHA-256 exactly
matches the earlier Kaggle result. All nine exported files were verified against
their source SHA-256 hashes. See `first_cloud_batch_2026-10-06.json` and
`000_zero_delta_batch.json`. Upload succeeded with server MD5 verification;
`000_zero_delta_submission.json` records the entry. Official scoring is pending.
EC2 termination and deletion of the attached 200 GiB disk were verified; the
private S3 backup is retained.

`000_zero_delta_status.json` records an earlier local disk failure, and
`000_zero_delta_validation.json` records the earlier Kaggle generation run;
these are historical evidence rather than the current batch status.

The verified preflight estimates **18.8 GiB free disk for generation alone**,
conservatively allowing for uncompressed sparse storage. Packaging needs additional
scratch and several copies of that matrix in RAM. The measured packaging
estimate was 57.0 GiB RAM and 26.1 GiB scratch. The successful host used 128 GiB
RAM and 200 GiB gp3; the full-panel runner requires at least 96 GiB effective RAM
and 100 GiB free disk before starting.
