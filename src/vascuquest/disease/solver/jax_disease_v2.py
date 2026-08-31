"""Production JAX backend with adaptive long-cycle support and bounded replay.

This module preserves the numerical operators from :mod:`jax_disease` but
removes the prototype solver's fixed 500k-step/history-memory coupling.  The
adaptive SSP-RK2 integration path is unchanged.  A subject-specific safety cap
is estimated from the initial stability limit, while final-cycle output is
replayed onto the source waveform time grid with bounded memory.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.errors import NumericalMethodError

from .jax_disease import _flatten_problem, _initial_flat_state, _kernel_factory
from .losses import LocalizedPressureLoss
from .model import ForwardSolution, SegmentSolution, SolverDiagnostics, SolverOptions
from .network import NetworkDiscretization, ThinWallLaw, VoigtWallLaw

try:
    import jax
    import jax.numpy as jnp
    from jax import lax
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The JAX Virtual Disease backend requires the optional 'jax' dependency. "
        "Install VascuQuest with `pip install 'vascuquest[jax]'`."
    ) from exc

jax.config.update("jax_enable_x64", True)


@dataclass(frozen=True, slots=True)
class JaxSolverTiming:
    total_s: float
    first_cycle_compile_and_execute_s: float
    subsequent_cycles_execute_s: float
    final_cycle_replay_s: float
    history_compile_and_execute_s: float
    final_cycle_steps: int
    output_samples: int
    max_steps_per_cycle: int
    initial_stability_dt_s: float
    platform: str
    device: str
    x64_enabled: bool


def _derive_step_cap(period: float, initial_dt: float, configured: int | None) -> int:
    if configured is not None:
        if isinstance(configured, bool) or not isinstance(configured, int) or configured < 1:
            raise ValueError("max_steps_per_cycle must be a positive integer or None")
        return configured
    if not math.isfinite(initial_dt) or initial_dt <= 0.0:
        raise NumericalMethodError("JAX backend could not derive a positive initial stability time step")
    estimated = int(math.ceil(period / initial_dt))
    # Nonlinear stenosis losses can reduce dt after flow develops.  A generous
    # multiplicative guard is cheap because the cap is only a scalar loop guard;
    # no array is allocated with this length in the production replay path.
    return min(max(1_000_000, 16 * estimated + 4096), 50_000_000)


def _output_grid(baseline: BaselineCardiovascularState, period: float) -> np.ndarray:
    base = np.asarray(baseline.aortic_inflow.time_s, dtype=float)
    base = base - float(base[0])
    interior = base[(base > 0.0) & (base < period - 1e-13)]
    target = np.concatenate((np.asarray([0.0]), interior, np.asarray([period])))
    if target.size < 2 or not np.all(np.diff(target) > 0.0):
        raise NumericalMethodError("JAX output sampling grid is not strictly increasing")
    return target


def _sampled_replay_factory(
    baseline: BaselineCardiovascularState,
    problem,
    options: SolverOptions,
    rhs_fn,
    stability_fn,
    target_times: np.ndarray,
    max_steps_per_cycle: int,
):
    a0 = jnp.asarray(problem.a0_m2, dtype=jnp.float64)
    targets = jnp.asarray(target_times, dtype=jnp.float64)
    period = float(problem.period_s)
    floor_ratio = float(options.area_floor_ratio)
    sample_count = int(target_times.size)

    def apply_floor(U):
        return U.at[0].set(jnp.maximum(U[0], floor_ratio * a0))

    def rk2(U, pc, absolute_time, dt):
        k1, pc1 = rhs_fn(U, pc, absolute_time)
        stage = apply_floor(U + dt * k1)
        pc_stage = pc + dt * pc1
        k2, pc2 = rhs_fn(stage, pc_stage, absolute_time + dt)
        updated = apply_floor(0.5 * (U + stage + dt * k2))
        pc_updated = 0.5 * (pc + pc_stage + dt * pc2)
        return updated, pc_updated

    def replay(U0, pc0, absolute_start):
        history = jnp.zeros((sample_count,) + U0.shape, dtype=jnp.float64)
        history = history.at[0].set(U0)
        initial = (
            U0,
            pc0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(False, dtype=jnp.bool_),
            jnp.asarray(0, dtype=jnp.int32),
            jnp.asarray(1, dtype=jnp.int32),
            history,
        )

        def cond(carry):
            _, _, phase, invalid, steps, _, _ = carry
            return (phase < period - 1e-14) & (~invalid) & (steps < max_steps_per_cycle)

        def body(carry):
            U, pc, phase, invalid, steps, next_index, history = carry
            dt_stable, _, _, _ = stability_fn(U)
            dt = jnp.minimum(dt_stable, period - phase)
            invalid_dt = (~jnp.isfinite(dt)) | (dt <= 0.0)
            safe_dt = jnp.where(invalid_dt, 1e-12, dt)
            updated, pc_updated = rk2(U, pc, absolute_start + phase, safe_dt)
            phase_new = phase + safe_dt
            floor = floor_ratio * a0
            invalid_state = (
                (~jnp.all(jnp.isfinite(updated)))
                | (~jnp.all(jnp.isfinite(pc_updated)))
                | jnp.any(updated[0] <= floor)
            )

            fill_initial = (next_index, history)

            def fill_cond(fill):
                idx, _ = fill
                safe_idx = jnp.minimum(idx, sample_count - 1)
                return (idx < sample_count) & (targets[safe_idx] <= phase_new + 1e-14)

            def fill_body(fill):
                idx, hist = fill
                target = targets[idx]
                fraction = jnp.clip((target - phase) / safe_dt, 0.0, 1.0)
                sample = U + fraction * (updated - U)
                return idx + 1, hist.at[idx].set(sample)

            next_index, history = lax.while_loop(fill_cond, fill_body, fill_initial)
            return (
                updated,
                pc_updated,
                phase_new,
                invalid | invalid_dt | invalid_state,
                steps + 1,
                next_index,
                history,
            )

        return lax.while_loop(cond, body, initial)

    return jax.jit(replay)


class JaxDiseaseOneDSolver:
    """JIT-compiled Virtual Disease solver with bounded-memory final-cycle output."""

    __slots__ = ("_options", "_configured_cap", "_last_timing")

    def __init__(
        self,
        options: SolverOptions | None = None,
        *,
        max_steps_per_cycle: int | None = None,
    ) -> None:
        self._options = SolverOptions() if options is None else options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("options must be SolverOptions")
        if max_steps_per_cycle is not None and (
            isinstance(max_steps_per_cycle, bool)
            or not isinstance(max_steps_per_cycle, int)
            or max_steps_per_cycle < 1
        ):
            raise ValueError("max_steps_per_cycle must be a positive integer or None")
        self._configured_cap = max_steps_per_cycle
        self._last_timing: JaxSolverTiming | None = None

    @property
    def options(self) -> SolverOptions:
        return self._options

    @property
    def last_timing(self) -> JaxSolverTiming | None:
        return self._last_timing

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

        period = float(baseline.aortic_inflow.duration_s)
        if abs(period - baseline.cardiac_period_s) > max(0.01, 0.02 * baseline.cardiac_period_s):
            raise NumericalMethodError(
                "source aortic inflow duration is inconsistent with subject heart rate"
            )

        total_start = time.perf_counter()
        problem = _flatten_problem(baseline, network, pressure_losses)
        U, pc = _initial_flat_state(baseline, problem)

        # Compile/evaluate only the stability operator first.  This provides a
        # subject-specific cap without allocating any cap-sized history array.
        _, probe_stability, _, _, _ = _kernel_factory(
            baseline, problem, self._options, max_steps_per_cycle=2
        )
        initial_dt, _, _, _ = probe_stability(U)
        initial_dt.block_until_ready()
        initial_dt_value = float(np.asarray(initial_dt))
        max_steps = _derive_step_cap(period, initial_dt_value, self._configured_cap)

        rhs_fn, stability_fn, cycle_fn, _, _ = _kernel_factory(
            baseline, problem, self._options, max_steps
        )

        convergence = float("inf")
        maximum_cfl = 0.0
        maximum_diffusion = 0.0
        cycles_completed = 0
        converged = False
        first_cycle_wall = 0.0
        subsequent_cycle_wall = 0.0
        final_start_U = U
        final_start_pc = pc
        final_cycle_index = 0
        final_steps = 0

        for cycle in range(self._options.maximum_cycles):
            start_U = U
            start_pc = pc
            wall_start = time.perf_counter()
            U, pc, phase, cycle_cfl, cycle_diffusion, invalid, steps = cycle_fn(
                U, pc, jnp.asarray(cycle * period, dtype=jnp.float64)
            )
            U.block_until_ready()
            wall_elapsed = time.perf_counter() - wall_start
            if cycle == 0:
                first_cycle_wall = wall_elapsed
            else:
                subsequent_cycle_wall += wall_elapsed

            phase_value = float(np.asarray(phase))
            step_value = int(np.asarray(steps))
            if step_value >= max_steps and phase_value < period - 1e-12:
                raise NumericalMethodError(
                    "JAX disease solver exceeded adaptive safety cap before completing "
                    f"a cardiac cycle: steps={step_value}, cap={max_steps}, "
                    f"phase={phase_value:.9g}s, period={period:.9g}s, "
                    f"initial_dt={initial_dt_value:.9g}s"
                )
            if bool(np.asarray(invalid)):
                raise NumericalMethodError(
                    "JAX disease solver produced an invalid state or reached its configured area floor"
                )

            start_np = np.asarray(start_U, dtype=float)
            end_np = np.asarray(U, dtype=float)
            diff = end_np - start_np
            convergence = float(
                np.sqrt(float(np.sum(diff * diff)) / max(float(np.sum(start_np * start_np)), 1e-30))
            )
            maximum_cfl = max(maximum_cfl, float(np.asarray(cycle_cfl)))
            maximum_diffusion = max(maximum_diffusion, float(np.asarray(cycle_diffusion)))
            cycles_completed = cycle + 1
            final_start_U = start_U
            final_start_pc = start_pc
            final_cycle_index = cycle
            final_steps = step_value
            if (
                cycles_completed >= self._options.minimum_cycles
                and convergence <= self._options.periodicity_tolerance
            ):
                converged = True
                break

        target_time = _output_grid(baseline, period)
        replay_fn = _sampled_replay_factory(
            baseline,
            problem,
            self._options,
            rhs_fn,
            stability_fn,
            target_time,
            max_steps,
        )
        replay_start = time.perf_counter()
        replay_U, _, replay_phase, replay_invalid, replay_steps, replay_samples, history = replay_fn(
            final_start_U,
            final_start_pc,
            jnp.asarray(final_cycle_index * period, dtype=jnp.float64),
        )
        replay_U.block_until_ready()
        history.block_until_ready()
        replay_wall = time.perf_counter() - replay_start
        replay_count = int(np.asarray(replay_steps))
        replay_phase_value = float(np.asarray(replay_phase))
        if replay_count >= max_steps and replay_phase_value < period - 1e-12:
            raise NumericalMethodError("JAX sampled final-cycle replay exceeded adaptive safety cap")
        if bool(np.asarray(replay_invalid)):
            raise NumericalMethodError("JAX sampled final-cycle replay produced an invalid state")
        if int(np.asarray(replay_samples)) != target_time.size:
            raise NumericalMethodError("JAX sampled replay did not populate the complete output grid")
        if replay_count != final_steps:
            raise NumericalMethodError("JAX sampled replay changed the adaptive step count")

        history_np = np.asarray(history, dtype=float)
        segment_solutions: list[SegmentSolution] = []
        minimum_area_ratio = float("inf")
        terminal_flow_histories: list[np.ndarray] = []
        for index, (segment, mesh) in enumerate(zip(baseline.segments, network.meshes, strict=True)):
            start = int(problem.starts[index])
            end = int(problem.ends[index]) + 1
            segment_history = history_np[:, :, start:end]
            area = segment_history[:, 0, :]
            flow = segment_history[:, 1, :]
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
                    segment_id=segment.segment_id,
                    x_m=mesh.x_m,
                    area_m2=area,
                    flow_m3_per_s=flow,
                    pressure_pa=pressure,
                )
            )
            if bool(problem.terminal_mask[index]):
                terminal_flow_histories.append(flow[:, -1])

        duration = float(target_time[-1] - target_time[0])
        root_mean = baseline.aortic_inflow.mean_flow_m3_per_s
        terminal_mean = sum(
            float(np.trapezoid(item, target_time) / duration)
            for item in terminal_flow_histories
        )
        terminal_mass_balance = abs(root_mean - terminal_mean) / max(abs(root_mean), 1e-12)

        diagnostics = SolverDiagnostics(
            cycles_completed=cycles_completed,
            periodicity_error=convergence,
            converged=converged,
            minimum_area_ratio=minimum_area_ratio,
            maximum_cfl=maximum_cfl,
            maximum_diffusion_number=maximum_diffusion,
            terminal_mass_balance_relative_error=terminal_mass_balance,
        )
        solution = ForwardSolution(
            time_s=target_time,
            segments=tuple(segment_solutions),
            diagnostics=diagnostics,
        )

        device = getattr(U, "device", None)
        if callable(device):
            device = device()
        if device is None:
            devices = jax.devices()
            device = devices[0] if devices else "unknown"
        self._last_timing = JaxSolverTiming(
            total_s=time.perf_counter() - total_start,
            first_cycle_compile_and_execute_s=first_cycle_wall,
            subsequent_cycles_execute_s=subsequent_cycle_wall,
            final_cycle_replay_s=replay_wall,
            history_compile_and_execute_s=replay_wall,
            final_cycle_steps=replay_count,
            output_samples=int(target_time.size),
            max_steps_per_cycle=max_steps,
            initial_stability_dt_s=initial_dt_value,
            platform=str(getattr(device, "platform", "unknown")),
            device=str(device),
            x64_enabled=bool(jax.config.x64_enabled),
        )
        return solution


__all__ = ["JaxDiseaseOneDSolver", "JaxSolverTiming"]
