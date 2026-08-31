"""Disease-aware finite-volume execution on a transformed arterial network.

This module deliberately leaves :class:`NativeOneDSolver` untouched. It
reuses the verified healthy numerical core while adding explicit, distributed
excess pressure-loss terms required by focal disease models.
"""

from __future__ import annotations

from collections import defaultdict
import math

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.errors import NumericalMethodError

from .boundaries import root_boundary_state, terminal_boundary_state
from .convergence import periodicity_error
from .finite_volume import (
    _apply_floor,
    _initial_state,
    _segment_rhs,
    _stability_dt,
    _terminal_mass_balance,
)
from .junctions import internal_junction_states
from .losses import LocalizedPressureLoss
from .model import ForwardSolution, SegmentSolution, SolverDiagnostics, SolverOptions
from .network import NetworkDiscretization, ThinWallLaw, VoigtWallLaw


def _losses_by_segment(
    network: NetworkDiscretization,
    losses: tuple[LocalizedPressureLoss, ...],
) -> dict[str, tuple[LocalizedPressureLoss, ...]]:
    grouped: dict[str, list[LocalizedPressureLoss]] = defaultdict(list)
    for loss in losses:
        if not isinstance(loss, LocalizedPressureLoss):
            raise TypeError("pressure_losses must contain LocalizedPressureLoss values")
        mesh = network.mesh(loss.segment_id)
        if loss.weights_per_m.shape != mesh.dx_m.shape:
            raise ValueError(
                f"pressure-loss weights for segment {loss.segment_id!r} do not match its mesh"
            )
        integral = float(np.sum(loss.weights_per_m * mesh.dx_m))
        if not math.isclose(integral, 1.0, rel_tol=1e-8, abs_tol=1e-10):
            raise ValueError(
                f"pressure-loss weights for segment {loss.segment_id!r} must integrate to one"
            )
        grouped[loss.segment_id].append(loss)
    return {segment_id: tuple(items) for segment_id, items in grouped.items()}


def _apply_pressure_losses(
    rhs: np.ndarray,
    conserved: np.ndarray,
    baseline: BaselineCardiovascularState,
    losses: tuple[LocalizedPressureLoss, ...],
) -> np.ndarray:
    """Apply signed distributed pressure losses to the momentum equation.

    The non-inertial part opposes the local direction of flow. An optional
    inertance term is represented as a local momentum mass factor, avoiding an
    explicit numerical derivative of flow.
    """

    if not losses:
        return rhs
    area = conserved[0]
    flow = conserved[1]
    rho = baseline.blood_density_kg_per_m3
    pressure_gradient = np.zeros_like(flow)
    inertance_density = np.zeros_like(flow)
    for loss in losses:
        pressure_gradient += loss.weights_per_m * (
            loss.linear_resistance_pa_s_per_m3 * flow
            + loss.quadratic_resistance_pa_s2_per_m6 * flow * np.abs(flow)
        )
        inertance_density += loss.weights_per_m * loss.inertance_pa_s2_per_m3

    mass_factor = 1.0 + area / rho * inertance_density
    if np.any(mass_factor <= 0) or not np.all(np.isfinite(mass_factor)):
        raise NumericalMethodError("disease pressure loss produced invalid momentum mass factor")
    result = rhs.copy()
    result[1] = (
        rhs[1] - area / rho * pressure_gradient
    ) / mass_factor
    return result


def _loss_stability_dt(
    conserved: dict[str, np.ndarray],
    network: NetworkDiscretization,
    baseline: BaselineCardiovascularState,
    options: SolverOptions,
    loss_map: dict[str, tuple[LocalizedPressureLoss, ...]],
) -> float:
    """Return an explicit-source time-step bound for resistive disease losses."""

    dt = float("inf")
    rho = baseline.blood_density_kg_per_m3
    for segment_id, losses in loss_map.items():
        mesh = network.mesh(segment_id)
        values = conserved[segment_id]
        area = values[0]
        flow = values[1]
        resistance_density = np.zeros_like(flow)
        inertance_density = np.zeros_like(flow)
        for loss in losses:
            resistance_density += loss.weights_per_m * (
                loss.linear_resistance_pa_s_per_m3
                + 2.0 * loss.quadratic_resistance_pa_s2_per_m6 * np.abs(flow)
            )
            inertance_density += loss.weights_per_m * loss.inertance_pa_s2_per_m3
        denominator = 1.0 + area / rho * inertance_density
        rate = area / rho * resistance_density / denominator
        maximum_rate = float(np.max(rate))
        if maximum_rate > 0:
            dt = min(dt, options.cfl / maximum_rate)
    return dt


