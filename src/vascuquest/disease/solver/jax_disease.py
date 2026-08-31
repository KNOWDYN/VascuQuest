"""JAX-accelerated Virtual Disease 1-D haemodynamic solver.

The NumPy DiseaseOneDSolver remains the frozen reference implementation. This
backend preserves the same finite-volume equations, wall laws, characteristic
junction coupling, terminal RCR model, focal pressure-loss terms, SSP-RK2
controls and periodic convergence criterion while flattening the 116-segment
network into JIT-compiled JAX kernels.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.errors import NumericalMethodError

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
        "Install VascuQuest with `pip install 'vascuquest[jax]'` or install JAX "
        "for the target accelerator before selecting the JAX backend."
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
    platform: str
    device: str
    x64_enabled: bool


@dataclass(frozen=True, slots=True)
class JaxOperatorSnapshot:
    derivatives: dict[str, np.ndarray]
    capacitor_derivatives: dict[str, float]
    stability_dt_s: float
    hyperbolic_cfl_rate_per_s: float
    diffusion_rate_per_s: float
    disease_loss_dt_s: float


@dataclass(frozen=True, slots=True)
class _FlatProblem:
    segment_ids: tuple[str, ...]
    starts: np.ndarray
    ends: np.ndarray
    counts: np.ndarray
    x_m: np.ndarray
    dx_m: np.ndarray
    a0_m2: np.ndarray
    beta_pa: np.ndarray
    gamma_pa_s_per_m: np.ndarray
    prev_cell: np.ndarray
    next_cell: np.ndarray
    interior_cell_mask: np.ndarray
    face_left_cell: np.ndarray
    face_right_cell: np.ndarray
    inlet_face: np.ndarray
    outlet_face: np.ndarray
    cell_left_face: np.ndarray
    cell_right_face: np.ndarray
    segment_in_node: np.ndarray
    segment_out_node: np.ndarray
    incoming_incidence: np.ndarray
    outgoing_incidence: np.ndarray
    terminal_mask: np.ndarray
    root_segment_index: int
    r1_pa_s_per_m3: np.ndarray
    r2_pa_s_per_m3: np.ndarray
    compliance_m3_per_pa: np.ndarray
    loss_linear_density: np.ndarray
    loss_quadratic_density: np.ndarray
    loss_inertance_density: np.ndarray
    inflow_time_s: np.ndarray
    inflow_flow_m3_per_s: np.ndarray
    period_s: float


def _characteristic_impedance(area: float, a0: float, beta: float, density: float) -> float:
    c = math.sqrt(beta / (2.0 * density)) * (area / a0) ** 0.25
    return density * c / area


def _flatten_problem(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    pressure_losses: tuple[LocalizedPressureLoss, ...],
) -> _FlatProblem:
    segment_ids = tuple(mesh.segment_id for mesh in network.meshes)
    baseline_ids = tuple(segment.segment_id for segment in baseline.segments)
    if segment_ids != baseline_ids:
        raise ValueError("transformed network must preserve baseline segment identity and order")
    if len(segment_ids) != 116:
        raise ValueError(
            "JAX Virtual Disease backend requires the canonical 116-segment network; "
            f"received {len(segment_ids)} segments"
        )

    counts = np.asarray([mesh.cell_count for mesh in network.meshes], dtype=np.int32)
    starts = np.concatenate(
        (np.asarray([0], dtype=np.int32), np.cumsum(counts[:-1], dtype=np.int32))
    )
    ends = starts + counts - 1
    total_cells = int(np.sum(counts))
    total_faces = total_cells + len(segment_ids)

    x = np.concatenate([np.asarray(mesh.x_m, dtype=float) for mesh in network.meshes])
    dx = np.concatenate([np.asarray(mesh.dx_m, dtype=float) for mesh in network.meshes])
    a0 = np.concatenate(
        [np.asarray(mesh.reference_area_m2, dtype=float) for mesh in network.meshes]
    )
    beta = np.concatenate([np.asarray(mesh.beta_pa, dtype=float) for mesh in network.meshes])
    gamma = np.concatenate(
        [np.asarray(mesh.source_gamma_pa_s_per_m, dtype=float) for mesh in network.meshes]
    )

    prev_cell = np.empty(total_cells, dtype=np.int32)
    next_cell = np.empty(total_cells, dtype=np.int32)
    interior = np.zeros(total_cells, dtype=bool)
    face_left_cell = np.empty(total_faces, dtype=np.int32)
    face_right_cell = np.empty(total_faces, dtype=np.int32)
    inlet_face = np.empty(len(segment_ids), dtype=np.int32)
    outlet_face = np.empty(len(segment_ids), dtype=np.int32)
    cell_left_face = np.empty(total_cells, dtype=np.int32)
    cell_right_face = np.empty(total_cells, dtype=np.int32)

    face_cursor = 0
    for index, (start, count) in enumerate(zip(starts, counts, strict=True)):
        start_i = int(start)
        count_i = int(count)
        face_start = face_cursor
        inlet_face[index] = face_start
        outlet_face[index] = face_start + count_i
        for local in range(count_i):
            cell = start_i + local
            prev_cell[cell] = start_i + max(local - 1, 0)
            next_cell[cell] = start_i + min(local + 1, count_i - 1)
            interior[cell] = 0 < local < count_i - 1
            cell_left_face[cell] = face_start + local
            cell_right_face[cell] = face_start + local + 1
        for local_face in range(count_i + 1):
            face = face_start + local_face
            face_left_cell[face] = start_i + max(local_face - 1, 0)
            face_right_cell[face] = start_i + min(local_face, count_i - 1)
        face_cursor += count_i + 1
    if face_cursor != total_faces:
        raise RuntimeError("internal JAX face indexing failed")

    nodes = tuple(
        sorted(
            {
                node
                for segment in baseline.segments
                for node in (segment.inlet_node, segment.outlet_node)
            }
        )
    )
    node_index = {node: index for index, node in enumerate(nodes)}
    segment_in_node = np.asarray(
        [node_index[segment.inlet_node] for segment in baseline.segments], dtype=np.int32
    )
    segment_out_node = np.asarray(
        [node_index[segment.outlet_node] for segment in baseline.segments], dtype=np.int32
    )
    incoming = np.zeros((len(nodes), len(segment_ids)), dtype=float)
    outgoing = np.zeros((len(nodes), len(segment_ids)), dtype=float)
    for index, segment in enumerate(baseline.segments):
        incoming[node_index[segment.outlet_node], index] = 1.0
        outgoing[node_index[segment.inlet_node], index] = 1.0

    terminal_ids = set(baseline.terminal_segment_ids)
    terminal_mask = np.asarray([sid in terminal_ids for sid in segment_ids], dtype=bool)
    root_index = segment_ids.index("1")

    r1 = np.ones(len(segment_ids), dtype=float)
    r2 = np.ones(len(segment_ids), dtype=float)
    compliance = np.ones(len(segment_ids), dtype=float)
    for index, (segment, mesh) in enumerate(zip(baseline.segments, network.meshes, strict=True)):
        if not terminal_mask[index]:
            continue
        total = float(segment.peripheral_resistance_pa_s_per_m3)
        area = float(mesh.reference_area_m2[-1])
        zc = _characteristic_impedance(
            area, area, float(mesh.beta_pa[-1]), baseline.blood_density_kg_per_m3
        )
        first = zc if zc < total else 0.5 * total
        second = total - first
        if first <= 0 or second <= 0 or segment.peripheral_compliance_m3_per_pa <= 0:
            raise NumericalMethodError(
                f"invalid terminal Windkessel parameters for segment {segment.segment_id}"
            )
        r1[index] = first
        r2[index] = second
        compliance[index] = float(segment.peripheral_compliance_m3_per_pa)

    loss_linear = np.zeros(total_cells, dtype=float)
    loss_quadratic = np.zeros(total_cells, dtype=float)
    loss_inertance = np.zeros(total_cells, dtype=float)
    segment_index = {sid: index for index, sid in enumerate(segment_ids)}
    for loss in pressure_losses:
        if not isinstance(loss, LocalizedPressureLoss):
            raise TypeError("pressure_losses must contain LocalizedPressureLoss values")
        if loss.segment_id not in segment_index:
            raise ValueError(f"pressure loss targets unknown segment {loss.segment_id!r}")
        index = segment_index[loss.segment_id]
        start = int(starts[index])
        end = int(ends[index]) + 1
        mesh = network.meshes[index]
        weights = np.asarray(loss.weights_per_m, dtype=float)
        if weights.shape != mesh.dx_m.shape:
            raise ValueError(
                f"pressure-loss weights for segment {loss.segment_id!r} do not match its mesh"
            )
        integral = float(np.sum(weights * mesh.dx_m))
        if not math.isclose(integral, 1.0, rel_tol=1e-8, abs_tol=1e-10):
            raise ValueError(
                f"pressure-loss weights for segment {loss.segment_id!r} must integrate to one"
            )
        loss_linear[start:end] += weights * float(loss.linear_resistance_pa_s_per_m3)
        loss_quadratic[start:end] += weights * float(loss.quadratic_resistance_pa_s2_per_m6)
        loss_inertance[start:end] += weights * float(loss.inertance_pa_s2_per_m3)

    base_time = np.asarray(baseline.aortic_inflow.time_s, dtype=float)
    base_time = base_time - base_time[0]
    period = float(baseline.aortic_inflow.duration_s)
    inflow_time = np.concatenate((base_time, np.asarray([period], dtype=float)))
    inflow_flow = np.concatenate(
        (
            np.asarray(baseline.aortic_inflow.flow_m3_per_s, dtype=float),
            np.asarray([baseline.aortic_inflow.flow_m3_per_s[0]], dtype=float),
        )
    )

    return _FlatProblem(
        segment_ids=segment_ids,
        starts=starts,
        ends=ends,
        counts=counts,
        x_m=x,
        dx_m=dx,
        a0_m2=a0,
        beta_pa=beta,
        gamma_pa_s_per_m=gamma,
        prev_cell=prev_cell,
        next_cell=next_cell,
        interior_cell_mask=interior,
        face_left_cell=face_left_cell,
        face_right_cell=face_right_cell,
        inlet_face=inlet_face,
        outlet_face=outlet_face,
        cell_left_face=cell_left_face,
        cell_right_face=cell_right_face,
        segment_in_node=segment_in_node,
        segment_out_node=segment_out_node,
        incoming_incidence=incoming,
        outgoing_incidence=outgoing,
        terminal_mask=terminal_mask,
        root_segment_index=root_index,
        r1_pa_s_per_m3=r1,
        r2_pa_s_per_m3=r2,
        compliance_m3_per_pa=compliance,
        loss_linear_density=loss_linear,
        loss_quadratic_density=loss_quadratic,
        loss_inertance_density=loss_inertance,
        inflow_time_s=inflow_time,
        inflow_flow_m3_per_s=inflow_flow,
        period_s=period,
    )


def _jax_arrays(problem: _FlatProblem) -> dict[str, Any]:
    float_names = (
        "x_m",
        "dx_m",
        "a0_m2",
        "beta_pa",
        "gamma_pa_s_per_m",
        "incoming_incidence",
        "outgoing_incidence",
        "r1_pa_s_per_m3",
        "r2_pa_s_per_m3",
        "compliance_m3_per_pa",
        "loss_linear_density",
        "loss_quadratic_density",
        "loss_inertance_density",
        "inflow_time_s",
        "inflow_flow_m3_per_s",
    )
    int_names = (
        "starts",
        "ends",
        "prev_cell",
        "next_cell",
        "face_left_cell",
        "face_right_cell",
        "inlet_face",
        "outlet_face",
        "cell_left_face",
        "cell_right_face",
        "segment_in_node",
        "segment_out_node",
    )
    result: dict[str, Any] = {}
    for name in float_names:
        result[name] = jnp.asarray(getattr(problem, name), dtype=jnp.float64)
    for name in int_names:
        result[name] = jnp.asarray(getattr(problem, name), dtype=jnp.int32)
    result["interior_cell_mask"] = jnp.asarray(problem.interior_cell_mask, dtype=jnp.bool_)
    result["terminal_mask"] = jnp.asarray(problem.terminal_mask, dtype=jnp.bool_)
    return result


def _kernel_factory(
    baseline: BaselineCardiovascularState,
    problem: _FlatProblem,
    options: SolverOptions,
    max_steps_per_cycle: int,
):
    p = _jax_arrays(problem)
    rho = float(baseline.blood_density_kg_per_m3)
    mu = float(baseline.blood_viscosity_pa_s)
    alpha = float(baseline.momentum_correction_alpha)
    diastolic = float(baseline.diastolic_pressure_pa)
    outlet_pressure = float(baseline.outlet_pressure_pa)
    cfl = float(options.cfl)
    diffusion_safety = float(options.diffusion_safety)
    area_floor_ratio = float(options.area_floor_ratio)
    period = float(problem.period_s)
    root_index = int(problem.root_segment_index)
    zeta = 9.0 if alpha <= 1.0 else max((2.0 - alpha) / (alpha - 1.0), 0.0)
    nu = mu / rho
    friction_coefficient = -2.0 * math.pi * nu * (zeta + 2.0)

    starts = p["starts"]
    ends = p["ends"]
    a0 = p["a0_m2"]
    beta = p["beta_pa"]
    gamma = p["gamma_pa_s_per_m"]
    dx = p["dx_m"]

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

    def flux(state, reference_area, stiffness):
        area = state[0]
        flow = state[1]
        coefficient = stiffness / (3.0 * rho * jnp.sqrt(reference_area))
        potential = coefficient * (
            jnp.power(area, 1.5) - jnp.power(reference_area, 1.5)
        )
        return jnp.stack((flow, alpha * flow * flow / area + potential), axis=0)

    def signal_speeds(state, reference_area, stiffness):
        area = state[0]
        flow = state[1]
        velocity = flow / area
        c = wave_speed(area, reference_area, stiffness)
        radical = jnp.sqrt(c * c + alpha * (alpha - 1.0) * velocity * velocity)
        center = alpha * velocity
        return center - radical, center + radical

    def hll(left, right, left_a0, right_a0, left_beta, right_beta):
        fl = flux(left, left_a0, left_beta)
        fr = flux(right, right_a0, right_beta)
        sl_l, sr_l = signal_speeds(left, left_a0, left_beta)
        sl_r, sr_r = signal_speeds(right, right_a0, right_beta)
        s_left = jnp.minimum(jnp.minimum(sl_l, sl_r), 0.0)
        s_right = jnp.maximum(jnp.maximum(sr_l, sr_r), 0.0)
        span = s_right - s_left
        safe_span = jnp.where(span > 1e-14, span, 1.0)
        jump = jnp.stack(
            (
                right[0] - right_a0 - (left[0] - left_a0),
                right[1] - left[1],
            ),
            axis=0,
        )
        middle = (
            s_right[None, :] * fl
            - s_left[None, :] * fr
            + (s_left * s_right)[None, :] * jump
        ) / safe_span[None, :]
        middle = jnp.where((span <= 1e-14)[None, :], 0.5 * (fl + fr), middle)
        result = jnp.where((s_left >= 0.0)[None, :], fl, middle)
        return jnp.where((s_right <= 0.0)[None, :], fr, result)

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

    def rhs(U, pc, time_s):
        inlet_a, inlet_q, outlet_a, outlet_q, dpc = boundary_states(U, pc, time_s)
        perturb = jnp.stack((U[0] - a0, U[1]), axis=0)
        backward = perturb - perturb[:, p["prev_cell"]]
        forward = perturb[:, p["next_cell"]] - perturb
        same_sign = jnp.sign(backward) == jnp.sign(forward)
        slopes = jnp.where(
            same_sign,
            jnp.sign(backward) * jnp.minimum(jnp.abs(backward), jnp.abs(forward)),
            0.0,
        )
        slopes = jnp.where(p["interior_cell_mask"][None, :], slopes, 0.0)
        left_perturb = perturb - 0.5 * slopes
        right_perturb = perturb + 0.5 * slopes
        left_cell_state = jnp.stack(
            (jnp.maximum(a0 + left_perturb[0], 1e-12), left_perturb[1]), axis=0
        )
        right_cell_state = jnp.stack(
            (jnp.maximum(a0 + right_perturb[0], 1e-12), right_perturb[1]), axis=0
        )

        left_state = right_cell_state[:, p["face_left_cell"]]
        right_state = left_cell_state[:, p["face_right_cell"]]
        left_state = left_state.at[:, p["inlet_face"]].set(
            jnp.stack((inlet_a, inlet_q), axis=0)
        )
        right_state = right_state.at[:, p["outlet_face"]].set(
            jnp.stack((outlet_a, outlet_q), axis=0)
        )
        face_flux = hll(
            left_state,
            right_state,
            a0[p["face_left_cell"]],
            a0[p["face_right_cell"]],
            beta[p["face_left_cell"]],
            beta[p["face_right_cell"]],
        )
        derivative = -(
            face_flux[:, p["cell_right_face"]] - face_flux[:, p["cell_left_face"]]
        ) / dx[None, :]

        derivative = derivative.at[1].add(friction_coefficient * U[1] / U[0])

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
        derivative = derivative.at[1].add(
            area / rho * (
                psi[p["cell_right_face"]] - psi[p["cell_left_face"]]
            ) / dx
        )

        pressure_gradient = (
            p["loss_linear_density"] * q
            + p["loss_quadratic_density"] * q * jnp.abs(q)
        )
        mass_factor = 1.0 + area / rho * p["loss_inertance_density"]
        derivative = derivative.at[1].set(
            (derivative[1] - area / rho * pressure_gradient) / mass_factor
        )
        return derivative, dpc

    def stability(U):
        area = U[0]
        flow = U[1]
        velocity = flow / area
        c = wave_speed(area, a0, beta)
        radical = jnp.sqrt(c * c + alpha * (alpha - 1.0) * velocity * velocity)
        speed = jnp.maximum(
            jnp.abs(alpha * velocity - radical),
            jnp.abs(alpha * velocity + radical),
        )
        max_cfl_rate = jnp.max(speed / dx)
        dt_hyperbolic = cfl / jnp.maximum(max_cfl_rate, 1e-12)
        diffusion_rate = 2.0 * gamma * jnp.sqrt(area) / rho / (dx * dx)
        max_diffusion_rate = jnp.max(diffusion_rate)
        dt_diffusion = jnp.where(
            max_diffusion_rate > 0.0,
            diffusion_safety / max_diffusion_rate,
            jnp.inf,
        )
        resistance_density = (
            p["loss_linear_density"]
            + 2.0 * p["loss_quadratic_density"] * jnp.abs(flow)
        )
        denominator = 1.0 + area / rho * p["loss_inertance_density"]
        maximum_loss_rate = jnp.max(area / rho * resistance_density / denominator)
        dt_loss = jnp.where(maximum_loss_rate > 0.0, cfl / maximum_loss_rate, jnp.inf)
        dt = jnp.minimum(jnp.minimum(dt_hyperbolic, dt_diffusion), dt_loss)
        return dt, max_cfl_rate, max_diffusion_rate, dt_loss

    def apply_floor(U):
        return U.at[0].set(jnp.maximum(U[0], area_floor_ratio * a0))

    def rk2(U, pc, time_s, dt):
        k1, pc1 = rhs(U, pc, time_s)
        stage = apply_floor(U + dt * k1)
        pc_stage = pc + dt * pc1
        k2, pc2 = rhs(stage, pc_stage, time_s + dt)
        updated = apply_floor(0.5 * (U + stage + dt * k2))
        pc_updated = 0.5 * (pc + pc_stage + dt * pc2)
        return updated, pc_updated

    def cycle_kernel(U0, pc0, absolute_start):
        initial = (
            U0,
            pc0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(False, dtype=jnp.bool_),
            jnp.asarray(0, dtype=jnp.int32),
        )

        def cond(carry):
            _, _, phase, _, _, invalid, steps = carry
            return (
                (phase < period - 1e-14)
                & (~invalid)
                & (steps < max_steps_per_cycle)
            )

        def body(carry):
            U, pc, phase, max_cfl, max_diffusion, invalid, steps = carry
            dt_stable, cfl_rate, diffusion_rate, _ = stability(U)
            dt = jnp.minimum(dt_stable, period - phase)
            invalid_dt = (~jnp.isfinite(dt)) | (dt <= 0.0)
            safe_dt = jnp.where(invalid_dt, 1e-12, dt)
            updated, pc_updated = rk2(U, pc, absolute_start + phase, safe_dt)
            floor = area_floor_ratio * a0
            invalid_state = (
                (~jnp.all(jnp.isfinite(updated)))
                | (~jnp.all(jnp.isfinite(pc_updated)))
                | jnp.any(updated[0] <= floor)
            )
            return (
                updated,
                pc_updated,
                phase + safe_dt,
                jnp.maximum(max_cfl, cfl_rate * safe_dt),
                jnp.maximum(max_diffusion, diffusion_rate * safe_dt),
                invalid | invalid_dt | invalid_state,
                steps + 1,
            )

        return lax.while_loop(cond, body, initial)

    def dt_sequence_kernel(U0, pc0, absolute_start):
        initial = (
            U0,
            pc0,
            jnp.asarray(0.0, dtype=jnp.float64),
            jnp.asarray(False, dtype=jnp.bool_),
            jnp.asarray(0, dtype=jnp.int32),
            jnp.zeros((max_steps_per_cycle,), dtype=jnp.float64),
        )

        def cond(carry):
            _, _, phase, invalid, steps, _ = carry
            return (
                (phase < period - 1e-14)
                & (~invalid)
                & (steps < max_steps_per_cycle)
            )

        def body(carry):
            U, pc, phase, invalid, steps, dts = carry
            dt_stable, _, _, _ = stability(U)
            dt = jnp.minimum(dt_stable, period - phase)
            invalid_dt = (~jnp.isfinite(dt)) | (dt <= 0.0)
            safe_dt = jnp.where(invalid_dt, 1e-12, dt)
            updated, pc_updated = rk2(U, pc, absolute_start + phase, safe_dt)
            floor = area_floor_ratio * a0
            invalid_state = (
                (~jnp.all(jnp.isfinite(updated)))
                | (~jnp.all(jnp.isfinite(pc_updated)))
                | jnp.any(updated[0] <= floor)
            )
            return (
                updated,
                pc_updated,
                phase + safe_dt,
                invalid | invalid_dt | invalid_state,
                steps + 1,
                dts.at[steps].set(safe_dt),
            )

        return lax.while_loop(cond, body, initial)

    def history_kernel(U0, pc0, absolute_start, dts):
        def step(carry, dt):
            U, pc, phase = carry
            updated, pc_updated = rk2(U, pc, absolute_start + phase, dt)
            return (updated, pc_updated, phase + dt), updated

        (_, _, _), tail = lax.scan(
            step,
            (U0, pc0, jnp.asarray(0.0, dtype=jnp.float64)),
            dts,
        )
        return jnp.concatenate((U0[None, :, :], tail), axis=0)

    return (
        jax.jit(rhs),
        jax.jit(stability),
        jax.jit(cycle_kernel),
        jax.jit(dt_sequence_kernel),
        jax.jit(history_kernel),
    )


def _initial_flat_state(baseline: BaselineCardiovascularState, problem: _FlatProblem):
    U = np.zeros((2, problem.a0_m2.size), dtype=float)
    U[0] = problem.a0_m2
    pc = np.full(len(problem.segment_ids), baseline.diastolic_pressure_pa, dtype=float)
    return jnp.asarray(U, dtype=jnp.float64), jnp.asarray(pc, dtype=jnp.float64)


def _split_flat_state(problem: _FlatProblem, values: np.ndarray) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for sid, start, end in zip(problem.segment_ids, problem.starts, problem.ends, strict=True):
        result[sid] = np.asarray(values[:, int(start) : int(end) + 1], dtype=float)
    return result


def jax_operator_snapshot(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    conserved: dict[str, np.ndarray],
    capacitor_pressures: dict[str, float],
    *,
    pressure_losses: tuple[LocalizedPressureLoss, ...] = (),
    time_s: float = 0.0,
    options: SolverOptions | None = None,
) -> JaxOperatorSnapshot:
    """Evaluate the JAX RHS/stability operators without advancing the solution."""
    resolved = SolverOptions() if options is None else options
    if not isinstance(resolved, SolverOptions):
        raise TypeError("options must be SolverOptions or None")
    problem = _flatten_problem(baseline, network, pressure_losses)
    rhs_fn, stability_fn, _, _, _ = _kernel_factory(
        baseline, problem, resolved, max_steps_per_cycle=2
    )
    U = np.zeros((2, problem.a0_m2.size), dtype=float)
    for sid, start, end in zip(problem.segment_ids, problem.starts, problem.ends, strict=True):
        if sid not in conserved:
            raise ValueError(f"conserved state is missing segment {sid!r}")
        item = np.asarray(conserved[sid], dtype=float)
        expected = (2, int(end) - int(start) + 1)
        if item.shape != expected:
            raise ValueError(
                f"conserved segment {sid!r} has shape {item.shape}; expected {expected}"
            )
        U[:, int(start) : int(end) + 1] = item
    pc = np.full(len(problem.segment_ids), baseline.diastolic_pressure_pa, dtype=float)
    for index, sid in enumerate(problem.segment_ids):
        if problem.terminal_mask[index]:
            if sid not in capacitor_pressures:
                raise ValueError(f"capacitor state is missing terminal segment {sid!r}")
            pc[index] = float(capacitor_pressures[sid])

    U_jax = jnp.asarray(U, dtype=jnp.float64)
    dU, dpc = rhs_fn(
        U_jax,
        jnp.asarray(pc, dtype=jnp.float64),
        jnp.asarray(float(time_s), dtype=jnp.float64),
    )
    dt, cfl_rate, diffusion_rate, loss_dt = stability_fn(U_jax)
    dU_np = np.asarray(dU, dtype=float)
    dpc_np = np.asarray(dpc, dtype=float)
    return JaxOperatorSnapshot(
        derivatives=_split_flat_state(problem, dU_np),
        capacitor_derivatives={
            sid: float(dpc_np[index])
            for index, sid in enumerate(problem.segment_ids)
            if problem.terminal_mask[index]
        },
        stability_dt_s=float(np.asarray(dt)),
        hyperbolic_cfl_rate_per_s=float(np.asarray(cfl_rate)),
        diffusion_rate_per_s=float(np.asarray(diffusion_rate)),
        disease_loss_dt_s=float(np.asarray(loss_dt)),
    )


class JaxDiseaseOneDSolver:
    """JIT-compiled flattened-network backend for Virtual Disease haemodynamics."""

    __slots__ = ("_options", "_max_steps_per_cycle", "_last_timing")

    def __init__(
        self,
        options: SolverOptions | None = None,
        *,
        max_steps_per_cycle: int = 500_000,
    ) -> None:
        self._options = SolverOptions() if options is None else options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("options must be SolverOptions")
        if (
            isinstance(max_steps_per_cycle, bool)
            or not isinstance(max_steps_per_cycle, int)
            or max_steps_per_cycle < 1
        ):
            raise ValueError("max_steps_per_cycle must be a positive integer")
        self._max_steps_per_cycle = max_steps_per_cycle
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
        if abs(period - baseline.cardiac_period_s) > max(
            0.01, 0.02 * baseline.cardiac_period_s
        ):
            raise NumericalMethodError(
                "source aortic inflow duration is inconsistent with subject heart rate"
            )

        total_start = time.perf_counter()
        problem = _flatten_problem(baseline, network, pressure_losses)
        _, _, cycle_fn, dt_sequence_fn, history_fn = _kernel_factory(
            baseline, problem, self._options, self._max_steps_per_cycle
        )
        U, pc = _initial_flat_state(baseline, problem)

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
            invalid_value = bool(np.asarray(invalid))
            step_value = int(np.asarray(steps))
            if step_value >= self._max_steps_per_cycle and phase_value < period - 1e-12:
                raise NumericalMethodError(
                    "JAX disease solver exceeded max_steps_per_cycle before completing a cardiac cycle"
                )
            if invalid_value:
                raise NumericalMethodError(
                    "JAX disease solver produced an invalid state or reached its configured area floor"
                )

            start_np = np.asarray(start_U, dtype=float)
            end_np = np.asarray(U, dtype=float)
            diff = end_np - start_np
            convergence = float(
                np.sqrt(
                    float(np.sum(diff * diff))
                    / max(float(np.sum(start_np * start_np)), 1e-30)
                )
            )
            maximum_cfl = max(maximum_cfl, float(np.asarray(cycle_cfl)))
            maximum_diffusion = max(
                maximum_diffusion, float(np.asarray(cycle_diffusion))
            )
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

        replay_start = time.perf_counter()
        replay_U, _, replay_phase, replay_invalid, replay_steps, dt_values = dt_sequence_fn(
            final_start_U,
            final_start_pc,
            jnp.asarray(final_cycle_index * period, dtype=jnp.float64),
        )
        replay_U.block_until_ready()
        replay_wall = time.perf_counter() - replay_start
        replay_count = int(np.asarray(replay_steps))
        replay_phase_value = float(np.asarray(replay_phase))
        if bool(np.asarray(replay_invalid)):
            raise NumericalMethodError("JAX final-cycle replay produced an invalid state")
        if replay_count >= self._max_steps_per_cycle and replay_phase_value < period - 1e-12:
            raise NumericalMethodError("JAX final-cycle replay exceeded max_steps_per_cycle")
        if replay_count != final_steps:
            raise NumericalMethodError(
                "JAX final-cycle replay changed the adaptive step count"
            )

        dt_host = np.asarray(dt_values, dtype=float)[:replay_count]
        history_start = time.perf_counter()
        history = history_fn(
            final_start_U,
            final_start_pc,
            jnp.asarray(final_cycle_index * period, dtype=jnp.float64),
            jnp.asarray(dt_host, dtype=jnp.float64),
        )
        history.block_until_ready()
        history_wall = time.perf_counter() - history_start
        history_np = np.asarray(history, dtype=float)
        final_time = np.concatenate((np.asarray([0.0], dtype=float), np.cumsum(dt_host)))
        if final_time.size != history_np.shape[0]:
            raise RuntimeError("JAX history/time dimensions are inconsistent")
        if not math.isclose(
            float(final_time[-1]),
            period,
            rel_tol=0.0,
            abs_tol=max(1e-11, 1e-10 * period),
        ):
            raise NumericalMethodError(
                "JAX final-cycle history does not terminate at the cardiac period"
            )

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
            if problem.terminal_mask[index]:
                terminal_flow_histories.append(flow[:, -1])

        duration = float(final_time[-1] - final_time[0])
        if duration <= 0:
            raise NumericalMethodError("JAX final-cycle history has non-positive duration")
        root_mean = baseline.aortic_inflow.mean_flow_m3_per_s
        terminal_mean = sum(
            float(np.trapezoid(item, final_time) / duration)
            for item in terminal_flow_histories
        )
        terminal_mass_balance = abs(root_mean - terminal_mean) / max(
            abs(root_mean), 1e-12
        )

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
            time_s=final_time,
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
            history_compile_and_execute_s=history_wall,
            final_cycle_steps=replay_count,
            platform=str(getattr(device, "platform", "unknown")),
            device=str(device),
            x64_enabled=bool(jax.config.x64_enabled),
        )
        return solution


__all__ = [
    "JaxDiseaseOneDSolver",
    "JaxOperatorSnapshot",
    "JaxSolverTiming",
    "jax_operator_snapshot",
]
