"""Structure-preserving accelerated JAX solver for Virtual Disease.

The frozen NumPy :class:`DiseaseOneDSolver` remains the scientific reference.
This backend preserves its semidiscrete 116-segment operator but changes the
time integration so avoidable source stiffness does not control the global
step:

    exact focal-loss half step
    -> global Voigt RKC2 half step
    -> hyperbolic/network SSP-RK2 full step
    -> global Voigt RKC2 half step
    -> exact focal-loss half step

The composition is symmetric and second order. In the non-autonomous extended
system, physical time advances only in the hyperbolic/network subflow; the
source subflows therefore evaluate boundary data at the left/right endpoint of
the outer step respectively. Young--Seeley excess inertance must be zero,
which is the deployed Virtual Disease v1 contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.errors import NumericalMethodError

from .jax_disease import (
    _flatten_problem,
    _initial_flat_state,
    _jax_arrays,
    _kernel_factory,
)
from .losses import LocalizedPressureLoss
from .model import ForwardSolution, SegmentSolution, SolverDiagnostics, SolverOptions
from .network import NetworkDiscretization, ThinWallLaw, VoigtWallLaw

try:
    import jax
    import jax.numpy as jnp
    from jax import lax
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The accelerated Virtual Disease backend requires the optional 'jax' "
        "dependency. Install VascuQuest with `pip install 'vascuquest[jax]'`."
    ) from exc

jax.config.update("jax_enable_x64", True)

JAX_SPLIT_SCHEME_ID = "jax-exact-loss-rkc2-voigt-ssprk2-v1"
_RKC_DAMPING = 2.0 / 13.0


@dataclass(frozen=True, slots=True)
class JaxSplitSolverTiming:
    total_s: float
    first_cycle_compile_and_execute_s: float
    subsequent_cycles_execute_s: float
    final_cycle_replay_s: float
    final_cycle_outer_steps: int
    final_cycle_rkc_stages_total: int
    final_cycle_rkc_stages_max: int
    minimum_wave_dt_s: float
    minimum_voigt_explicit_dt_s: float
    minimum_loss_explicit_dt_s: float
    output_samples: int
    exact_loss_updates: int
    scheme_id: str
    platform: str
    device: str
    x64_enabled: bool


def _output_grid(baseline: BaselineCardiovascularState, period: float) -> np.ndarray:
    base = np.asarray(baseline.aortic_inflow.time_s, dtype=float)
    base = base - float(base[0])
    interior = base[(base > 0.0) & (base < period - 1e-13)]
    target = np.concatenate((np.asarray([0.0]), interior, np.asarray([period])))
    if target.size < 2 or not np.all(np.diff(target) > 0.0):
        raise NumericalMethodError("JAX split output grid is not strictly increasing")
    return target


def _derive_outer_step_cap(period: float, wave_dt: float) -> int:
    if not math.isfinite(wave_dt) or wave_dt <= 0.0:
        raise NumericalMethodError("unable to derive a positive wave-CFL step")
    estimated = int(math.ceil(period / wave_dt))
    return min(max(100_000, 16 * estimated + 4096), 5_000_000)


def _split_kernel_factory(
    baseline: BaselineCardiovascularState,
    problem,
    options: SolverOptions,
    *,
    max_outer_steps: int,
    max_rkc_stages: int,
    target_times: np.ndarray,
):
    p = _jax_arrays(problem)
    rho = float(baseline.blood_density_kg_per_m3)
    cfl = float(options.cfl)
    diffusion_safety = float(options.diffusion_safety)
    floor_ratio = float(options.area_floor_ratio)
    diastolic = float(baseline.diastolic_pressure_pa)
    outlet_pressure = float(baseline.outlet_pressure_pa)
    period = float(problem.period_s)
    root_index = int(problem.root_segment_index)
    starts = p["starts"]
    ends = p["ends"]
    a0 = p["a0_m2"]
    beta = p["beta_pa"]
    gamma = p["gamma_pa_s_per_m"]
    dx = p["dx_m"]
    targets = jnp.asarray(target_times, dtype=jnp.float64)
    sample_count = int(target_times.size)

    # Reuse the already-qualified complete semidiscrete JAX operator. Its
    # cycle/history functions are intentionally ignored here.
    full_rhs, full_stability, _, _, _ = _kernel_factory(
        baseline, problem, options, max_steps_per_cycle=2
    )

    loss_linear = p["loss_linear_density"]
    loss_quadratic = p["loss_quadratic_density"]

    def pressure(area, reference_area, stiffness):
        return diastolic + stiffness * (
            jnp.sqrt(jnp.maximum(area / reference_area, 1e-24)) - 1.0
        )

    def area_from_pressure(pressure_pa, reference_area, stiffness):
        factor = 1.0 + (pressure_pa - diastolic) / stiffness
        factor = jnp.maximum(factor, 1e-6)
        return reference_area * factor * factor

    def wave_speed(area, reference_area, stiffness):
        return jnp.sqrt(stiffness / (2.0 * rho)) * jnp.power(
            area / reference_area, 0.25
        )

    def impedance(area, reference_area, stiffness):
        return rho * wave_speed(area, reference_area, stiffness) / area

    def inflow_value(time_s):
        phase = jnp.mod(time_s, period)
        return jnp.interp(phase, p["inflow_time_s"], p["inflow_flow_m3_per_s"])

    def boundary_states(U, pc, time_s):
        a_in = U[0, starts]
        q_in = U[1, starts]
        a_out = U[0, ends]
        q_out = U[1, ends]
        a0_in = a0[starts]
        a0_out = a0[ends]
        beta_in = beta[starts]
        beta_out = beta[ends]
        p_in = pressure(a_in, a0_in, beta_in)
        p_out = pressure(a_out, a0_out, beta_out)
        z_in = impedance(a_in, a0_in, beta_in)
        z_out = impedance(a_out, a0_out, beta_out)

        numerator = (
            p["incoming_incidence"] @ (q_out + p_out / z_out)
            + p["outgoing_incidence"] @ (-q_in + p_in / z_in)
        )
        denominator = (
            p["incoming_incidence"] @ (1.0 / z_out)
            + p["outgoing_incidence"] @ (1.0 / z_in)
        )
        node_pressure = numerator / jnp.where(denominator > 0.0, denominator, 1.0)
        inlet_node_pressure = node_pressure[p["segment_in_node"]]
        outlet_node_pressure = node_pressure[p["segment_out_node"]]
        inlet_q = q_in + (inlet_node_pressure - p_in) / z_in
        inlet_a = area_from_pressure(inlet_node_pressure, a0_in, beta_in)
        outlet_q = q_out + (p_out - outlet_node_pressure) / z_out
        outlet_a = area_from_pressure(outlet_node_pressure, a0_out, beta_out)

        q_root = inflow_value(time_s)
        p_root = p_in[root_index] + z_in[root_index] * (q_root - q_in[root_index])
        a_root = area_from_pressure(p_root, a0_in[root_index], beta_in[root_index])
        inlet_q = inlet_q.at[root_index].set(q_root)
        inlet_a = inlet_a.at[root_index].set(a_root)

        q_terminal = (
            q_out + (p_out - pc) / z_out
        ) / (1.0 + p["r1_pa_s_per_m3"] / z_out)
        p_terminal = pc + p["r1_pa_s_per_m3"] * q_terminal
        a_terminal = area_from_pressure(p_terminal, a0_out, beta_out)
        terminal_mask = p["terminal_mask"]
        outlet_q = jnp.where(terminal_mask, q_terminal, outlet_q)
        outlet_a = jnp.where(terminal_mask, a_terminal, outlet_a)
        dpc = (
            q_terminal - (pc - outlet_pressure) / p["r2_pa_s_per_m3"]
        ) / p["compliance_m3_per_pa"]
        return inlet_a, inlet_q, outlet_a, outlet_q, jnp.where(terminal_mask, dpc, 0.0)

    def voigt_rhs(U, pc, time_s):
        inlet_a, inlet_q, outlet_a, outlet_q, _ = boundary_states(U, pc, time_s)
        q = U[1]
        area = U[0]
        face_gradient = (
            q[p["face_right_cell"]] - q[p["face_left_cell"]]
        ) / (0.5 * (dx[p["face_left_cell"]] + dx[p["face_right_cell"]]))
        face_area = 0.5 * (
            area[p["face_left_cell"]] + area[p["face_right_cell"]]
        )
        face_gamma = 0.5 * (
            gamma[p["face_left_cell"]] + gamma[p["face_right_cell"]]
        )
        face_gradient = face_gradient.at[p["inlet_face"]].set(
            (q[starts] - inlet_q) / dx[starts]
        )
        face_area = face_area.at[p["inlet_face"]].set(0.5 * (area[starts] + inlet_a))
        face_gamma = face_gamma.at[p["inlet_face"]].set(gamma[starts])
        face_gradient = face_gradient.at[p["outlet_face"]].set(
            (outlet_q - q[ends]) / dx[ends]
        )
        face_area = face_area.at[p["outlet_face"]].set(0.5 * (area[ends] + outlet_a))
        face_gamma = face_gamma.at[p["outlet_face"]].set(gamma[ends])
        psi = face_gamma * face_gradient / jnp.sqrt(jnp.maximum(face_area, 1e-18))
        momentum = area / rho * (
            psi[p["cell_right_face"]] - psi[p["cell_left_face"]]
        ) / dx
        return jnp.stack((jnp.zeros_like(momentum), momentum), axis=0)

    def loss_rhs(U):
        area = U[0]
        q = U[1]
        momentum = -area / rho * (
            loss_linear * q + loss_quadratic * q * jnp.abs(q)
        )
        return jnp.stack((jnp.zeros_like(momentum), momentum), axis=0)

    def hyperbolic_rhs(U, pc, time_s):
        complete, dpc = full_rhs(U, pc, time_s)
        # Decomposition is exact for vd1 because excess inertance is zero.
        return complete - voigt_rhs(U, pc, time_s) - loss_rhs(U), dpc

    def exact_loss(U, dt):
        area = U[0]
        q = U[1]
        a = area / rho * loss_linear
        b = area / rho * loss_quadratic
        magnitude = jnp.abs(q)
        adt = a * dt
        decay = jnp.exp(-adt)
        one_minus_decay = -jnp.expm1(-adt)
        use_linear = a > 1e-30
        ratio = b / jnp.where(use_linear, a, 1.0)
        magnitude_linear = magnitude * decay / (
            1.0 + ratio * magnitude * one_minus_decay
        )
        magnitude_quadratic = magnitude / (1.0 + b * magnitude * dt)
        updated_q = jnp.sign(q) * jnp.where(
            use_linear, magnitude_linear, magnitude_quadratic
        )
        return U.at[1].set(updated_q)

    def apply_floor(U):
        return U.at[0].set(jnp.maximum(U[0], floor_ratio * a0))

    def h_ssprk2(U, pc, time_s, dt):
        k1, pc1 = hyperbolic_rhs(U, pc, time_s)
        stage = apply_floor(U + dt * k1)
        pc_stage = pc + dt * pc1
        k2, pc2 = hyperbolic_rhs(stage, pc_stage, time_s + dt)
        updated = apply_floor(0.5 * (U + stage + dt * k2))
        pc_updated = 0.5 * (pc + pc_stage + dt * pc2)
        return updated, pc_updated

    def cheb_terminal(s, w0):
        initial = (
            jnp.asarray(2, dtype=jnp.int32),
            jnp.asarray(1.0, dtype=jnp.float64),
            w0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(1.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
        )

        def cond(carry):
            j, *_ = carry
            return j <= s

        def body(carry):
            j, tm2, tm1, dm2, dm1, ddm2, ddm1 = carry
            tj = 2.0 * w0 * tm1 - tm2
            dj = 2.0 * tm1 + 2.0 * w0 * dm1 - dm2
            ddj = 4.0 * dm1 + 2.0 * w0 * ddm1 - ddm2
            return j + 1, tm1, tj, dm1, dj, ddm1, ddj

        _, _, ts, _, ds, _, dds = lax.while_loop(cond, body, initial)
        return ts, ds, dds

    def rkc_stage_count(U, duration):
        area = U[0]
        diffusion_rate = 2.0 * gamma * jnp.sqrt(area) / rho / (dx * dx)
        maximum_rate = jnp.max(diffusion_rate)
        explicit_safe_dt = jnp.where(
            maximum_rate > 0.0,
            diffusion_safety / maximum_rate,
            jnp.inf,
        )
        # The damped second-order RKC real stability boundary scales as
        # beta(s) ~= 0.65*(s^2-1).  Relative to s=2, beta(s)/beta(2) is
        # approximately (s^2-1)/3.  Therefore choose the smallest s whose
        # stable interval is at least duration/explicit_safe_dt times the
        # already-qualified explicit Voigt safety step. This preserves the
        # user's configured diffusion_safety instead of introducing a new
        # empirical RKC safety constant.
        ratio = jnp.where(
            jnp.isfinite(explicit_safe_dt),
            duration / explicit_safe_dt,
            0.0,
        )
        raw = jnp.ceil(jnp.sqrt(1.0 + 3.0 * jnp.maximum(ratio, 0.0))).astype(
            jnp.int32
        )
        return jnp.maximum(raw, jnp.asarray(2, dtype=jnp.int32)), maximum_rate

    def rkc2_voigt(U0, pc, frozen_time, duration):
        stages, spectral = rkc_stage_count(U0, duration)
        overflow = stages > max_rkc_stages
        safe_stages = jnp.minimum(stages, max_rkc_stages)
        w0 = 1.0 + _RKC_DAMPING / (safe_stages.astype(jnp.float64) ** 2)
        _, ds, dds = cheb_terminal(safe_stages, w0)
        w1 = ds / jnp.maximum(dds, 1e-30)
        # T2'=4*w0, T2''=4 -> b2=1/(4*w0^2); b0=b1=b2.
        b2 = 1.0 / (4.0 * w0 * w0)
        f0 = voigt_rhs(U0, pc, frozen_time)
        y1 = U0 + (b2 * w1) * duration * f0
        y1 = y1.at[0].set(U0[0])

        initial = (
            jnp.asarray(2, dtype=jnp.int32),
            U0,
            y1,
            jnp.asarray(1.0, dtype=jnp.float64),
            w0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(1.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            b2,
            b2,
        )

        def cond(carry):
            j, *_ = carry
            return j <= safe_stages

        def body(carry):
            (
                j,
                yjm2,
                yjm1,
                tm2,
                tm1,
                dm2,
                dm1,
                ddm2,
                ddm1,
                bjm2,
                bjm1,
            ) = carry
            tj = 2.0 * w0 * tm1 - tm2
            dj = 2.0 * tm1 + 2.0 * w0 * dm1 - dm2
            ddj = 4.0 * dm1 + 2.0 * w0 * ddm1 - ddm2
            bj = ddj / jnp.maximum(dj * dj, 1e-30)
            a_prev = 1.0 - bjm1 * tm1
            mu = 2.0 * bj * w0 / bjm1
            nu = -bj / bjm2
            tmu = 2.0 * bj * w1 / bjm1
            tgamma = -a_prev * tmu
            fprev = voigt_rhs(yjm1, pc, frozen_time)
            yj = (
                (1.0 - mu - nu) * U0
                + mu * yjm1
                + nu * yjm2
                + tmu * duration * fprev
                + tgamma * duration * f0
            )
            # The Voigt suboperator has exactly zero area derivative.
            yj = yj.at[0].set(U0[0])
            return (
                j + 1,
                yjm1,
                yj,
                tm1,
                tj,
                dm1,
                dj,
                ddm1,
                ddj,
                bjm1,
                bj,
            )

        final = lax.while_loop(cond, body, initial)
        return final[2], stages, spectral, overflow

    def split_step(U, pc, time_s, dt):
        half = 0.5 * dt
        U1 = exact_loss(U, half)
        U2, stages_left, spectral_left, overflow_left = rkc2_voigt(
            U1, pc, time_s, half
        )
        U3, pc3 = h_ssprk2(U2, pc, time_s, dt)
        U4, stages_right, spectral_right, overflow_right = rkc2_voigt(
            U3, pc3, time_s + dt, half
        )
        U5 = exact_loss(U4, half)
        return (
            U5,
            pc3,
            stages_left + stages_right,
            jnp.maximum(stages_left, stages_right),
            jnp.maximum(spectral_left, spectral_right),
            overflow_left | overflow_right,
        )

    def limiter_values(U):
        _, cfl_rate, diffusion_rate, loss_dt = full_stability(U)
        wave_dt = cfl / jnp.maximum(cfl_rate, 1e-12)
        voigt_dt = jnp.where(
            diffusion_rate > 0.0,
            diffusion_safety / diffusion_rate,
            jnp.inf,
        )
        return wave_dt, voigt_dt, loss_dt, cfl_rate, diffusion_rate

    loss_active = bool(
        np.any(np.asarray(problem.loss_linear_density) > 0.0)
        or np.any(np.asarray(problem.loss_quadratic_density) > 0.0)
    )
    loss_updates_per_step = 2 if loss_active else 0

    def cycle_kernel(U0, pc0, absolute_start):
        initial = (
            U0,
            pc0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(jnp.inf, dtype=jnp.float64),
            jnp.asarray(jnp.inf, dtype=jnp.float64),
            jnp.asarray(jnp.inf, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(0, dtype=jnp.int64),
            jnp.asarray(0, dtype=jnp.int32),
            jnp.asarray(0, dtype=jnp.int64),
            jnp.asarray(False, dtype=jnp.bool_),
            jnp.asarray(0, dtype=jnp.int32),
        )

        def cond(carry):
            phase = carry[2]
            invalid = carry[11]
            steps = carry[12]
            return (phase < period - 1e-14) & (~invalid) & (steps < max_outer_steps)

        def body(carry):
            (
                U,
                pc,
                phase,
                min_wave,
                min_voigt,
                min_loss,
                max_cfl,
                max_diffnum,
                rkc_total,
                rkc_max,
                exact_updates,
                invalid,
                steps,
            ) = carry
            wave_dt, voigt_dt, loss_dt, cfl_rate, diffusion_rate = limiter_values(U)
            dt = jnp.minimum(wave_dt, period - phase)
            invalid_dt = (~jnp.isfinite(dt)) | (dt <= 0.0)
            safe_dt = jnp.where(invalid_dt, 1e-12, dt)
            updated, pc_updated, rkc_stages, rkc_peak, spectral, overflow = split_step(
                U, pc, absolute_start + phase, safe_dt
            )
            floor = floor_ratio * a0
            invalid_state = (
                (~jnp.all(jnp.isfinite(updated)))
                | (~jnp.all(jnp.isfinite(pc_updated)))
                | jnp.any(updated[0] <= floor)
            )
            return (
                updated,
                pc_updated,
                phase + safe_dt,
                jnp.minimum(min_wave, wave_dt),
                jnp.minimum(min_voigt, voigt_dt),
                jnp.minimum(min_loss, loss_dt),
                jnp.maximum(max_cfl, cfl_rate * safe_dt),
                jnp.maximum(max_diffnum, spectral * safe_dt),
                rkc_total + rkc_stages.astype(jnp.int64),
                jnp.maximum(rkc_max, rkc_peak),
                exact_updates + jnp.asarray(loss_updates_per_step, dtype=jnp.int64),
                invalid | invalid_dt | invalid_state | overflow,
                steps + 1,
            )

        return lax.while_loop(cond, body, initial)

    def replay_kernel(U0, pc0, absolute_start):
        history = jnp.zeros((sample_count,) + U0.shape, dtype=jnp.float64)
        history = history.at[0].set(U0)
        initial = (
            U0,
            pc0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(1, dtype=jnp.int32),
            history,
            jnp.asarray(0, dtype=jnp.int64),
            jnp.asarray(0, dtype=jnp.int32),
            jnp.asarray(0, dtype=jnp.int64),
            jnp.asarray(jnp.inf, dtype=jnp.float64),
            jnp.asarray(jnp.inf, dtype=jnp.float64),
            jnp.asarray(jnp.inf, dtype=jnp.float64),
            jnp.asarray(False, dtype=jnp.bool_),
            jnp.asarray(0, dtype=jnp.int32),
        )

        def cond(carry):
            phase = carry[2]
            invalid = carry[11]
            steps = carry[12]
            return (phase < period - 1e-14) & (~invalid) & (steps < max_outer_steps)

        def body(carry):
            (
                U,
                pc,
                phase,
                next_index,
                history,
                rkc_total,
                rkc_max,
                exact_updates,
                min_wave,
                min_voigt,
                min_loss,
                invalid,
                steps,
            ) = carry
            wave_dt, voigt_dt, loss_dt, _, _ = limiter_values(U)
            dt = jnp.minimum(wave_dt, period - phase)
            invalid_dt = (~jnp.isfinite(dt)) | (dt <= 0.0)
            safe_dt = jnp.where(invalid_dt, 1e-12, dt)
            updated, pc_updated, rkc_stages, rkc_peak, _, overflow = split_step(
                U, pc, absolute_start + phase, safe_dt
            )
            phase_new = phase + safe_dt
            floor = floor_ratio * a0
            invalid_state = (
                (~jnp.all(jnp.isfinite(updated)))
                | (~jnp.all(jnp.isfinite(pc_updated)))
                | jnp.any(updated[0] <= floor)
            )

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

            next_index, history = lax.while_loop(
                fill_cond, fill_body, (next_index, history)
            )
            return (
                updated,
                pc_updated,
                phase_new,
                next_index,
                history,
                rkc_total + rkc_stages.astype(jnp.int64),
                jnp.maximum(rkc_max, rkc_peak),
                exact_updates + jnp.asarray(loss_updates_per_step, dtype=jnp.int64),
                jnp.minimum(min_wave, wave_dt),
                jnp.minimum(min_voigt, voigt_dt),
                jnp.minimum(min_loss, loss_dt),
                invalid | invalid_dt | invalid_state | overflow,
                steps + 1,
            )

        return lax.while_loop(cond, body, initial)

    return (
        jax.jit(full_rhs),
        jax.jit(full_stability),
        jax.jit(voigt_rhs),
        jax.jit(loss_rhs),
        jax.jit(hyperbolic_rhs),
        jax.jit(exact_loss),
        jax.jit(cycle_kernel),
        jax.jit(replay_kernel),
    )


class JaxDiseaseOneDSolver:
    """CFL-limited JAX solver with exact focal loss and stabilized Voigt source."""

    __slots__ = ("_options", "_max_rkc_stages", "_last_timing")

    def __init__(
        self,
        options: SolverOptions | None = None,
        *,
        max_rkc_stages: int = 2048,
    ) -> None:
        self._options = SolverOptions() if options is None else options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("options must be SolverOptions")
        if isinstance(max_rkc_stages, bool) or not isinstance(max_rkc_stages, int) or max_rkc_stages < 2:
            raise ValueError("max_rkc_stages must be an integer >= 2")
        self._max_rkc_stages = max_rkc_stages
        self._last_timing: JaxSplitSolverTiming | None = None

    @property
    def options(self) -> SolverOptions:
        return self._options

    @property
    def last_timing(self) -> JaxSplitSolverTiming | None:
        return self._last_timing

    def solve(
        self,
        baseline: BaselineCardiovascularState,
        network: NetworkDiscretization,
        *,
        pressure_losses: tuple[LocalizedPressureLoss, ...] = (),
    ) -> ForwardSolution:
        if not isinstance(baseline, BaselineCardiovascularState):
            raise TypeError("baseline must be BaselineCardiovascularState")
        if not isinstance(network, NetworkDiscretization):
            raise TypeError("network must be NetworkDiscretization")
        if not isinstance(pressure_losses, tuple):
            raise TypeError("pressure_losses must be a tuple")
        for loss in pressure_losses:
            if float(loss.inertance_pa_s2_per_m3) != 0.0:
                raise NumericalMethodError(
                    "accelerated exact-loss solver requires zero excess focal-loss inertance"
                )

        period = float(baseline.aortic_inflow.duration_s)
        if abs(period - baseline.cardiac_period_s) > max(0.01, 0.02 * baseline.cardiac_period_s):
            raise NumericalMethodError(
                "source aortic inflow duration is inconsistent with subject heart rate"
            )

        total_start = time.perf_counter()
        problem = _flatten_problem(baseline, network, pressure_losses)
        U, pc = _initial_flat_state(baseline, problem)
        target_time = _output_grid(baseline, period)

        # Probe the original explicit limiter decomposition at the initial state.
        _, stability_probe, _, _, _ = _kernel_factory(
            baseline, problem, self._options, max_steps_per_cycle=2
        )
        _, cfl_rate0, _, _ = stability_probe(U)
        cfl_rate0.block_until_ready()
        initial_wave_dt = float(self._options.cfl / max(float(np.asarray(cfl_rate0)), 1e-12))
        max_outer_steps = _derive_outer_step_cap(period, initial_wave_dt)

        (
            _,
            _,
            _,
            _,
            _,
            _,
            cycle_fn,
            replay_fn,
        ) = _split_kernel_factory(
            baseline,
            problem,
            self._options,
            max_outer_steps=max_outer_steps,
            max_rkc_stages=self._max_rkc_stages,
            target_times=target_time,
        )

        convergence = float("inf")
        maximum_cfl = 0.0
        maximum_diffusion_number = 0.0
        cycles_completed = 0
        converged = False
        first_cycle_wall = 0.0
        subsequent_cycle_wall = 0.0
        final_start_U = U
        final_start_pc = pc
        final_cycle_index = 0
        final_cycle_stats = None

        for cycle in range(self._options.maximum_cycles):
            start_U = U
            start_pc = pc
            wall_start = time.perf_counter()
            result = cycle_fn(
                U, pc, jnp.asarray(cycle * period, dtype=jnp.float64)
            )
            U = result[0]
            pc = result[1]
            U.block_until_ready()
            wall_elapsed = time.perf_counter() - wall_start
            if cycle == 0:
                first_cycle_wall = wall_elapsed
            else:
                subsequent_cycle_wall += wall_elapsed

            phase = float(np.asarray(result[2]))
            invalid = bool(np.asarray(result[11]))
            steps = int(np.asarray(result[12]))
            if steps >= max_outer_steps and phase < period - 1e-12:
                raise NumericalMethodError(
                    "accelerated JAX solver exceeded wave-CFL outer-step safety cap"
                )
            if invalid:
                raise NumericalMethodError(
                    "accelerated JAX solver produced an invalid state or exceeded the RKC stage cap"
                )

            start_np = np.asarray(start_U, dtype=float)
            end_np = np.asarray(U, dtype=float)
            diff = end_np - start_np
            convergence = float(
                np.sqrt(float(np.sum(diff * diff)) / max(float(np.sum(start_np * start_np)), 1e-30))
            )
            maximum_cfl = max(maximum_cfl, float(np.asarray(result[6])))
            maximum_diffusion_number = max(
                maximum_diffusion_number, float(np.asarray(result[7]))
            )
            cycles_completed = cycle + 1
            final_start_U = start_U
            final_start_pc = start_pc
            final_cycle_index = cycle
            final_cycle_stats = result
            if (
                cycles_completed >= self._options.minimum_cycles
                and convergence <= self._options.periodicity_tolerance
            ):
                converged = True
                break

        if final_cycle_stats is None:
            raise RuntimeError("accelerated JAX solver completed no cardiac cycles")

        replay_start = time.perf_counter()
        replay = replay_fn(
            final_start_U,
            final_start_pc,
            jnp.asarray(final_cycle_index * period, dtype=jnp.float64),
        )
        replay[0].block_until_ready()
        replay[4].block_until_ready()
        replay_wall = time.perf_counter() - replay_start
        replay_phase = float(np.asarray(replay[2]))
        replay_samples = int(np.asarray(replay[3]))
        replay_invalid = bool(np.asarray(replay[11]))
        replay_steps = int(np.asarray(replay[12]))
        if replay_invalid:
            raise NumericalMethodError("accelerated JAX final-cycle replay failed")
        if replay_steps >= max_outer_steps and replay_phase < period - 1e-12:
            raise NumericalMethodError("accelerated JAX replay exceeded outer-step safety cap")
        if replay_samples != target_time.size:
            raise NumericalMethodError("accelerated JAX replay did not populate output grid")

        history_np = np.asarray(replay[4], dtype=float)
        segment_solutions: list[SegmentSolution] = []
        minimum_area_ratio = float("inf")
        terminal_flow_histories: list[np.ndarray] = []
        for index, (segment, mesh) in enumerate(
            zip(baseline.segments, network.meshes, strict=True)
        ):
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
            maximum_diffusion_number=maximum_diffusion_number,
            terminal_mass_balance_relative_error=terminal_mass_balance,
            wall_viscoelasticity_mode="pwdb_voigt_gamma_rkc2_global_split",
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

        min_wave = float(np.asarray(replay[8]))
        min_voigt = float(np.asarray(replay[9]))
        min_loss = float(np.asarray(replay[10]))
        self._last_timing = JaxSplitSolverTiming(
            total_s=time.perf_counter() - total_start,
            first_cycle_compile_and_execute_s=first_cycle_wall,
            subsequent_cycles_execute_s=subsequent_cycle_wall,
            final_cycle_replay_s=replay_wall,
            final_cycle_outer_steps=replay_steps,
            final_cycle_rkc_stages_total=int(np.asarray(replay[5])),
            final_cycle_rkc_stages_max=int(np.asarray(replay[6])),
            minimum_wave_dt_s=min_wave,
            minimum_voigt_explicit_dt_s=min_voigt,
            minimum_loss_explicit_dt_s=min_loss,
            output_samples=int(target_time.size),
            exact_loss_updates=int(np.asarray(replay[7])),
            scheme_id=JAX_SPLIT_SCHEME_ID,
            platform=str(getattr(device, "platform", "unknown")),
            device=str(device),
            x64_enabled=bool(jax.config.x64_enabled),
        )
        return solution


__all__ = [
    "JAX_SPLIT_SCHEME_ID",
    "JaxDiseaseOneDSolver",
    "JaxSplitSolverTiming",
]
