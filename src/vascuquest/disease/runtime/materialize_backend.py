"""Backend-aware materialisation for accelerated Virtual Disease execution.

The historical :func:`materialize_subject` remains untouched and therefore
continues to use the frozen NumPy reference.  Cohort execution uses the helper
here when an explicit numerical backend is selected.
"""

from __future__ import annotations

import numpy as np

from vascuquest.api import DatasetSession
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.subject import VirtualSubject
from vascuquest.disease.baseline import PWDBBaselineAssembler
from vascuquest.disease.baseline.model import MMHG_TO_PA
from vascuquest.disease.model import DiseaseRunIdentity
from vascuquest.disease.physics import transform_disease
from vascuquest.disease.solver.backends import create_disease_solver, normalize_solver_backend
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.validation.reconstruction import PWDB_COMMON_SITE_MODEL_LOCATIONS
from vascuquest.errors import NumericalMethodError

from .materialize import (
    RuntimeSubjectState,
    _geometry_result,
    _resample_history,
    _scalar_result,
    _waveform_result,
)
from .quantities import status_mapping


def materialize_subject_with_backend(
    session: DatasetSession,
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject_id: str,
    assembler: PWDBBaselineAssembler,
    solver_options: SolverOptions | None = None,
    solver_backend: str = "numpy",
) -> RuntimeSubjectState:
    """Fork, transform, solve and materialise one subject with an explicit backend."""

    if not isinstance(session, DatasetSession):
        raise TypeError("session must be a DatasetSession")
    if not isinstance(runtime_identity, DatasetIdentity):
        raise TypeError("runtime_identity must be a DatasetIdentity")
    if not isinstance(run_identity, DiseaseRunIdentity):
        raise TypeError("run_identity must be a DiseaseRunIdentity")
    if subject_id not in run_identity.canonical_subject_ids:
        raise ValueError("subject_id is not a member of the disease run selection")
    if not isinstance(assembler, PWDBBaselineAssembler):
        raise TypeError("assembler must be a PWDBBaselineAssembler")
    options = SolverOptions() if solver_options is None else solver_options
    if not isinstance(options, SolverOptions):
        raise TypeError("solver_options must be SolverOptions or None")
    backend = normalize_solver_backend(solver_backend)

    baseline = assembler.assemble(session, subject_id)
    physics = transform_disease(
        baseline,
        run_identity.request.specification,
        options=options,
    )
    solver = create_disease_solver(options, backend=backend)
    solution = solver.solve(
        baseline,
        physics.network,
        pressure_losses=physics.pressure_losses,
    )
    if not solution.diagnostics.converged:
        raise NumericalMethodError(
            f"disease runtime subject {subject_id!r} did not reach periodic convergence"
        )

    runtime_subject = VirtualSubject(SubjectKey(runtime_identity, subject_id))
    subject_key = runtime_subject.key
    statuses = status_mapping(run_identity.request.specification.condition)
    results = []
    provenance_records = []

    for quantity, value in (
        ("age", baseline.age_years),
        ("heart_rate", baseline.heart_rate_bpm),
        ("stroke_volume", baseline.stroke_volume_ml),
        (
            "cardiac_output",
            baseline.heart_rate_bpm * baseline.stroke_volume_ml / 1000.0,
        ),
    ):
        result, record = _scalar_result(
            runtime_identity=runtime_identity,
            run_identity=run_identity,
            subject=subject_key,
            physics=physics,
            options=options,
            solution=solution,
            quantity=quantity,
            value=value,
            status=statuses[quantity],
        )
        results.append(result)
        provenance_records.append(record)

    geometry, geometry_provenance = _geometry_result(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject_key,
        physics=physics,
        options=options,
        solution=solution,
        status=statuses["vascular_geometry"],
    )
    results.append(geometry)
    provenance_records.append(geometry_provenance)

    target_time = np.asarray(baseline.aortic_inflow.time_s, dtype=float)
    brachial_pressure: np.ndarray | None = None
    for site_id, (segment_id, fraction) in PWDB_COMMON_SITE_MODEL_LOCATIONS.items():
        location = MeasurementSite(site_id)
        area, flow, pressure_pa = _resample_history(
            solution,
            segment_id,
            fraction,
            target_time,
        )
        pressure = pressure_pa / MMHG_TO_PA
        velocity = flow / area
        waveforms = {
            "pressure": pressure,
            "flow_velocity": velocity,
            "luminal_area": area,
            "flow_rate": flow,
        }
        for quantity, values in waveforms.items():
            result, record = _waveform_result(
                runtime_identity=runtime_identity,
                run_identity=run_identity,
                subject=subject_key,
                physics=physics,
                options=options,
                solution=solution,
                quantity=quantity,
                values=values,
                location=location,
                time_s=target_time,
                status=statuses[quantity],
                segment_id=segment_id,
            )
            results.append(result)
            provenance_records.append(record)
        if site_id == "Brachial":
            brachial_pressure = pressure

    if brachial_pressure is None:
        raise RuntimeError("canonical Brachial site is missing from runtime site mapping")
    brachial_location = MeasurementSite("Brachial")
    sbp, sbp_record = _scalar_result(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject_key,
        physics=physics,
        options=options,
        solution=solution,
        quantity="brachial_systolic_pressure",
        value=float(np.max(brachial_pressure)),
        status=statuses["brachial_systolic_pressure"],
        location=brachial_location,
    )
    results.append(sbp)
    provenance_records.append(sbp_record)

    return RuntimeSubjectState(
        subject=runtime_subject,
        baseline=baseline,
        physics=physics,
        solution=solution,
        results=tuple(results),
        provenance_records=tuple(provenance_records),
    )


__all__ = ["materialize_subject_with_backend"]
