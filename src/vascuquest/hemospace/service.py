"""HEMOSPACE record construction from verified PWDB artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

from vascuquest.backends.pwdb3275625.capabilities import PWDB_MEASUREMENT_SITE_IDS
from vascuquest.backends.pwdb3275625.csv_reader import SubjectCSVTable
from vascuquest.domain.location import MeasurementSite
from vascuquest.errors import VascuQuestError

from .catalogue import SCALAR_SOURCE_ARTIFACTS, UNAVAILABLE_BY_PWDB, semantics_for
from .model import KnowledgeCoverage, KnowledgeItem, UnavailableKnowledge, VirtualCardiovascularRecord


ArtifactResolver = Callable[[str], Path]
_ALLOWED_DEPTHS = frozenset({"scalar", "geometry", "comprehensive"})


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
        """Build the HEMOSPACE record for one canonical virtual subject."""

        if depth not in _ALLOWED_DEPTHS:
            raise ValueError(f"depth must be one of {sorted(_ALLOWED_DEPTHS)!r}")
        subject = self._session.subject(subject_id)
        subject_id = subject.canonical_subject_id

        items: list[KnowledgeItem] = []
        warnings: list[str] = []
        fields_seen = 0
        fields_exposed = 0
        fields_missing = 0
        table_names: list[str] = []

        for source_scope, artifact_id in SCALAR_SOURCE_ARTIFACTS:
            path = self._resolve(artifact_id)
            table = SubjectCSVTable(path)
            if subject_id not in table.subject_ids():
                raise ValueError(f"subject {subject_id!r} is absent from HEMOSPACE source {artifact_id!r}")
            table_names.append(source_scope)
            for source_field in table.fieldnames:
                if source_field == "Subject Number":
                    continue
                fields_seen += 1
                cell = table.numeric(subject_id, source_field)
                if cell.missing:
                    fields_missing += 1
                    continue
                semantics = semantics_for(source_scope, source_field)
                items.append(
                    KnowledgeItem(
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
                    )
                )
                fields_exposed += 1

        derived_before = len(items)
        items.extend(self._derive_scalar_knowledge(items))

        geometry_included = False
        if depth in {"geometry", "comprehensive"}:
            geometry_included = True
            try:
                items.extend(self._geometry_knowledge(subject_id))
            except VascuQuestError as exc:
                warnings.append(f"geometry unavailable: {exc}")
                geometry_included = False

        waveform_included = False
        if depth == "comprehensive":
            try:
                waveform_items, waveform_warnings = self._waveform_knowledge(subject_id)
                items.extend(waveform_items)
                warnings.extend(waveform_warnings)
                waveform_included = bool(waveform_items)
            except VascuQuestError as exc:
                warnings.append(f"common-site waveforms unavailable: {exc}")

        derived_items = sum(item.evidence != "SOURCE" for item in items)
        coverage = KnowledgeCoverage(
            source_fields_seen=fields_seen,
            source_fields_exposed=fields_exposed,
            source_fields_missing=fields_missing,
            source_tables=tuple(table_names),
            derived_items=derived_items,
            geometry_included=geometry_included,
            waveform_summaries_included=waveform_included,
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

    def _derive_scalar_knowledge(self, source_items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        by_id = {item.canonical_id: item for item in source_items if item.value is not None}
        derived: list[KnowledgeItem] = []

        hr = by_id.get("haemodynamic_hr") or by_id.get("prescribed_heart_rate")
        sv = by_id.get("haemodynamic_sv") or by_id.get("prescribed_stroke_volume")
        co = by_id.get("haemodynamic_co")
        if hr is not None and float(hr.value) > 0:
            derived.append(KnowledgeItem(
                "cardiac_cycle_duration", "Cardiac-cycle duration", "cardiac",
                60.0 / float(hr.value), "s", "DERIVED",
                method="60 / heart_rate_bpm",
                assumptions=("Heart rate describes a periodic beat frequency in beats per minute.",),
            ))
        if hr is not None and sv is not None:
            co_reconstructed = float(hr.value) * float(sv.value) / 1000.0
            derived.append(KnowledgeItem(
                "cardiac_output_from_hr_sv", "Cardiac output reconstructed from HR and SV", "cardiac",
                co_reconstructed, "l/min", "RECONSTRUCTED",
                method="heart_rate_bpm * stroke_volume_ml / 1000",
            ))
            if co is not None and float(co.value) != 0:
                discrepancy = 100.0 * (co_reconstructed - float(co.value)) / float(co.value)
                derived.append(KnowledgeItem(
                    "cardiac_output_reconstruction_discrepancy", "CO reconstruction discrepancy", "quality_and_plausibility",
                    discrepancy, "%", "DERIVED",
                    method="100 * (CO_HR_SV - CO_source) / CO_source",
                    notes=("A consistency diagnostic, not a clinical abnormality score.",),
                ))

        field_map = {item.source_field: item for item in source_items if item.source_artifact == "haemodynamic_parameters" and item.source_field}
        for field, sbp_item in tuple(field_map.items()):
            if not field.startswith("SBP_"):
                continue
            suffix = field[len("SBP_"):].split(" ", 1)[0]
            dbp_field = field.replace("SBP_", "DBP_", 1)
            dbp_item = field_map.get(dbp_field)
            if dbp_item is None:
                continue
            derived.append(KnowledgeItem(
                f"reconstructed_pulse_pressure_{suffix.lower()}",
                f"Reconstructed pulse pressure ({suffix})", "pressure",
                float(sbp_item.value) - float(dbp_item.value), "mmHg", "RECONSTRUCTED",
                method="systolic_pressure - diastolic_pressure",
            ))

        mbp = by_id.get("haemodynamic_mbp_a") or by_id.get("haemodynamic_mbp")
        if mbp is not None and co is not None:
            watts = float(mbp.value) * 133.32236842105263 * float(co.value) / 60000.0
            derived.append(KnowledgeItem(
                "mean_systemic_hydraulic_power", "Mean systemic hydraulic power", "energetic",
                watts, "W", "DERIVED",
                method="mean_pressure_Pa * cardiac_output_m3_per_s",
                assumptions=("Uses mean arterial pressure and cardiac output as a system-level hydraulic-power approximation.",),
                notes=("This is hydraulic power, not myocardial metabolic power.",),
            ))
        return derived

    def _geometry_knowledge(self, subject_id: str) -> list[KnowledgeItem]:
        result = self._session.geometry(subject=subject_id)
        segments = tuple(result.values)
        structured: list[dict[str, Any]] = []
        total_length = 0.0
        volume = 0.0
        diameters: list[float] = []
        for segment in segments:
            if is_dataclass(segment):
                data = asdict(segment)
            else:
                data = {
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
            length = float(data["length_m"])
            r1 = float(data["inlet_radius_m"])
            r2 = float(data["outlet_radius_m"])
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

    @staticmethod
    def _wave_summary(values: object, times: object, missing_mask: object | None = None, padding_mask: object | None = None) -> dict[str, float]:
        array = np.asarray(values, dtype=float)
        time = np.asarray(times, dtype=float)
        valid = np.isfinite(array)
        if missing_mask is not None:
            valid &= ~np.asarray(missing_mask, dtype=bool)
        if padding_mask is not None:
            valid &= ~np.asarray(padding_mask, dtype=bool)
        if not np.any(valid):
            raise ValueError("waveform has no finite source samples")
        v = array[valid]
        t = time[valid]
        peak_index = int(np.argmax(v))
        return {
            "min": float(np.min(v)),
            "max": float(np.max(v)),
            "mean": float(np.mean(v)),
            "amplitude": float(np.max(v) - np.min(v)),
            "time_to_max_s": float(t[peak_index]),
        }

    def _waveform_knowledge(self, subject_id: str) -> tuple[list[KnowledgeItem], list[str]]:
        items: list[KnowledgeItem] = []
        warnings: list[str] = []
        signal_units = {"pressure": "mmHg", "flow_velocity": "m/s", "luminal_area": "m^2", "photoplethysmogram": "au"}
        for site_id in PWDB_MEASUREMENT_SITE_IDS:
            location = MeasurementSite(site_id)
            for signal, unit in signal_units.items():
                try:
                    wave = self._session.waveform(signal, subject=subject_id, location=location)
                    times = wave.coordinates[0].values
                    summary = self._wave_summary(wave.values, times, wave.missing_mask, wave.padding_mask)
                    items.append(KnowledgeItem(
                        f"waveform_summary_{site_id.lower()}_{signal}",
                        f"{site_id} {signal.replace('_', ' ')} waveform summary", "waveform_morphology",
                        summary, unit, "DERIVED", source_artifact="common_site_waveforms_csv", source_field=wave.source_label,
                        location=site_id, method="finite source waveform summary; raw waveform remains available through VascuQuest",
                    ))
                except (VascuQuestError, ValueError) as exc:
                    warnings.append(f"{site_id}:{signal} summary unavailable: {exc}")
            try:
                flow = self._session.derive("vascuquest:flow-rate-reconstruction", subjects=subject_id, location=location)
                times = flow.coordinates[0].values
                summary = self._wave_summary(flow.values, times)
                array = np.asarray(flow.values, dtype=float)
                time = np.asarray(times, dtype=float)
                finite = np.isfinite(array) & np.isfinite(time)
                if np.count_nonzero(finite) >= 2:
                    summary["cycle_volume_m3"] = float(np.trapezoid(array[finite], time[finite]))
                items.append(KnowledgeItem(
                    f"flow_rate_summary_{site_id.lower()}", f"{site_id} volumetric-flow summary", "flow",
                    summary, "m^3/s", "RECONSTRUCTED", location=site_id,
                    method="vascuquest:flow-rate-reconstruction (Q=U*A), followed by deterministic waveform summary",
                ))
            except (VascuQuestError, ValueError) as exc:
                warnings.append(f"{site_id}:flow-rate summary unavailable: {exc}")
        return items, warnings


__all__ = ["ArtifactResolver", "HemospaceSession"]
