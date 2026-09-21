"""Session 2/3 boundary; do not fit features using held-out perturbation outcomes.

Start with target-gene basal expression from target-line controls. Then add
target-gene mean expression across TRAINING lines and GO/STRING neighbor deltas
fit on TRAINING lines only. Version gene identifiers, graph release and units.
Target-line control profiles are allowed covariates; its perturbations are labels.
Norman 2019 is excluded (CRISPRa); adding it requires a separate task/assay model.
"""
