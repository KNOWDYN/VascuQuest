"""Small, explicit unit conversions used by qualified v1 research methods."""
from __future__ import annotations

import numpy as np
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import UnitError

_PRESSURE_TO_PA = {"Pa": 1.0, "kPa": 1000.0, "mmHg": 133.322387415}
_AREA_TO_M2 = {"m^2": 1.0, "m2": 1.0, "cm^2": 1e-4, "cm2": 1e-4, "mm^2": 1e-6, "mm2": 1e-6}
_FLOW_TO_M3S = {"m^3/s": 1.0, "m3/s": 1.0, "L/s": 1e-3, "mL/s": 1e-6}
_VELOCITY_TO_MS = {"m/s": 1.0, "cm/s": 1e-2, "mm/s": 1e-3}


def _unit(result: ScientificResult) -> str | None:
    return result.canonical_unit or result.source_unit


def _convert(result: ScientificResult, table: dict[str, float], kind: str) -> np.ndarray:
    unit = _unit(result)
    if unit not in table:
        raise UnitError(f"{kind} operation requires one of {sorted(table)!r}; received {unit!r}")
    values = np.asarray(result.values, dtype=float) * table[unit]
    if not np.all(np.isfinite(values)):
        raise UnitError(f"{kind} values must be finite")
    return values


def pressure_pa(result: ScientificResult) -> np.ndarray:
    return _convert(result, _PRESSURE_TO_PA, "pressure")


def area_m2(result: ScientificResult) -> np.ndarray:
    return _convert(result, _AREA_TO_M2, "area")


def flow_m3s(result: ScientificResult) -> np.ndarray:
    return _convert(result, _FLOW_TO_M3S, "flow")


def velocity_ms(result: ScientificResult) -> np.ndarray:
    return _convert(result, _VELOCITY_TO_MS, "velocity")


__all__ = ["area_m2", "flow_m3s", "pressure_pa", "velocity_ms"]
