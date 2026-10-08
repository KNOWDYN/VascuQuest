"""HEMOSPACE record construction and operation facade over verified PWDB artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
import math
from pathlib import Path
from typing import Any

from vascuquest.backends.pwdb3275625.capabilities import PWDB_MEASUREMENT_SITE_IDS
from vascuquest.domain.location import MeasurementSite
from vascuquest.errors import VascuQuestError

from .catalogue import SCALAR_SOURCE_ARTIFACTS, UNAVAILABLE_BY_PWDB, semantics_for
from .derivations import site_derivations, wave_summary
from .model import KnowledgeCoverage, KnowledgeItem, UnavailableKnowledge, VirtualCardiovascularRecord
from .plausibility import reconstruct_plausibility
from .source_table import HemospaceSubjectCSVTable

ArtifactResolver = Callable[[str], Path]
_ALLOWED_DEPTHS = frozenset({"scalar", "geometry", "comprehensive"})
_SIGNAL_UNITS = {
    "pressure": "mmHg",
    "flow_velocity": "m/s",
    "luminal_area": "m^2",
    "photoplethysmogram": "au",
}


class HemospaceSession:
    """HEMOSPACE operation mode bound to one canonical VascuQuest dataset session."""

    __slots__ = ("_session", "_resolve")

    def __init__(self, dataset_session: object, artifact_resolver: ArtifactResolver) -> None:
        if not callable(artifact_resolver):
            raise TypeError("artifact_resolver must be callable")
        if not hasattr(dataset_session, "identity") or not hasattr(dataset_session, "subject"):
            raise TypeError("dataset_session must expose the VascuQuest DatasetSession contract")
        self._session = dataset_session
        self._resolve = artifact_resolver

    @property
    def identity(self) -> object:
        return self._session.identity

    def record(self, subject_id: str, *, depth: str = "scalar") -> VirtualCardiovascularRecord:
        if depth not in _ALLOWED_DEPTHS:
            raise ValueError(f"depth must be one of {sorted(_ALLOWED_DEPTHS)!r}")
        subject = self._session.subject(subject_id)
        subject_id = subject.canonical_subject_id

        items: list[KnowledgeItem] = [
            KnowledgeItem(
                canonical_id="model_population_sex_assumption",
                label="PWDB model-population sex assumption",
                section="identity_and_design",
                value="male",
                unit=None,
                evidence="SOURCE",
                source_artifact="common_site_waveforms_wfdb",
                source_field="WFDB record description <sex>",
                notes=(
                    "Encoded by the upstream PWDB exporter for every virtual recording.",
                    "This is a model-population assumption, not an observed biological attribute of a real patient.",
                ),
            )
        ]
        warnings: list[str] = []
        fields_seen = fields_exposed = fields_missing = 0
        table_names: list[str] = []

        for source_scope, artifact_id in SCALAR_SOURCE_ARTIFACTS:
            table = HemospaceSubjectCSVTable(self._resolve(artifact_id))
            if subject_id not in table.subject_ids():
                raise ValueError(f"subject {subject_id!r} is absent from HEMOSPACE source {artifact_id!r}")
            table_names.append(source_scope)
            for source_field in table.fieldnames:
                if source_field in {"Subject Number", "SUBJECT NUMBER"}:
                    continue
                fields_seen += 1
                cell = table.numeric(subject_id, source_field)
                if cell.missing:
                    fields_missing += 1
                    continue
                semantics = semantics_for(source_scope, source_field)
                items.append(KnowledgeItem(
                    canonical_id=semantics.canonical_id,
                    label=semantics.label,
                    section=semantics.section,
                    value=cell.value,
                    unit=semantics.unit,
                    evidence="SOURCE",
                    source_artifact=artifact_id,
                    source_field=source_field,
                    location=semantics.location,
                    notes=semantics.notes,
                ))
                fields_exposed += 1

        items.extend(self._derive_scalar_knowledge(items))
        plausibility = reconstruct_plausibility(items)
        if plausibility is not None:
            items.append(plausibility)

        geometry_included = False
        if depth in {"geometry", "comprehensive"}:
            try:
                items.extend(self._geometry_knowledge(subject_id))
                geometry_included = True
            except VascuQuestError as exc:
                warnings.append(f"geometry unavailable: {exc}")

        waveform_included = False
        waveform_expected = waveform_summarized = 0
        if depth == "comprehensive":
            waveform_expected = len(PWDB_MEASUREMENT_SITE_IDS) * len(_SIGNAL_UNITS)
            try:
                waveform_items, waveform_warnings, waveform_summarized = self._waveform_knowledge(subject_id)
                items.extend(waveform_items)
                warnings.extend(waveform_warnings)
                waveform_included = waveform_summarized > 0
            except VascuQuestError as exc:
                warnings.append(f"common-site waveforms unavailable: {exc}")

        coverage = KnowledgeCoverage(
            source_fields_seen=fields_seen,
            source_fields_exposed=fields_exposed,
            source_fields_missing=fields_missing,
            source_tables=tuple(table_names),
            derived_items=sum(item.evidence != "SOURCE" for item in items),
            geometry_included=geometry_included,
            waveform_summaries_included=waveform_included,
            common_site_waveforms_expected=waveform_expected,
            common_site_waveforms_summarized=waveform_summarized,
            path_access_modes=("aorta_brain", "aorta_finger", "aorta_foot", "aorta_r_subclavian"),
        )
        identity = self._session.identity
        unavailable = tuple(UnavailableKnowledge(key, reason) for key, reason in UNAVAILABLE_BY_PWDB)
        return VirtualCardiovascularRecord(
            dataset_family=identity.dataset_family,
            dataset_record_id=identity.record_id,
            dataset_identifier=identity.persistent_identifier,
            subject_id=subject_id,
            depth=depth,
            items=tuple(items),
            unavailable=unavailable,
            coverage=coverage,
            warnings=tuple(warnings),
        )

    def path(self, subject_id: str, path_name: str) -> object:
        from .path import path_profile
        self._session.subject(subject_id)
        return path_profile(self._resolve, subject_id, path_name)

    def select_cohort(self, criteria: tuple[object, ...] | list[object], *, profile_id: str | None = None) -> object:
        from .cohort import select_cohort
        return select_cohort(self, criteria, profile_id=profile_id)

    def describe_cohort(self, cohort: object, *, canonical_ids: tuple[str, ...] | None = None) -> dict[str, object]:
        from .cohort import describe_cohort
        return describe_cohort(self, cohort, canonical_ids=canonical_ids)

    def response(self, bundle: str | Path, subject_id: str) -> object:
        from .response import response_from_bundle
        self._session.subject(subject_id)
        return response_from_bundle(self, bundle, subject_id)

    def closure(self, subject_id: str, *, depth: str = "comprehensive") -> object:
        from .closure import closure_report
        self._session.subject(subject_id)
        return closure_report(self, subject_id, depth=depth)

    def agent_contract(self) -> dict[str, object]:
        from .agent import agent_contract
        return agent_contract()

    def _derive_scalar_knowledge(self, source_items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        by_id = {item.canonical_id: item for item in source_items if item.value is not None}
        derived: list[KnowledgeItem] = []
        hr = by_id.get("haemodynamic_hr") or by_id.get("prescribed_heart_rate")
        sv = by_id.get("haemodynamic_sv") or by_id.get("prescribed_stroke_volume")
        co = by_id.get("haemodynamic_co")
        if hr is not None and float(hr.value) > 0:
            derived.append(KnowledgeItem("cardiac_cycle_duration", "Cardiac-cycle duration", "cardiac", 60.0 / float(hr.value), "s", "DERIVED", method="60 / heart_rate_bpm", assumptions=("Heart rate describes a periodic beat frequency in beats per minute.",)))
        if hr is not None and sv is not None:
            co_reconstructed = float(hr.value) * float(sv.value) / 1000.0
            derived.append(KnowledgeItem("cardiac_output_from_hr_sv", "Cardiac output reconstructed from HR and SV", "cardiac", co_reconstructed, "l/min", "RECONSTRUCTED", method="heart_rate_bpm * stroke_volume_ml / 1000"))
            if co is not None and float(co.value) != 0:
                discrepancy = 100.0 * (co_reconstructed - float(co.value)) / float(co.value)
                derived.append(KnowledgeItem("cardiac_output_reconstruction_discrepancy", "CO reconstruction discrepancy", "quality_and_plausibility", discrepancy, "%", "DERIVED", method="100 * (CO_HR_SV - CO_source) / CO_source", notes=("A consistency diagnostic, not a clinical abnormality score.",)))

        field_map = {item.source_field: item for item in source_items if item.source_artifact == "haemodynamic_parameters" and item.source_field}
        for field, sbp_item in tuple(field_map.items()):
            if not field.startswith("SBP_"):
                continue
            suffix = field[len("SBP_"):].split(" ", 1)[0]
            dbp_item = field_map.get(field.replace("SBP_", "DBP_", 1))
            if dbp_item is not None:
                derived.append(KnowledgeItem(f"reconstructed_pulse_pressure_{suffix.lower()}", f"Reconstructed pulse pressure ({suffix})", "pressure", float(sbp_item.value) - float(dbp_item.value), "mmHg", "RECONSTRUCTED", method="systolic_pressure - diastolic_pressure"))

        mbp = by_id.get("haemodynamic_mbp_a") or by_id.get("haemodynamic_mbp")
        if mbp is not None and co is not None:
            watts = float(mbp.value) * 133.32236842105263 * float(co.value) / 60000.0
            derived.append(KnowledgeItem("mean_systemic_hydraulic_power", "Mean systemic hydraulic power", "energetic", watts, "W", "DERIVED", method="mean_pressure_Pa * cardiac_output_m3_per_s", assumptions=("Uses mean arterial pressure and cardiac output as a system-level hydraulic-power approximation.",), notes=("This is hydraulic power, not myocardial metabolic power.",)))
        return derived

    def _geometry_knowledge(self, subject_id: str) -> list[KnowledgeItem]:
        result = self._session.geometry(subject=subject_id)
        segments = tuple(result.values)
        structured: list[dict[str, Any]] = []
        total_length = volume = 0.0
        diameters: list[float] = []
        for segment in segments:
            data = asdict(segment) if is_dataclass(segment) else {
                "segment_id": segment.segment_id,
                "inlet_node": segment.inlet_node,
                "outlet_node": segment.outlet_node,
                "length_m": segment.length_m,
                "inlet_radius_m": segment.inlet_radius_m,
                "outlet_radius_m": segment.outlet_radius_m,
                "peripheral_c": segment.peripheral_c,
                "peripheral_r": segment.peripheral_r,
            }
            structured.append(data)
            length = float(data["length_m"]); r1 = float(data["inlet_radius_m"]); r2 = float(data["outlet_radius_m"])
            total_length += length
            volume += math.pi * length * (r1 * r1 + r1 * r2 + r2 * r2) / 3.0
            diameters.extend((2.0 * r1, 2.0 * r2))
        return [
            KnowledgeItem("vascular_geometry_segments", "Subject-specific vascular network geometry", "anatomy", structured, None, "SOURCE", source_artifact="geometry", source_field="geo.zip"),
            KnowledgeItem("vascular_segment_count", "Vascular segment count", "anatomy", len(segments), "1", "DERIVED", method="count(source geometry segments)"),
            KnowledgeItem("vascular_network_total_segment_length", "Total source-network segment length", "anatomy", total_length, "m", "DERIVED", method="sum(segment lengths)"),
            KnowledgeItem("vascular_network_min_diameter", "Minimum represented segment-end diameter", "anatomy", min(diameters), "m", "DERIVED", method="2 * min(source endpoint radii)"),
            KnowledgeItem("vascular_network_max_diameter", "Maximum represented segment-end diameter", "anatomy", max(diameters), "m", "DERIVED", method="2 * max(source endpoint radii)"),
            KnowledgeItem("vascular_network_frustum_volume", "Approximate represented arterial lumen volume", "anatomy", volume, "m^3", "DERIVED", method="sum(pi*L*(r_in^2+r_in*r_out+r_out^2)/3)", assumptions=("Each source segment is approximated as a circular conical frustum between endpoint radii.",)),
        ]

    def _waveform_knowledge(self, subject_id: str) -> tuple[list[KnowledgeItem], list[str], int]:
        items: list[KnowledgeItem] = []
        warnings: list[str] = []
        source_summaries = 0
        for site_id in PWDB_MEASUREMENT_SITE_IDS:
            location = MeasurementSite(site_id)
            waves: dict[str, object] = {}
            flow_wave: object | None = None
            for signal, unit in _SIGNAL_UNITS.items():
                try:
                    wave = self._session.waveform(signal, subject=subject_id, location=location)
                    summary = wave_summary(wave.values, wave.coordinates[0].values, wave.missing_mask, wave.padding_mask)
                    items.append(KnowledgeItem(f"waveform_summary_{site_id.lower()}_{signal}", f"{site_id} {signal.replace('_', ' ')} waveform summary", "waveform_morphology", summary, unit, "DERIVED", source_artifact="common_site_waveforms_csv", source_field=wave.source_label, location=site_id, method="finite source waveform summary; raw waveform remains available through VascuQuest"))
                    waves[signal] = wave
                    source_summaries += 1
                except (VascuQuestError, ValueError) as exc:
                    warnings.append(f"{site_id}:{signal} summary unavailable: {exc}")
            try:
                flow = self._session.derive("vascuquest:flow-rate-reconstruction", subjects=subject_id, location=location)
                flow_wave = flow
                summary = wave_summary(flow.values, flow.coordinates[0].values)
                summary["cycle_volume_m3"] = summary.pop("integral")
                items.append(KnowledgeItem(f"waveform_summary_{site_id.lower()}_flow_rate", f"{site_id} volumetric-flow waveform summary", "flow", summary, "m^3/s", "RECONSTRUCTED", location=site_id, method="vascuquest:flow-rate-reconstruction (Q=U*A), followed by deterministic waveform summary"))
            except (VascuQuestError, ValueError) as exc:
                warnings.append(f"{site_id}:flow-rate summary unavailable: {exc}")
            try:
                items.extend(site_derivations(site_id, waves, flow_wave))
            except ValueError as exc:
                warnings.append(f"{site_id}:derived waveform physiology unavailable: {exc}")
        return items, warnings, source_summaries


__all__ = ["ArtifactResolver", "HemospaceSession"]
