"""Native finite-volume solver for healthy PWDB reconstruction.

The implementation solves the nonlinear 1-D area/flow system on the complete
PWDB network. It uses a second-order MUSCL reconstruction, an HLL-type
interface flux written in perturbation variables so the diastolic tapered
network is a discrete rest state, SSP-RK2 time stepping, characteristic
junction coupling, source PWDB Voigt-wall viscosity, and three-element
Windkessel terminal boundaries.
"""

from __future__ import annotations

import math

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.errors import NumericalMethodError

from .boundaries import root_boundary_state, terminal_boundary_state
from .convergence import periodicity_error
from .junctions import internal_junction_states
from .model import ForwardSolution, SegmentMesh, SegmentSolution, SolverDiagnostics, SolverOptions
from .network import NetworkDiscretization, ThinWallLaw, VoigtWallLaw, build_network


def _minmod(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    same_sign = np.sign(a) == np.sign(b)
    return np.where(
        same_sign,
        np.sign(a) * np.minimum(np.abs(a), np.abs(b)),
        0.0,
    )


def _flux_scalar(
    state: np.ndarray,
    reference_area: float,
    beta_pa: float,
    baseline: BaselineCardiovascularState,
) -> np.ndarray:
    area = float(state[0])
    flow = float(state[1])
    if area <= 0:
        raise NumericalMethodError("finite-volume flux received non-positive area")
    pressure_potential = float(
        ThinWallLaw.pressure_potential(
            area,
            reference_area,
            beta_pa,
            baseline.blood_density_kg_per_m3,
        )
    )
    return np.asarray(
        [
            flow,
            baseline.momentum_correction_alpha * flow * flow / area + pressure_potential,
        ],
        dtype=float,
    )


def _signal_speed_scalar(
    state: np.ndarray,
    reference_area: float,
    beta_pa: float,
    baseline: BaselineCardiovascularState,
) -> tuple[float, float]:
    area = float(state[0])
    flow = float(state[1])
    velocity = flow / area
    c = float(
        ThinWallLaw.wave_speed_m_per_s(
            area,
            reference_area,
            beta_pa,
            baseline.blood_density_kg_per_m3,
        )
    )
    alpha = baseline.momentum_correction_alpha
    radical = math.sqrt(c * c + alpha * (alpha - 1.0) * velocity * velocity)
    center = alpha * velocity
    return center - radical, center + radical


def _hll_pair(
    left: np.ndarray,
    right: np.ndarray,
    left_a0: float,
    right_a0: float,
    left_beta: float,
    right_beta: float,
    baseline: BaselineCardiovascularState,
) -> np.ndarray:
    """HLL-type flux using perturbation-state dissipation.

    Dissipation is applied to ``(A-A_d, Q)`` instead of raw ``(A,Q)``. This
    prevents a tapered artery at uniform diastolic pressure from generating a
    spurious mass flux solely because adjacent cells have different reference
    areas.
    """

    fl = _flux_scalar(left, left_a0, left_beta, baseline)
    fr = _flux_scalar(right, right_a0, right_beta, baseline)
    sl_l, sr_l = _signal_speed_scalar(left, left_a0, left_beta, baseline)
    sl_r, sr_r = _signal_speed_scalar(right, right_a0, right_beta, baseline)
    s_left = min(sl_l, sl_r, 0.0)
    s_right = max(sr_l, sr_r, 0.0)
    if s_left >= 0.0:
        return fl
    if s_right <= 0.0:
        return fr
    if s_right - s_left <= 1e-14:
        return 0.5 * (fl + fr)
    jump = np.asarray(
        [right[0] - right_a0 - (left[0] - left_a0), right[1] - left[1]],
        dtype=float,
    )
    return (s_right * fl - s_left * fr + s_left * s_right * jump) / (
        s_right - s_left
    )


def _friction_source(
    conserved: np.ndarray,
    baseline: BaselineCardiovascularState,
) -> np.ndarray:
    alpha = baseline.momentum_correction_alpha
    if alpha <= 1.0:
        zeta = 9.0
    else:
        zeta = max((2.0 - alpha) / (alpha - 1.0), 0.0)
    nu = baseline.blood_viscosity_pa_s / baseline.blood_density_kg_per_m3
    source = np.zeros_like(conserved)
    source[1] = (
        -2.0
        * math.pi
        * nu
        * (zeta + 2.0)
        * conserved[1]
        / conserved[0]
    )
    return source


def _voigt_source(
    conserved: np.ndarray,
    mesh: SegmentMesh,
    baseline: BaselineCardiovascularState,
    inlet_state: tuple[float, float],
    outlet_state: tuple[float, float],
) -> np.ndarray:
    """Explicit momentum contribution of the source Voigt wall coefficient."""

    cells = mesh.cell_count
    q = conserved[1]
    area = conserved[0]
    face_gradient = np.empty(cells + 1, dtype=float)
    face_area = np.empty(cells + 1, dtype=float)
    face_gamma = np.empty(cells + 1, dtype=float)

    face_gradient[0] = (q[0] - inlet_state[1]) / mesh.dx_m[0]
    face_area[0] = 0.5 * (area[0] + inlet_state[0])
    face_gamma[0] = mesh.source_gamma_pa_s_per_m[0]

    if cells > 1:
        center_distance = 0.5 * (mesh.dx_m[:-1] + mesh.dx_m[1:])
        face_gradient[1:-1] = (q[1:] - q[:-1]) / center_distance
        face_area[1:-1] = 0.5 * (area[1:] + area[:-1])
        face_gamma[1:-1] = 0.5 * (
            mesh.source_gamma_pa_s_per_m[1:]
            + mesh.source_gamma_pa_s_per_m[:-1]
        )

    face_gradient[-1] = (outlet_state[1] - q[-1]) / mesh.dx_m[-1]
    face_area[-1] = 0.5 * (area[-1] + outlet_state[0])
    face_gamma[-1] = mesh.source_gamma_pa_s_per_m[-1]

    psi = face_gamma * face_gradient / np.sqrt(np.maximum(face_area, 1e-18))
    source = np.zeros_like(conserved)
    source[1] = (
        area
        / baseline.blood_density_kg_per_m3
        * (psi[1:] - psi[:-1])
        / mesh.dx_m
    )
    return source


def _segment_rhs(
    conserved: np.ndarray,
    mesh: SegmentMesh,
    baseline: BaselineCardiovascularState,
    inlet_state: tuple[float, float],
    outlet_state: tuple[float, float],
) -> np.ndarray:
    cells = mesh.cell_count
    perturbation = np.vstack(
        (conserved[0] - mesh.reference_area_m2, conserved[1])
    )
    slopes = np.zeros_like(perturbation)
    if cells > 2:
        backward = perturbation[:, 1:-1] - perturbation[:, :-2]
        forward = perturbation[:, 2:] - perturbation[:, 1:-1]
        slopes[:, 1:-1] = _minmod(backward, forward)

    left_perturb = perturbation - 0.5 * slopes
    right_perturb = perturbation + 0.5 * slopes
    left_face = np.vstack(
        (mesh.reference_area_m2 + left_perturb[0], left_perturb[1])
    )
    right_face = np.vstack(
        (mesh.reference_area_m2 + right_perturb[0], right_perturb[1])
    )
    floor = 1e-12
    left_face[0] = np.maximum(left_face[0], floor)
    right_face[0] = np.maximum(right_face[0], floor)

    fluxes = np.zeros((2, cells + 1), dtype=float)
    inlet = np.asarray(inlet_state, dtype=float)
    outlet = np.asarray(outlet_state, dtype=float)
    fluxes[:, 0] = _hll_pair(
        inlet,
        left_face[:, 0],
        float(mesh.reference_area_m2[0]),
        float(mesh.reference_area_m2[0]),
        float(mesh.beta_pa[0]),
        float(mesh.beta_pa[0]),
        baseline,
    )
    for index in range(cells - 1):
        fluxes[:, index + 1] = _hll_pair(
            right_face[:, index],
            left_face[:, index + 1],
            float(mesh.reference_area_m2[index]),
            float(mesh.reference_area_m2[index + 1]),
            float(mesh.beta_pa[index]),
            float(mesh.beta_pa[index + 1]),
            baseline,
        )
    fluxes[:, -1] = _hll_pair(
        right_face[:, -1],
        outlet,
        float(mesh.reference_area_m2[-1]),
        float(mesh.reference_area_m2[-1]),
        float(mesh.beta_pa[-1]),
        float(mesh.beta_pa[-1]),
        baseline,
    )

    rhs = -(fluxes[:, 1:] - fluxes[:, :-1]) / mesh.dx_m
    rhs += _friction_source(conserved, baseline)
    rhs += _voigt_source(conserved, mesh, baseline, inlet_state, outlet_state)
    return rhs


def _stability_dt(
    conserved: dict[str, np.ndarray],
    network: NetworkDiscretization,
    baseline: BaselineCardiovascularState,
    options: SolverOptions,
) -> tuple[float, float, float]:
    dt = float("inf")
    max_cfl_rate = 0.0
    max_diffusion_rate = 0.0
    rho = baseline.blood_density_kg_per_m3
    for segment_id, values in conserved.items():
        mesh = network.mesh(segment_id)
        area = values[0]
        flow = values[1]
        velocity = flow / area
        c = ThinWallLaw.wave_speed_m_per_s(
            area,
            mesh.reference_area_m2,
            mesh.beta_pa,
            rho,
        )
        alpha = baseline.momentum_correction_alpha
        radical = np.sqrt(c * c + alpha * (alpha - 1.0) * velocity * velocity)
        speed = np.maximum(
            np.abs(alpha * velocity - radical),
            np.abs(alpha * velocity + radical),
        )
        hyperbolic_rate = speed / mesh.dx_m
        max_cfl_rate = max(max_cfl_rate, float(np.max(hyperbolic_rate)))
        dt = min(
            dt,
            float(options.cfl / max(float(np.max(hyperbolic_rate)), 1e-12)),
        )

        diffusion = mesh.source_gamma_pa_s_per_m * np.sqrt(area) / rho
        diffusion_rate = 2.0 * diffusion / (mesh.dx_m * mesh.dx_m)
        max_diffusion_rate = max(
            max_diffusion_rate,
            float(np.max(diffusion_rate)),
        )
        if np.max(diffusion_rate) > 0:
            dt = min(
                dt,
                float(options.diffusion_safety / np.max(diffusion_rate)),
            )

    if not math.isfinite(dt) or dt <= 0:
        raise NumericalMethodError(
            "unable to determine a positive finite stability time step"
        )
    return dt, max_cfl_rate, max_diffusion_rate


def _rhs(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    conserved: dict[str, np.ndarray],
    capacitor_pressures: dict[str, float],
    time_s: float,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    boundaries = internal_junction_states(baseline, network, conserved)
    boundaries[("1", "inlet")] = root_boundary_state(
        baseline,
        network.mesh("1"),
        conserved["1"],
        time_s,
    )

    pc_rhs: dict[str, float] = {}
    for segment in baseline.segments:
        if segment.segment_id not in capacitor_pressures:
            continue
        boundary, derivative = terminal_boundary_state(
            baseline,
            segment,
            network.mesh(segment.segment_id),
            conserved[segment.segment_id],
            capacitor_pressures[segment.segment_id],
        )
        boundaries[(segment.segment_id, "outlet")] = boundary
        pc_rhs[segment.segment_id] = derivative

    derivatives: dict[str, np.ndarray] = {}
    for segment in baseline.segments:
        sid = segment.segment_id
        inlet = boundaries.get((sid, "inlet"))
        outlet = boundaries.get((sid, "outlet"))
        if inlet is None or outlet is None:
            raise NumericalMethodError(f"missing boundary state for segment {sid!r}")
        derivatives[sid] = _segment_rhs(
            conserved[sid],
            network.mesh(sid),
            baseline,
            inlet,
            outlet,
        )
    return derivatives, pc_rhs


def _apply_floor(values: np.ndarray, mesh: SegmentMesh, ratio: float) -> np.ndarray:
    result = values.copy()
    result[0] = np.maximum(result[0], ratio * mesh.reference_area_m2)
    return result


def _rk2_step(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    conserved: dict[str, np.ndarray],
    capacitor_pressures: dict[str, float],
    time_s: float,
    dt: float,
    options: SolverOptions,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    k1, pc1 = _rhs(baseline, network, conserved, capacitor_pressures, time_s)
    stage = {
        sid: _apply_floor(
            conserved[sid] + dt * k1[sid],
            network.mesh(sid),
            options.area_floor_ratio,
        )
        for sid in conserved
    }
    pc_stage = {
        sid: capacitor_pressures[sid] + dt * pc1[sid]
        for sid in capacitor_pressures
    }
    k2, pc2 = _rhs(baseline, network, stage, pc_stage, time_s + dt)
    updated = {
        sid: _apply_floor(
            0.5 * (conserved[sid] + stage[sid] + dt * k2[sid]),
            network.mesh(sid),
            options.area_floor_ratio,
        )
        for sid in conserved
    }
    pc_updated = {
        sid: 0.5 * (
            capacitor_pressures[sid] + pc_stage[sid] + dt * pc2[sid]
        )
        for sid in capacitor_pressures
    }
    return updated, pc_updated


def _initial_state(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    conserved: dict[str, np.ndarray] = {}
    for mesh in network.meshes:
        values = np.zeros((2, mesh.cell_count), dtype=float)
        values[0] = mesh.reference_area_m2
        conserved[mesh.segment_id] = values
    capacitor = {
        segment_id: baseline.diastolic_pressure_pa
        for segment_id in baseline.terminal_segment_ids
    }
    return conserved, capacitor


def _mean_over_cycle(time: np.ndarray, values: np.ndarray) -> float:
    duration = float(time[-1] - time[0])
    if duration <= 0:
        raise NumericalMethodError("final-cycle history has non-positive duration")
    return float(np.trapezoid(values, time) / duration)


def _terminal_mass_balance(
    baseline: BaselineCardiovascularState,
    time: np.ndarray,
    histories: dict[str, list[np.ndarray]],
) -> float:
    root_mean = baseline.aortic_inflow.mean_flow_m3_per_s
    terminal_mean = 0.0
    for sid in baseline.terminal_segment_ids:
        history = np.stack(histories[sid], axis=0)
        terminal_mean += _mean_over_cycle(time, history[:, 1, -1])
    scale = max(abs(root_mean), 1e-12)
    return abs(root_mean - terminal_mean) / scale


class NativeOneDSolver:
    """Independent NumPy implementation of the healthy PWDB 1-D network core."""

    __slots__ = ("_options",)

    def __init__(self, options: SolverOptions | None = None) -> None:
        self._options = SolverOptions() if options is None else options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("options must be SolverOptions")

    @property
    def options(self) -> SolverOptions:
        return self._options

    def solve(self, baseline: BaselineCardiovascularState) -> ForwardSolution:
        if not isinstance(baseline, BaselineCardiovascularState):
            raise TypeError("baseline must be a BaselineCardiovascularState")
        network = build_network(baseline, self._options)
        conserved, capacitor = _initial_state(baseline, network)
        period = baseline.aortic_inflow.duration_s
        if abs(period - baseline.cardiac_period_s) > max(
            0.01,
            0.02 * baseline.cardiac_period_s,
        ):
            raise NumericalMethodError(
                "source aortic inflow duration is inconsistent with subject heart rate"
            )

        convergence = float("inf")
        maximum_cfl = 0.0
        maximum_diffusion_number = 0.0
        final_times: list[float] = []
        final_history: dict[str, list[np.ndarray]] = {}
        converged = False
        cycles_completed = 0

        for cycle in range(self._options.maximum_cycles):
            start = {sid: values.copy() for sid, values in conserved.items()}
            phase = 0.0
            record_times = [0.0]
            record_history = {
                sid: [values.copy()] for sid, values in conserved.items()
            }
            while phase < period - 1e-14:
                dt_stable, cfl_rate, diffusion_rate = _stability_dt(
                    conserved,
                    network,
                    baseline,
                    self._options,
                )
                dt = min(dt_stable, period - phase)
                maximum_cfl = max(maximum_cfl, cfl_rate * dt)
                maximum_diffusion_number = max(
                    maximum_diffusion_number,
                    diffusion_rate * dt,
                )
                conserved, capacitor = _rk2_step(
                    baseline,
                    network,
                    conserved,
                    capacitor,
                    cycle * period + phase,
                    dt,
                    self._options,
                )
                if any(
                    not np.all(np.isfinite(values))
                    for values in conserved.values()
                ):
                    raise NumericalMethodError(
                        "native 1-D solver produced non-finite state"
                    )
                if any(
                    np.any(
                        values[0]
                        <= self._options.area_floor_ratio
                        * network.mesh(sid).reference_area_m2
                    )
                    for sid, values in conserved.items()
                ):
                    raise NumericalMethodError(
                        "native 1-D solver reached its configured area floor"
                    )
                phase += dt
                record_times.append(phase)
                for sid, values in conserved.items():
                    record_history[sid].append(values.copy())

            cycles_completed = cycle + 1
            convergence = periodicity_error(start, conserved)
            final_times = record_times
            final_history = record_history
            if (
                cycles_completed >= self._options.minimum_cycles
                and convergence <= self._options.periodicity_tolerance
            ):
                converged = True
                break

        if not final_times or not final_history:
            raise NumericalMethodError("native 1-D solver produced no cycle history")

        final_time_array = np.asarray(final_times, dtype=float)
        segment_solutions: list[SegmentSolution] = []
        minimum_area_ratio = float("inf")
        for segment in baseline.segments:
            sid = segment.segment_id
            mesh = network.mesh(sid)
            history = np.stack(final_history[sid], axis=0)
            area = history[:, 0, :]
            flow = history[:, 1, :]
            elastic_pressure = ThinWallLaw.pressure_pa(
                area,
                mesh.reference_area_m2[None, :],
                mesh.beta_pa[None, :],
                baseline.diastolic_pressure_pa,
            )
            pressure = VoigtWallLaw.total_pressure_pa(
                elastic_pressure,
                area,
                flow,
                mesh.x_m,
                mesh.source_gamma_pa_s_per_m,
            )
            minimum_area_ratio = min(
                minimum_area_ratio,
                float(
                    np.min(
                        area / mesh.reference_area_m2[None, :]
                    )
                ),
            )
            segment_solutions.append(
                SegmentSolution(
                    segment_id=sid,
                    x_m=mesh.x_m,
                    area_m2=area,
                    flow_m3_per_s=flow,
                    pressure_pa=pressure,
                )
            )

        diagnostics = SolverDiagnostics(
            cycles_completed=cycles_completed,
            periodicity_error=convergence,
            converged=converged,
            minimum_area_ratio=minimum_area_ratio,
            maximum_cfl=maximum_cfl,
            maximum_diffusion_number=maximum_diffusion_number,
            terminal_mass_balance_relative_error=_terminal_mass_balance(
                baseline,
                final_time_array,
                final_history,
            ),
        )
        return ForwardSolution(
            time_s=final_time_array,
            segments=tuple(segment_solutions),
            diagnostics=diagnostics,
        )


__all__ = ["NativeOneDSolver"]
