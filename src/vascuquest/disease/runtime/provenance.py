"""Deterministic provenance for in-memory Virtual Disease datasets."""

from __future__ import annotations

from dataclasses import asdict

from vascuquest._version import __version__
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import VascularLocation
from vascuquest.domain.result import ValidityState, ValueState
from vascuquest.disease.model import DiseaseQuantityStatus, DiseaseRunIdentity
from vascuquest.disease.physics.model import DiseasePhysicsModel
from vascuquest.disease.solver.model import SolverDiagnostics, SolverOptions
from vascuquest.provenance import (
    ComponentReference,
    ProvenanceBuilder,
    ProvenanceRecord,
    SourceArtifactReference,
)
from vascuquest.schema import load_manifest

RUNTIME_METHOD_ID = "vascuquest:virtual-disease-runtime"
RUNTIME_COMPONENT_VERSION = "1.0.0"


def _identity_payload(identity: DatasetIdentity) -> dict[str, str]:
    return {
        "dataset_family": identity.dataset_family,
        "record_id": identity.record_id,
        "persistent_identifier": identity.persistent_identifier,
        "schema_version": identity.schema_version,
    }


def _source_artifacts() -> tuple[SourceArtifactReference, ...]:
    manifest = load_manifest()
    references: list[SourceArtifactReference] = []
    for artifact_id in (
        "model_configurations",
        "geometry",
        "common_site_waveforms_csv",
    ):
        artifact = manifest.artifact(artifact_id)
        references.append(
            SourceArtifactReference(
                artifact_id=artifact.artifact_id,
                checksum_algorithm=artifact.checksum_algorithm,
                checksum_value=artifact.checksum_value,
            )
        )
    return tuple(references)


def runtime_component() -> ComponentReference:
    return ComponentReference(
        qualified_id=RUNTIME_METHOD_ID,
        implementation_version=RUNTIME_COMPONENT_VERSION,
        distribution_name="vascuquest",
        distribution_version=__version__,
    )


def build_runtime_provenance(
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject: SubjectKey,
    physics: DiseasePhysicsModel,
    solver_options: SolverOptions,
    diagnostics: SolverDiagnostics,
    quantity_name: str,
    quantity_status: DiseaseQuantityStatus,
    output_identity: str,
    location: VascularLocation | None = None,
    source_fields: tuple[str, ...] = (),
    citations: tuple[str, ...] = (),
) -> ProvenanceRecord:
    """Build one MODELLED result record with explicit parent/source lineage facts.

    Core provenance v1 intentionally requires direct input records to use the
    same dataset identity. The parent PWDB identity is therefore encoded as an
    explicit immutable parameter rather than falsifying a cross-dataset input
    edge. Source artifact checksums still identify the canonical PWDB inputs.
    """

    if runtime_identity != subject.dataset_identity:
        raise ValueError("runtime subject identity must match runtime dataset identity")
    parameters = {
        "virtual_disease_contract": run_identity.contract_version,
        "run_id": run_identity.run_id,
        "parent_dataset": _identity_payload(run_identity.parent_dataset_identity),
        "parent_canonical_subject_id": subject.canonical_subject_id,
        "condition": run_identity.request.specification.condition.value,
        "disease_parameters": dict(run_identity.request.specification.parameters),
        "preset_version": run_identity.request.specification.preset_version,
        "quantity": quantity_name,
        "quantity_status": quantity_status.value,
        "modified_segment_ids": list(physics.modified_segment_ids),
        "solver_options": asdict(solver_options),
        "solver_diagnostics": asdict(diagnostics),
    }
    return ProvenanceBuilder(runtime_identity).build(
        evidence=EvidenceClass.MODELLED,
        validity=ValidityState.NOT_EVALUATED,
        value_state=ValueState.PRESENT,
        source_artifacts=_source_artifacts(),
        subject=subject,
        location=location,
        source_fields=source_fields,
        method_id=RUNTIME_METHOD_ID,
        component=runtime_component(),
        parameters=parameters,
        assumptions=physics.assumptions,
        citations=tuple(sorted(set(physics.citations + citations))),
        random_state={
            "population_selection_seed": run_identity.request.seed,
            "population_selection_algorithm": "sha256_rank_v1",
        },
        warnings=(
            "Virtual Disease output is MODELLED and is not a clinical observation.",
            "Healthy PWDB reconstruction thresholds remain unfrozen; disease output is not clinically validated.",
        ),
        output_identity=output_identity,
    )


__all__ = [
    "RUNTIME_COMPONENT_VERSION",
    "RUNTIME_METHOD_ID",
    "build_runtime_provenance",
    "runtime_component",
]
