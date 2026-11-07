#!/usr/bin/env python3
"""Regenerate the website's cardioacoustics dashboard JSON from the supplied study ZIP.

Usage:
    python tools/site/build_cardioacoustics_dashboard.py \
        Cardioacoustics_ECs_v1.0.0.zip site/assets/cardioacoustics-dashboard.json

Requires NumPy. Reads only archived arrays; does not invent, fit or extrapolate signals.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np

ROOT = "VascuQuest_Cardioacoustics_Zenodo_v1.0.0/"
SITE_LABELS = {
    "proximal_aorta": ("Proximal aorta", 1),
    "left_common_carotid": ("Left common carotid", 15),
    "abdominal_aorta_iv": ("Abdominal aorta IV", 39),
    "left_common_iliac": ("Left common iliac", 42),
    "left_femoral_path": ("Left femoral pathway", 46),
}


def vector(values: np.ndarray, digits: int) -> list[float]:
    return [round(float(value), digits) for value in values]


def build(path: Path) -> dict:
    with ZipFile(path) as zip_file:
        with np.load(BytesIO(zip_file.read(ROOT + "population/transfer_selected.npz")), allow_pickle=False) as transfer, np.load(
            BytesIO(zip_file.read(ROOT + "physiological_exposure/wp2_primary_exposure.npz")), allow_pickle=False
        ) as exposure:
            states = transfer["states"].tolist()
            sites = transfer["site_id"].tolist()
            frequencies = transfer["frequency_hz"].tolist()
            idx = list(range(0, len(frequencies), 3))
            assert len(frequencies) == 61 and len(idx) == 21
            assert states == ["healthy", "partial", "stiff"]
            assert list(sites) == list(SITE_LABELS)
            assert len(transfer["subject_id"]) == 102
            assert transfer["subject_id"].tolist() == exposure["subject_id"].tolist()
            ages = [25, 35, 45, 55, 65, 75]
            sample_subject = exposure["subject_id"].tolist().index("1048")
            payload = {
                "archive": "Cardioacoustics_ECs_v1.0.0",
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "subjects": 102,
                "age": ages,
                "states": states,
                "sampleFrequencyHz": vector(transfer["frequency_hz"][idx], 1),
                "sourceFrequencyHz": {"start": 10, "end": 40, "step": 0.5, "count": 61},
                "source_event": "WP2/A2",
                "source_event_frequency_hz": float(exposure["frequency_hz"]),
                "source_event_pressure_pa": float(exposure["root_pressure_pa"]),
                "sites": [],
            }
            for site_index, site_id in enumerate(sites):
                label, segment_id = SITE_LABELS[site_id]
                item = {"id": site_id, "label": label, "segment": segment_id, "states": []}
                for state_index in range(3):
                    pressure_transfer = abs(transfer["pressure_transfer"][:, state_index, site_index, :])
                    traction_transfer = abs(transfer["traction_transfer"][:, state_index, site_index, :])
                    motion_transfer = abs(transfer["displacement_transfer"][:, state_index, site_index, :])
                    pressure = exposure["pressure"][:, state_index, site_index]
                    traction = exposure["traction"][:, state_index, site_index]
                    displacement = exposure["displacement"][:, state_index, site_index]
                    reference = pressure[sample_subject]
                    item["states"].append({
                        "gain": vector(np.median(20 * np.log10(np.maximum(pressure_transfer[:, idx], 1e-12)), axis=0), 2),
                        "traction": vector(np.median(traction_transfer[:, idx] * 1000, axis=0), 3),
                        "motion": vector(np.median(motion_transfer[:, idx] * 1e9, axis=0), 2),
                        "p50": round(float(np.median(abs(pressure))), 1),
                        "t50": round(float(np.median(abs(traction))), 3),
                        "m50": round(float(np.median(abs(displacement)) * 1e6), 2),
                        "acc50": round(float(np.median(exposure["wall_acceleration_m_per_s2"][:, state_index, site_index])), 3),
                        "grad50": round(float(np.median(exposure["shear_gradient_pa_per_s"][:, state_index, site_index])), 1),
                        "refP": vector(np.array([reference.real, reference.imag]), 2),
                    })
                payload["sites"].append(item)
            payload["pwv"] = {
                name: vector([
                    np.median(transfer["state_cfpwv_m_per_s"][transfer["age_years"] == age, si])
                    for age in ages
                ], 2)
                for si, name in enumerate(states)
            }
            return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Written {args.output}: {len(result['sites'])} sites × {len(result['states'])} states")


if __name__ == "__main__":
    main()
