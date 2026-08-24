"""Scientific evidence classification for VascuQuest results.

Evidence class records how a scientific quantity or result came into being.
It is deliberately separate from validity, admissibility, plausibility, and
quality-control state.
"""

from __future__ import annotations

from enum import Enum


class EvidenceClass(str, Enum):
    """Scientific status of a VascuQuest quantity or result."""

    SOURCE = "SOURCE"
    RECONSTRUCTED = "RECONSTRUCTED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    MODELLED = "MODELLED"


__all__ = ["EvidenceClass"]