def _rhs(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    conserved: dict[str, np.ndarray],
    capacitor_pressures: dict[str, float],
    time_s: float,
    loss_map: dict[str, tuple[LocalizedPressureLoss, ...]],
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
        healthy_rhs = _segment_rhs(
            conserved[sid],
            network.mesh(sid),
            baseline,
            inlet,
            outlet,
        )
        derivatives[sid] = _apply_pressure_losses(
            healthy_rhs,
            conserved[sid],
            baseline,
            loss_map.get(sid, ()),
        )
    return derivatives, pc_rhs


def _rk2_step(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    conserved: dict[str, np.ndarray],
    capacitor_pressures: dict[str, float],
    time_s: float,
    dt: float,
    options: SolverOptions,
    loss_map: dict[str, tuple[LocalizedPressureLoss, ...]],
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    k1, pc1 = _rhs(
        baseline, network, conserved, capacitor_pressures, time_s, loss_map
    )
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
    k2, pc2 = _rhs(
        baseline, network, stage, pc_stage, time_s + dt, loss_map
    )
    updated = {
        sid: _apply_floor(
            0.5 * (conserved[sid] + stage[sid] + dt * k2[sid]),
            network.mesh(sid),
            options.area_floor_ratio,
        )
        for sid in conserved
    }
    pc_updated = {
        sid: 0.5 * (capacitor_pressures[sid] + pc_stage[sid] + dt * pc2[sid])
        for sid in capacitor_pressures
    }
    return updated, pc_updated


class DiseaseOneDSolver:
    """Execute a causal disease-transformed network with the PR-2 solver core."""

    __slots__ = ("_options",)

    def __init__(self, options: SolverOptions | None = None) -> None:
        self._options = SolverOptions() if options is None else options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("options must be SolverOptions")

    @property
    def options(self) -> SolverOptions:
        return self._options

    def solve(
        self,
        baseline: BaselineCardiovascularState,
        network: NetworkDiscretization,
        *,
        pressure_losses: tuple[LocalizedPressureLoss, ...] = (),
    ) -> ForwardSolution:
        if not isinstance(baseline, BaselineCardiovascularState):
            raise TypeError("baseline must be a BaselineCardiovascularState")
        if not isinstance(network, NetworkDiscretization):
            raise TypeError("network must be a NetworkDiscretization")
        if not isinstance(pressure_losses, tuple):
            raise TypeError("pressure_losses must be a tuple")
        if tuple(mesh.segment_id for mesh in network.meshes) != tuple(
            segment.segment_id for segment in baseline.segments
        ):
            raise ValueError("transformed network must preserve baseline segment identity and order")
        loss_map = _losses_by_segment(network, pressure_losses)
        conserved, capacitor = _initial_state(baseline, network)
        period = baseline.aortic_inflow.duration_s
        if abs(period - baseline.cardiac_period_s) > max(
            0.01, 0.02 * baseline.cardiac_period_s
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
            record_history = {sid: [values.copy()] for sid, values in conserved.items()}
            while phase < period - 1e-14:
                dt_stable, cfl_rate, diffusion_rate = _stability_dt(
                    conserved, network, baseline, self._options
                )
                loss_dt = _loss_stability_dt(
                    conserved, network, baseline, self._options, loss_map
                )
                dt = min(dt_stable, loss_dt, period - phase)
                if not math.isfinite(dt) or dt <= 0:
                    raise NumericalMethodError("disease solver determined invalid time step")
                maximum_cfl = max(maximum_cfl, cfl_rate * dt)
                maximum_diffusion_number = max(
                    maximum_diffusion_number, diffusion_rate * dt
                )
                conserved, capacitor = _rk2_step(
                    baseline,
                    network,
                    conserved,
                    capacitor,
                    cycle * period + phase,
                    dt,
                    self._options,
                    loss_map,
                )
                if any(not np.all(np.isfinite(values)) for values in conserved.values()):
                    raise NumericalMethodError("disease solver produced non-finite state")
                if any(
                    np.any(
                        values[0]
                        <= self._options.area_floor_ratio
                        * network.mesh(sid).reference_area_m2
                    )
                    for sid, values in conserved.items()
                ):
                    raise NumericalMethodError("disease solver reached its configured area floor")
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
            raise NumericalMethodError("disease solver produced no cycle history")

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
                float(np.min(area / mesh.reference_area_m2[None, :])),
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
                baseline, final_time_array, final_history
            ),
        )
        return ForwardSolution(
            time_s=final_time_array,
            segments=tuple(segment_solutions),
            diagnostics=diagnostics,
        )


__all__ = ["DiseaseOneDSolver"]
