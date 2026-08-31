"""Assemble a complete solver-ready healthy PWDB state without changing PWDB."""

from __future__ import annotations

from vascuquest.api import DatasetSession
from vascuquest.data import ArtifactAcquirer
from vascuquest.errors import AdmissibilityError

from .inflow import source_aortic_inflow
from .model import BaselineCardiovascularState, BaselineSegment
from .pwdb_reader import PWDBModelConfigurationReader


class PWDBBaselineAssembler:
    """Reconstruct one healthy subject using verified canonical PWDB artifacts."""

    __slots__ = ("_acquirer", "_offline")

    def __init__(self, acquirer: ArtifactAcquirer, *, offline: bool = False) -> None:
        if not isinstance(acquirer, ArtifactAcquirer):
            raise TypeError("acquirer must be an ArtifactAcquirer")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        self._acquirer = acquirer
        self._offline = offline

    def assemble(self, session: DatasetSession, subject_id: str) -> BaselineCardiovascularState:
        if not isinstance(session, DatasetSession):
            raise TypeError("session must be a DatasetSession")
        if session.identity.dataset_family != "PWDB" or session.identity.record_id != "3275625":
            raise AdmissibilityError("Virtual Disease PR-2 baseline assembly requires canonical PWDB 3275625")
        subject = session.subject(subject_id)

        config_path = self._acquirer.acquire("model_configurations", offline=self._offline)
        config = PWDBModelConfigurationReader(config_path).read_subject(subject.canonical_subject_id)

        geometry = session.geometry(subject=subject.canonical_subject_id)
        source_segments = tuple(geometry.values)
        if not source_segments:
            raise AdmissibilityError("PWDB geometry returned no arterial segments")
        segments = tuple(
            BaselineSegment(
                segment_id=str(item.segment_id),
                inlet_node=int(item.inlet_node),
                outlet_node=int(item.outlet_node),
                length_m=float(item.length_m),
                inlet_radius_m=float(item.inlet_radius_m),
                outlet_radius_m=float(item.outlet_radius_m),
                peripheral_compliance_m3_per_pa=float(item.peripheral_c),
                peripheral_resistance_pa_s_per_m3=float(item.peripheral_r),
            )
            for item in source_segments
        )
        inflow = source_aortic_inflow(session, subject.canonical_subject_id)
        return BaselineCardiovascularState(
            dataset_identity=session.identity,
            canonical_subject_id=subject.canonical_subject_id,
            age_years=config.age_years,
            heart_rate_bpm=config.heart_rate_bpm,
            stroke_volume_ml=config.stroke_volume_ml,
            lvet_s=config.lvet_s,
            peak_flow_time_s=config.peak_flow_time_s,
            reverse_flow_volume_ml=config.reverse_flow_volume_ml,
            diastolic_pressure_pa=config.diastolic_pressure_pa,
            mean_pressure_pa=config.mean_pressure_pa,
            outlet_pressure_pa=config.outlet_pressure_pa,
            blood_density_kg_per_m3=config.blood_density_kg_per_m3,
            blood_viscosity_pa_s=config.blood_viscosity_pa_s,
            momentum_correction_alpha=config.momentum_correction_alpha,
            systemic_pvr_pa_s_per_m3=config.systemic_pvr_pa_s_per_m3,
            wall_gamma_b0_g_per_s=config.wall_gamma_b0_g_per_s,
            wall_gamma_b1_g_cm_per_s=config.wall_gamma_b1_g_cm_per_s,
            stiffness_k1_g_per_s2_per_cm=config.stiffness_k1_g_per_s2_per_cm,
            stiffness_k2_per_cm=config.stiffness_k2_per_cm,
            stiffness_k3_g_per_s2_per_cm=config.stiffness_k3_g_per_s2_per_cm,
            segments=segments,
            aortic_inflow=inflow,
            source_configuration_member=config.source_member,
            source_geometry_member=geometry.source_label or "geo.zip",
        )


__all__ = ["PWDBBaselineAssembler"]
