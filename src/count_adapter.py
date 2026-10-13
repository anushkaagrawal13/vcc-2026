"""Experimental control-profile transport; always generate fresh multinomial counts.

Mean log1p deltas do not identify a single-cell distribution. This fixed heuristic
shifts empirical control log profiles, clips at zero and resamples new counts.
It is NOT an exact inversion of pseudobulk means; report achieved delta error.
The outside-panel bucket preserves the distinction between total UMI and panel sum.
"""
import numpy as np


class ControlTransport:
    def __init__(self, counts, libraries, normalization=10000):
        x = np.asarray(counts, dtype=np.float64)
        depth = np.asarray(libraries, dtype=np.float64)
        if (x.ndim != 2 or depth.shape != (len(x),) or len(x) < 2
                or not np.isfinite(x).all() or not np.isfinite(depth).all()
                or np.any(x < 0) or np.any(x != np.floor(x))
                or np.any(depth != np.floor(depth)) or np.any(depth <= 0)
                or np.any(depth > 1000000) or np.any(x.sum(1) > depth)):
            raise ValueError('Invalid control counts or total libraries')
        if not np.isfinite(normalization) or normalization <= 0:
            raise ValueError('Invalid normalization')
        self.depth = depth.astype(np.int64)
        self.norm = normalization
        self.log_profiles = np.log1p(x * normalization / depth[:, None])
        self.outside = (depth - x.sum(1)) * normalization / depth
        self.mean_log = self.log_profiles.mean(0)

    def generate(self, delta, cells, seed, donor_indices=None):
        delta = np.asarray(delta, dtype=np.float64)
        if delta.shape != self.mean_log.shape or not np.isfinite(delta).all():
            raise ValueError('Delta axis or values invalid')
        if not isinstance(cells, int) or cells < 1:
            raise ValueError('Invalid cell count')
        rng = np.random.default_rng(seed)
        if donor_indices is None:
            donors = rng.integers(len(self.depth), size=cells)
        else:
            donors = np.asarray(donor_indices)
            if (donors.shape != (cells,) or not np.issubdtype(donors.dtype, np.integer)
                    or np.any(donors < 0) or np.any(donors >= len(self.depth))):
                raise ValueError('Invalid donor indices')
        output = np.empty((cells, len(delta)), dtype=np.int32)
        clipped = 0
        for i, donor in enumerate(donors):
            shifted = self.log_profiles[donor] + delta
            clipped += int((shifted < 0).sum())
            if shifted.max() > 20:
                raise ValueError('Unbounded log intensity')
            rates = np.r_[np.expm1(np.maximum(shifted, 0)), self.outside[donor]]
            if rates.sum() <= 0:
                raise ValueError('All intensities vanished')
            output[i] = rng.multinomial(int(self.depth[donor]), rates/rates.sum())[:-1]
        depth = self.depth[donors].copy()
        achieved = np.log1p(output * self.norm / depth[:, None]).mean(0) - self.mean_log
        qc = dict(requested_delta_rmse=float(np.sqrt(np.mean((achieved-delta)**2))),
                  negative_shift_fraction=clipped/(cells*len(delta)),
                  maximum_panel_library=int(output.sum(1).max()),
                  minimum_panel_library=int(output.sum(1).min()),
                  all_counts_nonnegative_integer=True)
        return output, depth, qc


class MeanCalibratedTransport(ControlTransport):
    """Correct generated mean log expression using controls and requested delta only.

    Fixed Monte Carlo seeds stabilize updates; generation uses independent seeds.
    Mean correction does not promise correct dispersion or differential expression.
    """
    def calibrate(self, delta, iterations, calibration_cells, seed, donor_indices=None,
                  learning_rate=0.5, maximum_step=0.25, maximum_offset=4.0):
        delta = np.asarray(delta, dtype=np.float64)
        if delta.shape != self.mean_log.shape or not np.isfinite(delta).all():
            raise ValueError('Invalid requested delta')
        if (not isinstance(iterations, int) or iterations < 1
                or not 0 < learning_rate <= 1 or not 0 < maximum_step <= maximum_offset
                or not np.isfinite(maximum_offset)):
            raise ValueError('Invalid calibration parameters')
        desired = np.maximum(self.mean_log + delta, 0)
        offset = delta.copy()
        if np.any(np.abs(offset) > maximum_offset):
            raise ValueError('Requested offset exceeds bound')
        history = []
        for step in range(iterations + 1):
            counts, depth, _ = super().generate(offset, calibration_cells, seed, donor_indices)
            observed = np.log1p(counts * self.norm / depth[:, None]).mean(0)
            error = desired - observed
            history.append(float(np.sqrt(np.mean(error**2))))
            if step < iterations:
                offset = np.clip(offset + np.clip(learning_rate * error, -maximum_step, maximum_step),
                                 -maximum_offset, maximum_offset)
        return dict(offset=offset, requested_delta=delta.copy(),
                    qc=dict(iterations=iterations, calibration_seed=seed,
                            calibration_cells=calibration_cells, mean_log_rmse_history=history,
                            impossible_negative_mean_genes=int((self.mean_log + delta < 0).sum()),
                            offset_bound_genes=int((np.abs(offset) >= maximum_offset).sum())))

    def generate_calibrated(self, calibration, cells, seed, donor_indices=None):
        counts, depth, qc = super().generate(calibration['offset'], cells, seed, donor_indices)
        achieved = np.log1p(counts * self.norm / depth[:, None]).mean(0) - self.mean_log
        qc['requested_delta_rmse'] = float(np.sqrt(np.mean((achieved-calibration['requested_delta'])**2)))
        return counts, depth, qc
