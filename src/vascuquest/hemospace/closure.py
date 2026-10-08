"""Machine-auditable HEMOSPACE knowledge-closure reporting."""

from __future__ import annotations

from dataclasses import dataclass

from vascuquest.schema import load_manifest

from .derivations import scalar_derivation_catalogue, waveform_derivation_catalogue
from .path import PATH_ARTIFACTS


_PATH_QUALIFICATION = (
    "Qualified against the authoritative PWDB revised-submission exporter contract and "
    "MATLAB-v7.3/HDF5 struct/cell reference layout; canonical artifact identity remains "
    "enforced independently through manifest checksums."
)

_ARTIFACT_DISPOSITIONS = {
    "model_configurations": ("EXPOSED", "All numeric per-subject fields are exposed by HEMOSPACE scalar records."),
    "model_variations": ("EXPOSED", "All numeric generative-variation fields are exposed with design-space semantics."),
    "haemodynamic_parameters": ("EXPOSED", "All numeric haemodynamic fields are exposed by HEMOSPACE scalar records."),
    "pulse_wave_indices": ("EXPOSED", "All numeric pulse-wave-index fields are exposed by HEMOSPACE scalar records."),
    "onset_times": ("EXPOSED", "All numeric onset/fiducial-time fields are exposed by HEMOSPACE scalar records."),
    "geometry": ("ON_DEMAND", "Subject-specific geometry is exposed at geometry/comprehensive depth."),
    "common_site_waveforms_csv": ("ON_DEMAND", "Canonical P/U/A/PPG source waves are summarized at comprehensive depth and remain retrievable through core VascuQuest."),
    "common_site_waveforms_matlab": ("REDUNDANT_REPRESENTATION", "HEMOSPACE uses the canonical CSV common-site representation to avoid duplicate scientific meaning."),
    "common_site_waveforms_wfdb": ("REDUNDANT_REPRESENTATION", "HEMOSPACE uses the canonical CSV common-site representation to avoid duplicate scientific meaning."),
    "unified_matlab": ("PARTIALLY_RECONSTRUCTED", "The source physiological-plausibility flag is reconstructed exactly from lightweight haemodynamics. Most waveform/configuration content overlaps canonical artifacts, but a small set of exporter-only configuration metadata (for example desired-characteristic bookkeeping and static network names) is not loaded by default because the canonical 701.7 MB legacy MAT file has no bounded per-subject access path."),
    "path_aorta_brain": ("QUALIFIED_LAZY_ON_DEMAND", _PATH_QUALIFICATION),
    "path_aorta_finger": ("QUALIFIED_LAZY_ON_DEMAND", _PATH_QUALIFICATION),
    "path_aorta_foot_p": ("QUALIFIED_LAZY_ON_DEMAND", f"Pressure component for the aorta-to-foot path. {_PATH_QUALIFICATION}"),
    "path_aorta_foot_u": ("QUALIFIED_LAZY_ON_DEMAND", f"Velocity component for the aorta-to-foot path. {_PATH_QUALIFICATION}"),
    "path_aorta_foot_a": ("QUALIFIED_LAZY_ON_DEMAND", f"Area component for the aorta-to-foot path. {_PATH_QUALIFICATION}"),
    "path_aorta_rsubclavian": ("QUALIFIED_LAZY_ON_DEMAND", _PATH_QUALIFICATION),
}


@dataclass(frozen=True, slots=True)
class KnowledgeClosureReport:
    subject_id: str
    requested_depth: str
    status: str
    scalar_source_complete: bool
    geometry_included: bool
    common_site_waveforms_included: bool
    artifact_dispositions: tuple[dict[str, str], ...]
    derivations: tuple[dict[str, str], ...]
    path_modes: tuple[str, ...]
    unavailable_categories: tuple[str, ...]
    unresolved: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "vascuquest.hemospace.knowledge_closure_report",
            "schema_version": "hemospace-1",
            "subject_id": self.subject_id,
            "requested_depth": self.requested_depth,
            "status": self.status,
            "scalar_source_complete": self.scalar_source_complete,
            "geometry_included": self.geometry_included,
            "common_site_waveforms_included": self.common_site_waveforms_included,
            "artifact_dispositions": list(self.artifact_dispositions),
            "derivations": list(self.derivations),
            "path_modes": list(self.path_modes),
            "unavailable_categories": list(self.unavailable_categories),
            "unresolved": list(self.unresolved),
            "closure_definition": (
                "Every canonical PWDB artifact has an explicit HEMOSPACE disposition; "
                "every emitted derived quantity is catalogued; unencoded biology remains explicit."
            ),
        }


def closure_report(session: object, subject_id: str, *, depth: str = "comprehensive") -> KnowledgeClosureReport:
    record = session.record(subject_id, depth=depth)
    manifest = load_manifest()
    dispositions: list[dict[str, str]] = []
    unresolved: list[str] = []
    for artifact in manifest.artifacts:
        disposition = _ARTIFACT_DISPOSITIONS.get(artifact.artifact_id)
        if disposition is None:
            unresolved.append(f"unclassified canonical artifact: {artifact.artifact_id}")
            state, reason = "UNCLASSIFIED", "No HEMOSPACE disposition is registered."
        else:
            state, reason = disposition
        dispositions.append({
            "artifact_id": artifact.artifact_id,
            "filename": artifact.filename,
            "disposition": state,
            "reason": reason,
        })

    if not record.coverage.scalar_source_complete:
        unresolved.append("scalar source-field closure failed")
    if depth in {"geometry", "comprehensive"} and not record.coverage.geometry_included:
        unresolved.append("geometry was requested but could not be included")
    if depth == "comprehensive" and not record.coverage.waveform_summaries_included:
        unresolved.append("common-site waveforms were requested but could not be summarized")
    unresolved.append(
        "canonical unified_matlab contains a small exporter-only metadata remainder that is deliberately not whole-file-loaded; HEMOSPACE exposes this limitation instead of performing an unbounded 701.7 MB legacy-MAT load"
    )

    derivations = tuple(scalar_derivation_catalogue()) + tuple(waveform_derivation_catalogue())
    unavailable = tuple(item.canonical_id for item in record.unavailable)
    operational_failures = [
        item for item in unresolved
        if not item.startswith("canonical unified_matlab contains")
    ]
    status = "CLOSED_WITH_DECLARED_SOURCE_FORMAT_LIMITATION" if not operational_failures else "OPEN"
    return KnowledgeClosureReport(
        subject_id=subject_id,
        requested_depth=depth,
        status=status,
        scalar_source_complete=record.coverage.scalar_source_complete,
        geometry_included=record.coverage.geometry_included,
        common_site_waveforms_included=record.coverage.waveform_summaries_included,
        artifact_dispositions=tuple(dispositions),
        derivations=derivations,
        path_modes=tuple(sorted(PATH_ARTIFACTS)),
        unavailable_categories=unavailable,
        unresolved=tuple(unresolved),
    )


__all__ = ["KnowledgeClosureReport", "closure_report"]
