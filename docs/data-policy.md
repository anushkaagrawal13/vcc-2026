# Data and validation plan

| Dataset | Assay | Decision |
|---|---|---|
| Replogle 2022 K562 | CRISPRi | First training line |
| Replogle 2022 RPE1 | CRISPRi | Held-out transfer evaluation; perturbation labels never used for tuning |
| Adamson 2016 | CRISPRi | Session 3, audit condition/guide matching before pooling |
| Norman 2019 | CRISPRa | Excluded; activation is a separate task, not a signed copy of CRISPRi |

Replogle's official [dataset record](https://plus.figshare.com/articles/dataset/_Mapping_information-rich_genotype-phenotype_landscapes_with_genome-scale_Perturb-seq_Replogle_et_al_2022_processed_Perturb-seq_datasets/20029387)
is linked by the challenge. Smaller K562 file ID 35773219 and RPE1 35775606 are
the selected sources for experiment 001. The adapter checks the actual metadata
and verifies that every value in X is a nonnegative integer count.

For each source record accession, URL, file checksum, license, assay, cell line,
condition, batch, control labels, target/guide mapping, gene identifiers and count
layer. Raw/processed files stay out of git. Keep provenance and QC summaries in
results; do not commit raw cell metadata.

Pseudobulk groups must have matched non-targeting controls within the same dataset,
line, assay and experimental stratum. Retain guide support and cell counts. Decide
normalization explicitly before taking means/deltas; do not silently mix raw-count,
CPM, log1p or fold-change targets. Preserve the cell-level data for DE evaluation.

RPE1 controls can supply basal covariates. RPE1 perturbation outcomes cannot supply
neighbors' deltas, training means, feature selection, imputation, scaler statistics,
early stopping or alpha selection. Hyperparameter tuning belongs inside K562.
Report panel overlap: shared-target cross-line prediction and unseen-target
cross-line prediction answer different questions.

Count generation is its own model component. Mean deltas do not identify a
single-cell distribution; test how predicted counts, library sizes and dispersion
affect all six rubric metrics. A replicated mean or simple multinomial can give
miscalibrated DE even when its mean prediction is good.

## Experiment 001: Replogle pseudobulk

Pinned in `config/001_replogle_pseudobulk.yaml`: original Figshare raw single-cell
files, publisher MD5s, sizes and CC BY 4.0 attribution. K562 essential has
310,385 cells × 8,563 retained genes; RPE1 has 247,914 × 8,749. Both have dense
float32 X, with integer raw counts verified on every processed chunk. The
publisher already filtered the cell/gene axes; this run adds no cell filtering.

Downloads are losslessly gzip-compressed as they arrive to avoid staging 19.4 GB
of dense matrices. Receipts hash the original bytes and the compressed archive.
The original single cells remain available by decompressing these archives for
future DE evaluation. The adapter reads old AnnData categorical references and
streams the gzip-backed HDF5 matrix rather than loading it into memory. A pinned
`indexed-gzip` reader builds seek checkpoints once, avoiding full decompression
on every HDF5 metadata seek.

For each target, the normalized target is the mean of
`log1p(10000 * count / obs.UMI_count)` over its cells, minus a weighted mean of
non-targeting controls. Each gem group's control mean gets the same weight as
that group's fraction of target cells. Controls never cross dataset, cell line,
assay, or gem group. At least 10 controls per gem group are required; otherwise
the run fails. The total UMI metadata includes genes excluded from the retained
axis; the denominator is deliberately not the sum across retained genes.
Raw-count means and matched deltas are also retained as diagnostics.

Output is one tidy Parquet row per `(dataset, line, assay_type, target_gene_id,
target_gene, output_gene_id)`, with both scales, target cell count, guide-pair
support and matched-gem count. Separate Parquets contain control-only baseline
expression and target-by-gem matching counts. Symbols sharing an Ensembl ID are
preserved rather than silently merged. RPE1 targets NEDD8-MDP1, PRSS50, and
RBM14-RBM4 have missing source IDs: preserve them as `UNMAPPED:<symbol>`,
record their cell counts in QC, and exclude them from Ensembl-ID overlap cohorts.
No speculative gene mapping or cell deletion is performed. K562 and RPE1 files remain separate;
RPE1 outcomes are solely held-out evaluation labels. No modeling or tuning is
performed by this aggregation. These pseudobulks alone do not reproduce the
single-cell DE scoring rubric.

For local execution, run `make download-public` then `make pseudobulk`. The
CloudShell run instead uses `scripts/run-public-checkpointed.py` under an outer
two-hour timeout, with one BLAS thread. It backs up each source immediately after
checksum validation and each line immediately after aggregation. Every object
is read back from private encrypted S3 and checked by SHA-256. Logs and run state
are persisted in the CloudShell home directory and S3 during execution.

```bash
timeout 7200 python3 scripts/run-public-checkpointed.py \
  --bucket vcc-2026-artifacts-706098201643-us-east-2 \
  --prefix public/replogle_2022/001_replogle_pseudobulk
```

This supervisor uses system Python with boto3 for AWS access and `.venv/bin/python`
for the pinned scientific environment. Use `--resume` to reuse existing local artifacts whose hashes match the saved
checkpoint manifest. This is for recovery of this same experiment, not reuse after
changing its scientific configuration. The run records original and resume commits.
An interrupted run does not automatically restore remote checkpoints; inspect the
S3 `run-state.json` before restarting. Restore verified artifacts and the manifest
to `~/.vcc-cloud/public-run-state.json` first if local scratch has been lost. The
older all-at-end export script is not the checkpointed execution path.

To restore the processed tables in an authenticated AWS environment:

```bash
aws s3 sync \
  s3://vcc-2026-artifacts-706098201643-us-east-2/public/replogle_2022/001_replogle_pseudobulk/data/processed/001_replogle_pseudobulk/ \
  data/processed/001_replogle_pseudobulk/ --region us-east-2
```

Compare restored file SHA-256 hashes with the committed checkpoint manifest
before training. Raw archives remain backed up separately for later single-cell
DE evaluation. CloudShell does not incur EC2 compute charges; retained S3 objects
continue to use billable storage.
