"""Reconstruction of the upstream PWDB physiological-plausibility gate.

The PWDB exporter assesses seven pressure characteristics against age-dependent
99% literature ranges. HEMOSPACE reproduces that source algorithm from the
lightweight haemodynamic table, avoiding a whole-file load of pwdb_data.mat.
"""

from __future__ import annotations

import math

import numpy as np

from .model import KnowledgeItem


_AGES = np.asarray([15, 25, 35, 45, 55, 65, 75, 85], dtype=float)

# McEniery 2005 data embedded by the upstream PWDB export algorithm.
_LITERATURE: dict[str, dict[str, tuple[tuple[float, ...], tuple[float, ...], tuple[int, ...]]]] = {
    "SBP_b": {
        "male": ((123,124,123,125,125,126,127,130),(10,10,9,9,9,9,9,8),(172,178,183,258,429,430,280,39)),
        "female": ((113,115,115,118,122,126,127,128),(10,10,12,11,11,10,10,10),(133,101,165,301,495,509,290,38)),
    },
    "DBP_b": {
        "male": ((73,75,77,79,79,78,76,75),(8,10,9,9,9,9,9,8),(172,178,183,258,429,430,280,39)),
        "female": ((72,73,74,75,75,74,72,70),(8,8,9,8,7,7,8,9),(133,101,165,301,495,509,290,38)),
    },
    "PP_b": {
        "male": ((50,49,47,46,46,49,51,55),(9,9,8,7,8,8,8,9),(172,178,183,258,429,430,280,39)),
        "female": ((41,43,41,43,46,51,54,57),(8,7,9,9,9,8,9,11),(133,101,165,301,495,509,290,38)),
    },
    "MBP_b": {
        "male": ((88,89,92,95,95,94,93,92),(8,8,8,7,7,7,7,8),(172,178,183,258,429,430,280,39)),
        "female": ((86,86,88,90,93,93,92,90),(8,8,9,9,8,8,8,8),(133,101,165,301,495,509,290,38)),
    },
    "SBP_a": {
        "male": ((103,105,109,113,115,117,118,120),(8,8,9,9,9,9,9,8),(172,178,183,258,429,430,280,39)),
        "female": ((98,101,105,109,115,118,119,120),(9,9,11,11,11,10,9,11),(133,101,165,301,495,509,290,38)),
    },
    "PP_a": {
        "male": ((29,30,31,34,35,39,42,45),(5,6,6,6,7,7,7,9),(172,178,183,258,429,430,280,39)),
        "female": ((25,27,30,33,38,43,56,49),(6,7,8,8,8,8,8,12),(133,101,165,301,495,509,290,38)),
    },
    "PP_amp": {
        "male": ((1.72,1.7,1.50,1.39,1.33,1.26,1.24,1.25),(0.11,0.14,0.18,0.15,0.16,0.13,0.12,0.15),(172,178,183,258,429,430,280,39)),
        "female": ((1.67,1.59,1.41,1.29,1.22,1.21,1.19,1.18),(0.15,0.2,0.18,0.15,0.11,0.10,0.10,0.11),(133,101,165,301,495,509,290,38)),
    },
}

_CANONICAL = {
    "SBP_b": "haemodynamic_sbp_b",
    "DBP_b": "haemodynamic_dbp_b",
    "PP_b": "haemodynamic_pp_b",
    "MBP_b": "haemodynamic_mbp_b",
    "SBP_a": "haemodynamic_sbp_a",
    "PP_a": "haemodynamic_pp_a",
    "PP_amp": "haemodynamic_pp_amp",
}


def _pooled(mean1: float, sd1: float, n1: int, mean2: float, sd2: float, n2: int) -> tuple[float, float]:
    sum1 = n1 * mean1
    sum2 = n2 * mean2
    sumsq1 = (n1 - 1) * sd1 * sd1 + (sum1 * sum1) / n1
    sumsq2 = (n2 - 1) * sd2 * sd2 + (sum2 * sum2) / n2
    total_n = n1 + n2
    total_sum = sum1 + sum2
    total_sumsq = sumsq1 + sumsq2
    mean = total_sum / total_n
    sd = math.sqrt((total_sumsq - total_sum * total_sum / total_n) / (total_n - 1))
    return mean, sd


def _range(parameter: str, age: float) -> tuple[float, float, float, float]:
    data = _LITERATURE[parameter]
    male_mean, male_sd, male_n = data["male"]
    female_mean, female_sd, female_n = data["female"]
    pooled_mean: list[float] = []
    pooled_sd: list[float] = []
    for i in range(len(_AGES)):
        mean, sd = _pooled(
            float(male_mean[i]), float(male_sd[i]), int(male_n[i]),
            float(female_mean[i]), float(female_sd[i]), int(female_n[i]),
        )
        pooled_mean.append(mean)
        pooled_sd.append(sd)
    mean_at_age = float(np.interp(age, _AGES, np.asarray(pooled_mean)))
    sd_at_age = float(np.interp(age, _AGES, np.asarray(pooled_sd)))
    return mean_at_age, sd_at_age, mean_at_age - 2.575 * sd_at_age, mean_at_age + 2.575 * sd_at_age


def reconstruct_plausibility(source_items: list[KnowledgeItem]) -> KnowledgeItem | None:
    by_id = {item.canonical_id: item for item in source_items if item.value is not None}
    age_item = by_id.get("haemodynamic_age") or by_id.get("simulation_age")
    if age_item is None:
        return None
    age = float(age_item.value)
    criteria: dict[str, object] = {}
    plausible = True
    for source_name, canonical_id in _CANONICAL.items():
        item = by_id.get(canonical_id)
        if item is None:
            return None
        value = float(item.value)
        mean, sd, lower, upper = _range(source_name, age)
        within = lower <= value <= upper
        plausible = plausible and within
        criteria[source_name] = {
            "value": value,
            "literature_mean": mean,
            "literature_sd": sd,
            "lower_99_percent": lower,
            "upper_99_percent": upper,
            "within_range": within,
        }
    return KnowledgeItem(
        canonical_id="pwdb_physiological_plausibility",
        label="PWDB physiological plausibility assessment",
        section="quality_and_plausibility",
        value={"plausible": plausible, "criteria": criteria},
        unit=None,
        evidence="RECONSTRUCTED",
        source_artifact="unified_matlab",
        source_field="data.plausibility.plausibility_log",
        method=(
            "Exact reconstruction of upstream PWDB exporter gate: combined male/female "
            "McEniery-2005 age-specific reference distributions, linear age interpolation, "
            "and mean +/- 2.575 SD limits for SBP_b, DBP_b, PP_b, MBP_b, SBP_a, PP_a, PP_amp."
        ),
        assumptions=(
            "Reproduces the source exporter algorithm and its embedded reference data; it is not a new HEMOSPACE clinical screening rule.",
        ),
        notes=(
            "A virtual-subject plausibility flag relative to the PWDB source-generation validation, not a clinical diagnosis.",
        ),
    )


__all__ = ["reconstruct_plausibility"]
