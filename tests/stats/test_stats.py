import numpy as np
import pytest
from vascuquest.domain import Cohort, DatasetIdentity, EvidenceClass, QuantityDefinition, ScientificResult
from vascuquest.stats import correlate, describe, linear_regression, paired_compare

pytest.importorskip("scipy")


def _cohort_result(values, name="x"):
    identity = DatasetIdentity("PWDB", "3275625", "10.5281/zenodo.3275625", "v1")
    ids = tuple(str(i + 1) for i in range(len(values)))
    cohort = Cohort(identity, ids, "test_order")
    quantity = QuantityDefinition(name, name, name, "numeric", "v1", "dimensionless", "1")
    return ScientificResult(identity, quantity, np.asarray(values, dtype=float), f"prov:{name}", cohort=cohort, evidence=EvidenceClass.SOURCE)


def test_paired_statistics_preserve_subject_alignment():
    x = _cohort_result(np.arange(1.0, 21.0), "x")
    y = _cohort_result(np.arange(1.0, 21.0) * 2.0 + 3.0, "y")
    summary = describe(x)
    comparison = paired_compare(x, y)
    corr = correlate(x, y)
    regression = linear_regression(y, [x])
    assert summary.values["n"] == 20
    assert comparison.values["pvalue"] < 1e-8
    assert corr.values["coefficient"] == pytest.approx(1.0)
    assert regression.values["r2"] == pytest.approx(1.0)
    assert comparison.cohort.canonical_subject_ids == x.cohort.canonical_subject_ids
