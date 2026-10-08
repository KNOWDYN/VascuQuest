# Qualified statistics and probability in VascuQuest 1.0

## 1. Purpose

`vascuquest.stats` provides a **strict qualified statistical core** for native VascuQuest scientific results. It is not intended to replace SciPy, statsmodels, R, or a general-purpose statistics environment.

The namespace exists so statistical operations can preserve VascuQuest-specific scientific context:

- exact dataset identity;
- canonical subject IDs;
- deterministic cohort membership/order;
- healthy↔disease pairing;
- quantity and units;
- evidence class;
- provenance;
- designed-population interpretation.

## 2. Core rule

A statistical operation must not reduce a VascuQuest result to an anonymous vector before deciding whether the comparison is scientifically admissible.

In particular:

- paired analyses align by canonical subject ID, not row position;
- independent cohorts remain independent;
- different dataset identities are not silently mixed;
- designed PWDB cohorts are not treated as epidemiological random samples;
- modelled disease responses remain modelled after statistical analysis.

## 3. Input contract

The canonical input is a `ScientificResult` whose values can be interpreted as a finite scalar/vector sample for the selected method.

The analysis layer validates/extracts values while preserving scientific metadata.

For file-based CLI workflows, the input boundary is the native VascuQuest portable JSON result format. This ensures the method receives subject/cohort identity and scientific metadata rather than only numbers.

External arrays must first enter through the controlled `vascuquest.analysis` wrapping contract. Anonymous raw arrays do not automatically become canonical VascuQuest research inputs.

## 4. Output contract

Statistical functions return VascuQuest `ScientificResult` objects with:

- derived statistical quantity identity;
- output value/mapping;
- `DERIVED` evidence;
- stable method ID;
- input/provenance context;
- warnings where interpretation requires qualification.

A statistical result does not change the evidence class of the underlying physiological quantity. For example, a p-value computed from `MODELLED` disease outputs is a derived statistic about modelled outputs; it is not clinical evidence.

## 5. Descriptive statistics

### `describe(result)`

Produces a descriptive summary of finite values. The implementation reports the sample size and conventional distribution summaries needed for research inspection.

Use it for:

- individual/cohort endpoint summaries;
- checking scale/range before inference;
- documenting cohort/model-response distributions.

Do not interpret counts or distribution proportions as human prevalence unless an externally validated population weighting/sampling model is supplied.

### `empirical_quantiles(result)`

Returns canonical empirical quantiles over the represented virtual observations.

### `exceedance_probability(result, threshold, inclusive=True)`

Computes the empirical fraction of represented observations meeting/exceeding a declared threshold.

Interpretation is deliberately constrained:

> This is an empirical probability/fraction within the represented designed virtual population. It is not a patient risk estimate or epidemiological event probability.

## 6. Confidence intervals and bootstrap

### `bootstrap_mean_ci(...)`

Provides a seeded bootstrap confidence interval for the arithmetic mean.

Required parameters include an explicit confidence level, number of resamples, and seed/random state. Repeated calls with identical inputs/parameters/seed are expected to be reproducible within numerical precision.

The bootstrap quantifies uncertainty under the empirical resampling procedure. It does not make PWDB an epidemiological sample.

CLI:

```text
vascuquest stats bootstrap result.json --confidence 0.95 --resamples 2000 --seed 0
```

## 7. Paired comparisons

### `paired_compare(a, b, method=...)`

Intended for two results representing the same canonical virtual subjects under two conditions, such as healthy and matched disease counterfactuals.

Hard condition:

- canonical subject identities and alignment must match.

The method must not infer pairing merely because two vectors have the same length.

Typical interpretation:

> paired counterfactual model response

not:

> clinical treatment effect

CLI:

```text
vascuquest stats compare healthy.json disease.json --paired
```

## 8. Independent comparisons

### `independent_compare(a, b, method=...)`

Used for scientifically independent virtual cohorts/selections.

The default comparison method in the CLI is Welch-style unequal-variance comparison when `--paired` is not supplied.

Independence is a property of study design/selection, not merely different file names.

## 9. Permutation inference

### `permutation_mean_difference(a, b, paired=False, n_resamples=..., seed=...)`

Provides a deterministic seeded permutation test for a two-sided mean-difference hypothesis under the selected paired/independent design.

The permutation mechanism respects the declared design. Pairing is not inferred from row order.

CLI:

```text
vascuquest stats permutation a.json b.json --paired --resamples 5000 --seed 0
```

## 10. Effect sizes

Qualified comparison functions report effect-size information where implemented by the method contract.

Effect sizes describe the magnitude of differences within the analyzed virtual data. They do not independently establish clinical importance.

## 11. Normality diagnostics

