"""Machine-readable HEMOSPACE contract for scientific AI agents."""

from __future__ import annotations

from .cohort import TRIAL_PROFILES
from .derivations import scalar_derivation_catalogue, waveform_derivation_catalogue
from .path import PATH_ARTIFACTS


def agent_contract() -> dict[str, object]:
    return {
        "kind": "vascuquest.hemospace.agent_contract",
        "contract_version": "hemospace-agent-1",
        "record_schema_version": "hemospace-1",
        "subject_interpretation": "virtual_simulation_instance_not_patient",
        "evidence_classes": {
            "SOURCE": "Direct value from a canonical PWDB artifact.",
            "RECONSTRUCTED": "Deterministic recovery from aligned source quantities.",
            "DERIVED": "Calculation using an explicit declared definition.",
            "INFERRED": "Estimate from a separately qualified inference method.",
            "MODELLED": "Output of an explicit research model/operator.",
        },
        "operations": {
            "record": {
                "cli": "vascuquest hemospace record",
                "purpose": "Build a Virtual Cardiovascular Record.",
                "depths": ["scalar", "geometry", "comprehensive"],
            },
            "path": {
                "cli": "vascuquest hemospace path",
                "purpose": "Lazily characterize one canonical path-resolved PWDB source.",
                "paths": sorted(PATH_ARTIFACTS),
                "optional_dependency": "h5py via VascuQuest[path]",
                "qualification": "implemented; local real-source qualification required for multi-GB canonical path artifacts",
            },
            "cohort_select": {
                "cli": "vascuquest hemospace cohort select",
                "purpose": "Select virtual subjects using explicit numeric source-phenotype criteria.",
            },
            "disease_response": {
                "cli": "vascuquest hemospace response",
                "purpose": "Pair healthy PWDB physiology with already-persisted Virtual Disease results without rerunning a solver.",
            },
            "closure": {
                "cli": "vascuquest hemospace closure",
                "purpose": "Audit source-artifact disposition and requested-depth knowledge completeness.",
            },
        },
        "criterion_syntax": "canonical_id>=number (also <=, >, <, ==, !=)",
        "trial_profiles": {
            key: value.to_dict() for key, value in sorted(TRIAL_PROFILES.items())
        },
        "derivation_catalogue": {
            "scalar": list(scalar_derivation_catalogue()),
            "waveform": list(waveform_derivation_catalogue()),
        },
        "forbidden_gap_filling": [
            "Do not invent smoking, genetics, medications, symptoms, renal function, plaque composition, thrombotic state, or longitudinal life events.",
            "Do not reinterpret PWDB age groups as repeated observations of the same biological person.",
            "Do not promote DERIVED, RECONSTRUCTED, INFERRED, or MODELLED values to SOURCE.",
            "Do not report Virtual Disease response as clinical treatment efficacy.",
            "Do not infer rupture risk, stroke risk, thrombosis, wall shear stress, or 3-D recirculation from the one-dimensional disease engine.",
        ],
        "required_reporting": [
            "dataset persistent identifier",
            "canonical subject IDs",
            "HEMOSPACE schema/agent contract versions",
            "record depth",
            "selection criteria for cohorts",
            "evidence class for every scientific statement",
            "disease condition/severity/run identity when modelled output is used",
            "warnings and NOT_KNOWABLE_FROM_PWDB entries relevant to the conclusion",
        ],
        "recommended_sequence": [
            "Start with scalar records or phenotype cohort selection.",
            "Escalate to geometry only when vascular anatomy is relevant.",
            "Escalate to comprehensive common-site waves only for waveform/mechanics/energetics endpoints.",
            "Request a path profile explicitly only when continuous path information is required.",
            "Use disease-response mode only on an existing verified disease cohort bundle.",
            "Run knowledge closure before claiming a record is comprehensive for the requested depth.",
        ],
    }


__all__ = ["agent_contract"]
