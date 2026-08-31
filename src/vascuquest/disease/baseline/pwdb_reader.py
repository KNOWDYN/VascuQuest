"""Private bounded reader for PWDB model-configuration inputs.

This reader deliberately lives inside the Virtual Disease subsystem. It does
not widen the canonical PWDB backend or expose implementation-only simulation
parameters through the public VascuQuest schema.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
import re

from vascuquest.errors import IntegrityError, SchemaError, SelectionError

from .model import MMHG_TO_PA

_HEADER_UNIT_RE = re.compile(r"\s*\[[^\]]*\]\s*$")
_REQUIRED = {
    "subject_number",
    "age",
    "hr",
    "sv",
    "pft",
    "rfv",
    "dbp",
    "mbp",
    "viscosity",
    "alpha",
    "p_out",
    "density",
    "lvet",
    "pvr",
    "b0",
    "b1",
    "k1",
    "k2",
    "k3",
}


def _normal_header(text: str) -> str:
    value = _HEADER_UNIT_RE.sub("", text.replace("\ufeff", "").strip()).lower()
    value = value.replace("-", "_").replace(" ", "_")
    return re.sub(r"_+", "_", value)


def _finite(raw: str, field_name: str) -> float:
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise SchemaError(f"PWDB model configuration {field_name!r} must be numeric") from exc
    if not math.isfinite(value):
        raise SchemaError(f"PWDB model configuration {field_name!r} must be finite")
    return value


def _canonical_subject(raw: str) -> str:
    number = _finite(raw, "subject_number")
    if number < 1 or not number.is_integer():
        raise SchemaError("PWDB subject number must be a positive integer")
    return str(int(number))


@dataclass(frozen=True, slots=True)
class PWDBModelConfiguration:
    canonical_subject_id: str
    age_years: int
    heart_rate_bpm: float
    stroke_volume_ml: float
    peak_flow_time_s: float
    reverse_flow_volume_ml: float
    lvet_s: float
    diastolic_pressure_pa: float
    mean_pressure_pa: float
    outlet_pressure_pa: float
    blood_density_kg_per_m3: float
    blood_viscosity_pa_s: float
    momentum_correction_alpha: float
    systemic_pvr_pa_s_per_m3: float
    wall_gamma_b0_g_per_s: float
    wall_gamma_b1_g_cm_per_s: float
    stiffness_k1_g_per_s2_per_cm: float
    stiffness_k2_per_cm: float
    stiffness_k3_g_per_s2_per_cm: float
    source_member: str


class PWDBModelConfigurationReader:
    """Read one subject row from the checksum-verified model-config CSV."""

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise TypeError("path must be a pathlib.Path")
        self._path = path

    def read_subject(self, subject_id: str) -> PWDBModelConfiguration:
        if not isinstance(subject_id, str) or not subject_id or subject_id != subject_id.strip():
            raise SelectionError("subject_id must be a non-empty canonical subject identifier")
        try:
            with self._path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, skipinitialspace=True)
                if reader.fieldnames is None:
                    raise SchemaError("PWDB model configuration CSV has no header")
                normalized = {_normal_header(name): name for name in reader.fieldnames}
                aliases = {
                    "subject_number": ("subject_number",),
                    "age": ("age",),
                    "hr": ("hr",),
                    "sv": ("sv",),
                    "pft": ("pft", "t_pf"),
                    "rfv": ("rfv", "reg_vol"),
                    "dbp": ("dbp",),
                    "mbp": ("mbp",),
                    "viscosity": ("viscosity", "mu"),
                    "alpha": ("alpha",),
                    "p_out": ("p_out",),
                    "density": ("density", "rho"),
                    "lvet": ("lvet",),
                    "pvr": ("pvr",),
                    "b0": ("b0", "gamma_b0"),
                    "b1": ("b1", "gamma_b1"),
                    "k1": ("k1",),
                    "k2": ("k2",),
                    "k3": ("k3",),
                }
                resolved: dict[str, str] = {}
                for target, choices in aliases.items():
                    matches = [normalized[choice] for choice in choices if choice in normalized]
                    if len(matches) != 1:
                        raise SchemaError(f"PWDB model configuration lacks unambiguous field {target!r}")
                    resolved[target] = matches[0]
                if set(resolved) != _REQUIRED:
                    raise SchemaError("PWDB model configuration field contract is incomplete")

                for row in reader:
                    canonical = _canonical_subject(row[resolved["subject_number"]])
                    if canonical != subject_id:
                        continue
                    age = _finite(row[resolved["age"]], "age")
                    if not age.is_integer() or age < 0:
                        raise SchemaError("PWDB model age must be a non-negative integer")
                    return PWDBModelConfiguration(
                        canonical_subject_id=canonical,
                        age_years=int(age),
                        heart_rate_bpm=_finite(row[resolved["hr"]], "hr"),
                        stroke_volume_ml=_finite(row[resolved["sv"]], "sv"),
                        peak_flow_time_s=_finite(row[resolved["pft"]], "pft") / 1000.0,
                        reverse_flow_volume_ml=_finite(row[resolved["rfv"]], "rfv"),
                        lvet_s=_finite(row[resolved["lvet"]], "lvet") / 1000.0,
                        diastolic_pressure_pa=_finite(row[resolved["dbp"]], "dbp") * MMHG_TO_PA,
                        mean_pressure_pa=_finite(row[resolved["mbp"]], "mbp") * MMHG_TO_PA,
                        outlet_pressure_pa=_finite(row[resolved["p_out"]], "p_out") * MMHG_TO_PA,
                        blood_density_kg_per_m3=_finite(row[resolved["density"]], "density"),
                        blood_viscosity_pa_s=_finite(row[resolved["viscosity"]], "viscosity"),
                        momentum_correction_alpha=_finite(row[resolved["alpha"]], "alpha"),
                        systemic_pvr_pa_s_per_m3=_finite(row[resolved["pvr"]], "pvr"),
                        wall_gamma_b0_g_per_s=_finite(row[resolved["b0"]], "b0"),
                        wall_gamma_b1_g_cm_per_s=_finite(row[resolved["b1"]], "b1"),
                        stiffness_k1_g_per_s2_per_cm=_finite(row[resolved["k1"]], "k1"),
                        stiffness_k2_per_cm=_finite(row[resolved["k2"]], "k2"),
                        stiffness_k3_g_per_s2_per_cm=_finite(row[resolved["k3"]], "k3"),
                        source_member=self._path.name,
                    )
        except OSError as exc:
            raise IntegrityError(f"unable to read verified PWDB model configuration {self._path}") from exc
        raise SelectionError(f"PWDB model configuration has no subject {subject_id!r}")


__all__ = ["PWDBModelConfiguration", "PWDBModelConfigurationReader"]