### `normality_test(result, method=...)`

Provides qualified normality diagnostics such as Shapiro-type testing where supported.

A normality p-value is not a binary truth statement that data are/are not normal. It should be interpreted alongside distribution shape, sample size, and analysis design.

CLI:

```text
vascuquest stats normality result.json --method shapiro
```

## 12. Variance diagnostics

### `variance_test(a, b, center="median")`

Implements a Levene/Brown-Forsythe-style variance homogeneity diagnostic according to the selected center.

CLI:

```text
vascuquest stats variance a.json b.json --center median
```

## 13. Correlation

### `correlate(x, y, method="pearson")`

Requires aligned cohort observations. Correlation does not create subject alignment; subject alignment is a prerequisite.

### `partial_correlation(x, y, controls, method="pearson")`

Computes correlation after linear residualization against one or more aligned control variables.

CLI examples:

```text
vascuquest stats correlate x.json y.json --method pearson
vascuquest stats partial-correlate x.json y.json age.json mbp.json
```

Interpretation rule:

> correlation/partial correlation describe association in the represented virtual design; they are not automatically causal effects.

## 14. Linear regression

### `linear_regression(response, predictors, standardized=False)`

Fits an ordinary least-squares model over an aligned cohort.

The implementation records coefficients and model diagnostics in the returned scientific result.

Hard safeguards include:

- aligned observations;
- finite numeric input;
- explicit predictor list;
- rejection of rank-deficient designs.

CLI:

```text
vascuquest stats regress response.json x1.json x2.json
```

Standardized coefficients can be requested when supported by the public method.

## 15. Robust regression

### `robust_regression(response, predictors, huber_delta=1.345)`

Uses Huber-type iteratively reweighted least squares for a bounded robust alternative to OLS.

CLI:

```text
vascuquest stats robust-regress response.json x1.json x2.json --huber-delta 1.345
```

Robustness to some outliers does not mean immunity to model misspecification or confounding.

## 16. ANOVA and ANCOVA

### `one_way_anova(...)`

Supports qualified one-way group comparison where the group design is explicit.

### `ancova(...)`

Supports adjusted group comparison with declared covariates under the implemented linear-model assumptions.

These methods operate on the represented virtual observations; they do not confer epidemiological sampling assumptions.

## 17. Multiple-comparison correction

### `benjamini_hochberg(...)`
### `adjust_pvalues(...)`

Provide deterministic multiplicity adjustment over an explicit family of p-values.

The family of hypotheses is a study-design choice. A correction function cannot determine automatically which hypotheses belong to the same inferential family.

## 18. Individual vs cohort analysis

Statistics usually require multiple observations. A single-subject scalar result is still a valid VascuQuest result but is not a cohort sample.

For single-subject research, statistics may instead operate over explicitly defined repeated observations/dimensions only when the scientific meaning of those observations supports the method. Time samples from one waveform must not automatically be treated as independent subjects.

## 19. Healthy/disease response studies

For a disease-response study:

```text
healthy canonical subjects
        ↓ same identities
MODELLED disease population
        ↓
paired response endpoints
        ↓
vascuquest.stats paired analysis
```

The resulting inference concerns the **modelled counterfactual response of the virtual subjects**.

## 20. Reproducibility

Randomized methods expose deterministic seed controls.

A reproducible statistical analysis must record:

- input result identities/files;
- method ID;
- method parameters;
- seed/resample count where applicable;
- cohort/subject alignment;
- warnings/assumption diagnostics;
- software version.

## 21. CLI command map

```text
vascuquest stats describe
vascuquest stats bootstrap
vascuquest stats compare
vascuquest stats correlate
vascuquest stats partial-correlate
vascuquest stats regress
vascuquest stats robust-regress
vascuquest stats normality
vascuquest stats variance
vascuquest stats permutation
vascuquest stats quantiles
vascuquest stats exceedance
```

The Python namespace additionally exposes qualified methods such as ANOVA/ANCOVA and p-value adjustment even where a dedicated CLI convenience command is not yet present.

## 22. Optional dependency

The qualified research stack uses the `research` optional extra where SciPy functionality is required:

```text
pip install "vascuquest[research]"
```

Missing required optional dependencies must fail explicitly; VascuQuest must not silently substitute a different statistical method.

## 23. Non-claims

`vascuquest.stats` does not claim:

- that PWDB is an epidemiological sample;
- that p-values from modelled populations are clinical evidence;
- automatic causal inference;
- automatic satisfaction of method assumptions;
- clinical risk/prognostic probabilities;
- unrestricted coverage of every statistical technique researchers may use.

The v1 philosophy is **qualified core + explicit extensibility**, not maximum function count.
