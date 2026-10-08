# Qualified statistics

`vascuquest.stats` is a strict qualified core, not a generic wrapper around every SciPy function. Every canonical operation consumes VascuQuest `ScientificResult` objects and retains dataset/cohort identity.

## Canonical methods

- descriptive statistics;
- empirical quantiles and designed-cohort exceedance fractions;
- percentile bootstrap mean confidence interval with explicit seed;
- paired t test / Wilcoxon signed-rank;
- Welch independent t test / Mann-Whitney U;
- deterministic paired or independent permutation mean-difference tests;
- Shapiro-Wilk and D'Agostino-Pearson normality diagnostics;
- Levene/Brown-Forsythe variance diagnostics;
- Pearson / Spearman correlation;
- partial correlation with explicit aligned controls;
- ordinary least-squares regression;
- standardized regression for sensitivity/effect-modifier ranking;
- Huber IRLS robust regression;
- one-way ANOVA and Kruskal-Wallis;
- ANCOVA group-effect test with aligned covariates;
- Benjamini-Hochberg false-discovery-rate adjustment.

## Alignment rules

Paired comparisons, correlations, partial correlations, ANCOVA and regression operate over canonical subject identity. They refuse mismatched deterministic order instead of treating row numbers as biological correspondence.

## Interpretation boundary

Statistical significance over PWDB or generated disease cohorts describes a designed virtual population. Empirical cohort fractions are not epidemiological prevalence or patient risk.
