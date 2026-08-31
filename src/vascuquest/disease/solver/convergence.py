"""Cycle-to-cycle convergence metrics for the native 1-D solver."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np


def periodicity_error(
    start: Mapping[str, np.ndarray],
    end: Mapping[str, np.ndarray],
) -> float:
    """Return a scale-normalised L2 state difference across the whole network."""
    if set(start) != set(end):
        raise ValueError("periodicity states must contain identical segment IDs")
    numerator = 0.0
    denominator = 0.0
    for segment_id in sorted(start):
        first = np.asarray(start[segment_id], dtype=float)
        second = np.asarray(end[segment_id], dtype=float)
        if first.shape != second.shape:
            raise ValueError("periodicity state shapes do not match")
        diff = second - first
        numerator += float(np.sum(diff * diff))
        denominator += float(np.sum(first * first))
    return float(np.sqrt(numerator / max(denominator, 1e-30)))


__all__ = ["periodicity_error"]
