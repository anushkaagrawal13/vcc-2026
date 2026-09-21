# Data and validation plan

| Dataset | Assay | Decision |
|---|---|---|
| Replogle 2022 K562 | CRISPRi | First training line |
| Replogle 2022 RPE1 | CRISPRi | Held-out transfer evaluation; perturbation labels never used for tuning |
| Adamson 2016 | CRISPRi | Session 3, audit condition/guide matching before pooling |
| Norman 2019 | CRISPRa | Excluded; activation is a separate task, not a signed copy of CRISPRi |

Replogle's official [dataset record](https://plus.figshare.com/articles/dataset/_Mapping_information-rich_genotype-phenotype_landscapes_with_genome-scale_Perturb-seq_Replogle_et_al_2022_processed_Perturb-seq_datasets/20029387)
is linked by the challenge. Smaller K562 file ID 35773219 and RPE1 35775606 are
the initial candidates; inspect their actual metadata/count layers before writing
an adapter. Do not assume processed matrices contain raw counts in X.

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
