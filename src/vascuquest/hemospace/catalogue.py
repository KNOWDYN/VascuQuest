"""HEMOSPACE source semantics and bounded interpretation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


PWDB_CITATION = "doi:10.1152/ajpheart.00218.2019"


@dataclass(frozen=True, slots=True)
class FieldSemantics:
    canonical_id: str
    label: str
    section: str
    unit: str | None
    location: str | None = None
    notes: tuple[str, ...] = ()


_VARIATIONS = {
    "DIA": ("large_artery_diameter_variation", "Large-artery diameter variation"),
    "HR": ("heart_rate_variation", "Heart-rate variation"),
    "LEN": ("proximal_aortic_length_variation", "Proximal-aortic-length variation"),
    "LVET": ("lvet_variation", "Left-ventricular ejection-time variation"),
    "MBP": ("mean_blood_pressure_variation", "Mean-blood-pressure variation"),
    "PVC": ("peripheral_vascular_compliance_variation", "Peripheral-vascular-compliance variation"),
    "PWV": ("arterial_stiffness_variation", "Arterial-stiffness/PWV variation"),
    "RFV": ("reverse_flow_volume_variation", "Aortic-root reverse-flow-volume variation"),
    "SV": ("stroke_volume_variation", "Stroke-volume variation"),
    "PFT": ("peak_flow_time_variation", "Aortic-root peak-flow-time variation"),
}

_MODEL_FIELDS = {
    "base": ("global_baseline_flag", "Global baseline-subject flag", "generative_physiology"),
    "base_age": ("age_baseline_flag", "Age-specific baseline-subject flag", "generative_physiology"),
    "age": ("simulation_age", "Simulation age", "identity_and_design"),
    "hr": ("prescribed_heart_rate", "Prescribed heart rate", "generative_physiology"),
    "sv": ("prescribed_stroke_volume", "Prescribed stroke volume", "generative_physiology"),
    "pft": ("prescribed_peak_flow_time", "Prescribed peak-flow time", "generative_physiology"),
    "rfv": ("prescribed_reverse_flow_volume", "Prescribed reverse-flow volume", "generative_physiology"),
    "dbp": ("prescribed_diastolic_pressure", "Prescribed diastolic pressure", "generative_physiology"),
    "mbp": ("prescribed_mean_pressure", "Prescribed mean pressure", "generative_physiology"),
    "viscosity": ("blood_viscosity", "Blood viscosity", "blood_and_material"),
    "alpha": ("velocity_profile_coefficient", "Velocity-profile coefficient", "blood_and_material"),
    "p_drop": ("prescribed_tree_pressure_drop", "Prescribed arterial-tree pressure drop", "generative_physiology"),
    "pvc": ("peripheral_compliance_scale", "Peripheral vascular compliance scale", "generative_physiology"),
    "p_out": ("outflow_pressure", "Outflow pressure", "generative_physiology"),
    "density": ("blood_density", "Blood density", "blood_and_material"),
    "lvet": ("prescribed_lvet", "Prescribed left-ventricular ejection time", "generative_physiology"),
    "pvr": ("prescribed_peripheral_resistance", "Prescribed peripheral vascular resistance", "generative_physiology"),
    "b0": ("wall_viscosity_b0", "Arterial-wall-viscosity coefficient b0", "blood_and_material"),
    "b1": ("wall_viscosity_b1", "Arterial-wall-viscosity coefficient b1", "blood_and_material"),
    "k0": ("wall_stiffness_k0", "Arterial-wall-stiffness coefficient k0", "blood_and_material"),
    "k1": ("wall_stiffness_k1", "Arterial-wall-stiffness coefficient k1", "blood_and_material"),
    "k2": ("wall_stiffness_k2", "Arterial-wall-stiffness coefficient k2", "blood_and_material"),
}

_HEMODYNAMIC_SECTIONS = {
    "HR": "cardiac",
    "SV": "cardiac",
    "CO": "cardiac",
    "LVET": "cardiac",
    "PFT": "cardiac",
    "RFV": "flow",
    "SBP": "pressure",
    "DBP": "pressure",
    "MBP": "pressure",
    "PP": "pressure",
    "PP_amp": "pressure",
    "AP": "wave_reflection",
    "AIx": "wave_reflection",
    "Tr": "wave_reflection",
    "PWV_a": "wave_propagation",
    "PWV_cf": "wave_propagation",
    "PWV_br": "wave_propagation",
    "PWV_fa": "wave_propagation",
    "SVR": "systemic_haemodynamics",
    "svr": "systemic_haemodynamics",
    "pvr": "systemic_haemodynamics",
    "pvc": "arterial_mechanics",
    "pvc_iw": "arterial_mechanics",
    "ac": "arterial_mechanics",
    "c": "arterial_mechanics",
    "tau": "arterial_mechanics",
}

_PW_INDEX_UNITS = {
    "SBP": "mmHg", "DBP": "mmHg", "MBP": "mmHg", "PP": "mmHg",
    "Qmax": "m^3/s", "Qmin": "m^3/s", "Qmean": "m^3/s", "Qtotal": "m^3",
    "Umax": "m/s", "Umin": "m/s", "Umean": "m/s",
    "Amax": "m^2", "Amin": "m^2", "Amean": "m^2",
    "P1in": "mmHg", "P1pk": "mmHg", "P2in": "mmHg", "P2pk": "mmHg",
    "Psys": "mmHg", "Pms": "mmHg/s", "AI": "%", "AP": "mmHg", "PTT": "s",
    "PPGa": "au/s^2", "PPGb": "au/s^2", "PPGc": "au/s^2", "PPGd": "au/s^2", "PPGe": "au/s^2",
    "PPGsys": "au", "PPGdia": "au", "PPGdic": "au", "PPGms": "au/s",
    "RI": "1", "SI": "m/s", "AGI_mod": "1",
}

_SITE_LABELS = {
    "AorticRoot": "aortic root", "ThorAorta": "thoracic aorta", "AbdAorta": "abdominal aorta",
    "IliacBif": "iliac bifurcation", "Carotid": "carotid", "SupTemporal": "superficial temporal",
    "SupMidCerebral": "superior middle cerebral", "Brachial": "brachial", "Radial": "radial",
    "Digital": "digital", "CommonIliac": "common iliac", "Femoral": "femoral", "AntTibial": "anterior tibial",
}

_UNIT_RE = re.compile(r"^(?P<name>.*?)\s*\[(?P<unit>[^\]]+)\]\s*$")


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return value or "field"


def _split_unit(field: str) -> tuple[str, str | None]:
    match = _UNIT_RE.match(field)
    if match:
        return match.group("name").strip(), match.group("unit").strip()
    return field.strip(), None


def semantics_for(source_scope: str, source_field: str) -> FieldSemantics:
    """Resolve deterministic semantics for every supported scalar source field.

    Unknown-but-numeric source columns are retained under a stable source-based
    canonical identifier rather than discarded or given invented physiology.
    """

    field = source_field.strip()
    if source_scope == "model_variations":
        if field in _VARIATIONS:
            canonical, label = _VARIATIONS[field]
            return FieldSemantics(canonical, label, "generative_variation", "SD_from_age_specific_mean")
        return FieldSemantics(f"model_variation_{_slug(field)}", field, "generative_variation", "SD_from_age_specific_mean")

    if source_scope == "model_configurations":
        raw_name, unit = _split_unit(field)
        key = raw_name.strip().lower()
        if key in _MODEL_FIELDS:
            canonical, label, section = _MODEL_FIELDS[key]
            return FieldSemantics(canonical, label, section, unit)
        return FieldSemantics(f"model_config_{_slug(raw_name)}", raw_name, "generative_physiology", unit)

    if source_scope == "haemodynamic_parameters":
        raw_name, unit = _split_unit(field)
        section = _HEMODYNAMIC_SECTIONS.get(raw_name, "systemic_haemodynamics")
        if raw_name.startswith("dia_") or raw_name.startswith("len"):
            section = "anatomy"
        elif "drop" in raw_name.lower() or raw_name in {"SBP_diff", "SMBP"}:
            section = "pressure"
        elif raw_name in {"RI", "SI", "AGI_mod"}:
            section = "ppg"
        return FieldSemantics(f"haemodynamic_{_slug(raw_name)}", raw_name, section, unit)

    if source_scope == "pulse_wave_indices":
        if field == "Age":
            return FieldSemantics("pulse_wave_index_age", "Pulse-wave-index age", "identity_and_design", "years")
        parts = field.split("_")
        site = parts[0] if parts and parts[0] in _SITE_LABELS else None
        metric = parts[1] if site is not None and len(parts) >= 2 else field
        suffix = parts[2] if site is not None and len(parts) >= 3 else None
        unit = "s" if suffix == "T" else _PW_INDEX_UNITS.get(metric)
        section = "pulse_wave"
        if metric.startswith("Q") or metric.startswith("U"):
            section = "flow"
        elif metric.startswith("A") and metric not in {"AI", "AP", "AGI_mod"}:
            section = "arterial_mechanics"
        elif metric in {"SBP", "DBP", "MBP", "PP", "P1in", "P1pk", "P2in", "P2pk", "Psys", "Pms"}:
            section = "pressure"
        elif metric in {"AI", "AP", "PTT"}:
            section = "wave_reflection" if metric != "PTT" else "wave_propagation"
        elif metric.startswith("PPG") or metric in {"RI", "SI", "AGI_mod"}:
            section = "ppg"
        label = metric if site is None else f"{_SITE_LABELS[site].title()} {metric}"
        if suffix == "T":
            label += " time"
        return FieldSemantics(f"pulse_wave_{_slug(field)}", label, section, unit, site)

    if source_scope == "onset_times":
        if "_" in field:
            site, signal = field.rsplit("_", 1)
            return FieldSemantics(
                f"onset_{_slug(field)}",
                f"{_SITE_LABELS.get(site, site).title()} {signal} onset time",
                "wave_propagation",
                "s",
                site if site in _SITE_LABELS else None,
            )
        return FieldSemantics(f"onset_{_slug(field)}", field, "wave_propagation", "s")

    raw_name, unit = _split_unit(field)
    return FieldSemantics(f"{_slug(source_scope)}_{_slug(raw_name)}", raw_name, "source_other", unit)


SCALAR_SOURCE_ARTIFACTS = (
    ("model_configurations", "model_configurations"),
    ("model_variations", "model_variations"),
    ("haemodynamic_parameters", "haemodynamic_parameters"),
    ("pulse_wave_indices", "pulse_wave_indices"),
    ("onset_times", "onset_times"),
)

UNAVAILABLE_BY_PWDB = (
    ("biological_sex", "PWDB does not encode a biological-sex attribute for these virtual simulation instances."),
    ("smoking_history", "No smoking or exposure history is encoded in PWDB."),
    ("genetics", "No genomic or inherited-variant information is encoded in PWDB."),
    ("renal_function", "No renal laboratory or organ-function state is encoded in PWDB."),
    ("medication_history", "No medication history is encoded in PWDB."),
    ("clinical_symptoms", "The virtual subjects are simulations, not symptomatic clinical participants."),
    ("plaque_composition", "PWDB does not encode plaque histology or composition."),
    ("thrombotic_state", "PWDB does not encode coagulation or thrombotic state."),
    ("longitudinal_life_history", "Age groups are not repeated observations of one biological individual."),
    ("future_clinical_event_risk", "Clinical event probabilities are not identifiable from PWDB alone."),
)


__all__ = [
    "FieldSemantics",
    "PWDB_CITATION",
    "SCALAR_SOURCE_ARTIFACTS",
    "UNAVAILABLE_BY_PWDB",
    "semantics_for",
]
