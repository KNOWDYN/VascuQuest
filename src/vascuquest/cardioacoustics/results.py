"""Conversion of cardioacoustic solutions to portable VascuQuest results."""
from __future__ import annotations

import hashlib
import json
import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import SubjectKey
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState
from .model import CardioacousticNetworkSolution

_METHOD_ID = "vascuquest:cardioacoustics:endothelial-spectrum-v1"


def _provenance(solution: CardioacousticNetworkSolution, baseline: BaselineCardiovascularState) -> str:
    payload = {
        "method": _METHOD_ID,
        "dataset": baseline.dataset_identity.persistent_identifier,
        "subject": baseline.canonical_subject_id,
        "source": solution.source_identity,
        "source_citations": list(solution.source_citations),
        "backend": solution.backend_id,
        "terminal_model": solution.terminal_model,
        "frequency_hz": solution.frequency_hz.tolist(),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"analysis:{digest}"


def _quantity(
    baseline: BaselineCardiovascularState,
    canonical_name: str,
    label: str,
    description: str,
    unit: str,
    dimension: str,
    citations: tuple[str, ...],
) -> QuantityDefinition:
    return QuantityDefinition(
        canonical_name=canonical_name,
        label=label,
        description=description,
        value_kind="numeric",
        schema_version=baseline.dataset_identity.schema_version,
        physical_dimension=dimension,
        canonical_unit=unit,
        default_evidence=EvidenceClass.MODELLED,
        citations=citations,
        applicable_contexts=("cardioacoustics",),
    )


def endothelial_spectrum_results(
    solution: CardioacousticNetworkSolution,
    baseline: BaselineCardiovascularState,
) -> tuple[ScientificResult, ...]:
    """Return portable amplitude/phase fields over cell x frequency coordinates."""

    if not isinstance(solution, CardioacousticNetworkSolution):
        raise TypeError("solution must be a CardioacousticNetworkSolution")
    if not isinstance(baseline, BaselineCardiovascularState):
        raise TypeError("baseline must be a BaselineCardiovascularState")
    if not solution.cells:
        raise ValueError("solution contains no arterial cells")

    pressure = np.stack([cell.load.pressure_pa for cell in solution.cells], axis=0)
    traction = np.stack([cell.load.tangential_traction_pa for cell in solution.cells], axis=0)
    displacement = np.stack([cell.load.wall_displacement_m for cell in solution.cells], axis=0)
    segment_ids = np.asarray([cell.segment_id for cell in solution.cells])
    axial = np.asarray([cell.axial_position_m for cell in solution.cells], dtype=float)
    coordinates = (
        Coordinate("frequency", solution.frequency_hz, "Hz"),
        Coordinate("segment_id", segment_ids, None),
        Coordinate("axial_position", axial, "m"),
    )
    subject = SubjectKey(baseline.dataset_identity, baseline.canonical_subject_id)
    provenance = _provenance(solution, baseline)

    specs = (
        (
            "cardioacoustic_endothelial_pressure_amplitude",
            "Endothelial cardioacoustic pressure amplitude",
            "Magnitude of the modelled cardioacoustic pressure phasor at the endothelial interface.",
            "Pa",
            "pressure",
            np.abs(pressure),
        ),
        (
            "cardioacoustic_endothelial_pressure_phase",
            "Endothelial cardioacoustic pressure phase",
            "Phase of the modelled cardioacoustic pressure phasor using exp(i omega t).",
            "rad",
            "angle",
            np.angle(pressure),
        ),
        (
            "cardioacoustic_endothelial_traction_amplitude",
            "Endothelial cardioacoustic tangential traction amplitude",
            "Magnitude of oscillatory blood traction delivered tangentially to the endothelial interface.",
            "Pa",
            "pressure",
            np.abs(traction),
        ),
        (
            "cardioacoustic_endothelial_traction_phase",
            "Endothelial cardioacoustic tangential traction phase",
            "Phase of oscillatory tangential endothelial traction using exp(i omega t).",
            "rad",
            "angle",
            np.angle(traction),
        ),
        (
            "cardioacoustic_wall_displacement_amplitude",
            "Cardioacoustic wall displacement amplitude",
            "Magnitude of radial wall-borne substrate motion presented to the endothelial basal surface.",
            "m",
            "length",
            np.abs(displacement),
        ),
        (
            "cardioacoustic_wall_displacement_phase",
            "Cardioacoustic wall displacement phase",
            "Phase of radial wall-borne substrate motion using exp(i omega t).",
            "rad",
            "angle",
            np.angle(displacement),
        ),
    )

    output: list[ScientificResult] = []
    for name, label, description, unit, dimension, values in specs:
        values = np.asarray(values, dtype=float)
        values.setflags(write=False)
        output.append(
            ScientificResult(
                dataset_identity=baseline.dataset_identity,
                quantity=_quantity(
                    baseline, name, label, description, unit, dimension, solution.source_citations
                ),
                values=values,
                provenance_ref=provenance,
                dimensions=("cell", "frequency"),
                coordinates=coordinates,
                source_unit=unit,
                source_label=label,
                subject=subject,
                evidence=EvidenceClass.MODELLED,
                validity=ValidityState.VALID_WITH_WARNING,
                warnings=(
                    "Cardioacoustic terminal loading is a matched-impedance analytical boundary, not a PWDB Windkessel extrapolation into the sound band.",
                    "The result predicts endothelial mechanical exposure and does not establish a biological cellular response.",
                ),
                method_id=_METHOD_ID,
            )
        )
    return tuple(output)


__all__ = ["endothelial_spectrum_results"]
