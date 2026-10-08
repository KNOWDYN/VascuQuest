"""Multiple-testing correction."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
from vascuquest.analysis import make_result
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import ScientificResult
from ._shared import _finite_vector

def benjamini_hochberg(pvalues: Sequence[float]) -> np.ndarray:
    """Return Benjamini-Hochberg adjusted p-values for an explicit p-value vector."""
    p = np.asarray(tuple(pvalues), dtype=float)
    if p.ndim != 1 or p.size == 0 or not np.all(np.isfinite(p)) or np.any((p < 0) | (p > 1)):
        raise ValueError("pvalues must be a non-empty finite vector in [0, 1]")
    order = np.argsort(p)
    ranked = p[order]
    adjusted_ranked = np.minimum.accumulate((ranked * p.size / np.arange(1, p.size + 1))[::-1])[::-1]
    adjusted = np.empty_like(adjusted_ranked)
    adjusted[order] = np.minimum(adjusted_ranked, 1.0)
    return adjusted

def adjust_pvalues(result: ScientificResult) -> ScientificResult:
    p = _finite_vector(result, 1)
    adjusted = benjamini_hochberg(p)
    return make_result(
        result, canonical_name=f"stats.bh_adjusted.{result.quantity.canonical_name}", label="Benjamini-Hochberg adjusted p-values",
        description="False-discovery-rate adjustment of an explicit VascuQuest p-value vector.", values=adjusted,
        method_id="vascuquest:stats:benjamini-hochberg-v1", evidence=EvidenceClass.DERIVED,
        canonical_unit="1", physical_dimension="dimensionless", value_kind="series",
        dimensions=result.dimensions, coordinates=result.coordinates,
    )
