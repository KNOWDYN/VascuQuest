"""Optional pyva network backend for VascuQuest cardioacoustics."""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from vascuquest.analysis.core import require_optional_dependency
from vascuquest.disease.baseline.model import BaselineCardiovascularState, BaselineSegment
from vascuquest.disease.solver.network import NetworkDiscretization, build_network
from vascuquest.errors import AdmissibilityError, NumericalMethodError
from .arterial import arterial_mode_spectrum
from .endothelium import endothelial_load_in_uniform_cell
from .model import (
    CardioacousticNetworkSolution,
    CardioacousticSourceSpectrum,
    CellCardioacousticSolution,
)

PYVA_BACKEND_ID = "vascuquest:cardioacoustics:pyva-1d-v1"


@dataclass(frozen=True, slots=True)
class _Cell:
    segment_id: str
    cell_index: int
    length_m: float
    axial_position_m: float
    area_m2: float
    beta_pa: float
    gamma_pa_s_per_m: float


@dataclass(frozen=True, slots=True)
class _SegmentAssembly:
    segment: BaselineSegment
    cells: tuple[_Cell, ...]
    transfer_matrices: tuple[np.ndarray, ...]
    total_transfer: np.ndarray
    terminal_impedance: np.ndarray


def _segment_cells(mesh) -> tuple[_Cell, ...]:
    cells: list[_Cell] = []
    left_edge = 0.0
    for i in range(mesh.cell_count):
        length = float(mesh.dx_m[i])
        cells.append(
            _Cell(
                segment_id=mesh.segment_id,
                cell_index=i,
                length_m=length,
                axial_position_m=left_edge + 0.5 * length,
                area_m2=float(mesh.reference_area_m2[i]),
                beta_pa=float(mesh.beta_pa[i]),
                gamma_pa_s_per_m=float(mesh.source_gamma_pa_s_per_m[i]),
            )
        )
        left_edge += length
    return tuple(cells)


def _cell_transfer(mode, length_m: float) -> np.ndarray:
    k_l = mode.wavenumber_per_m * length_m
    zc = mode.characteristic_impedance_pa_s_per_m3
    c = np.cos(k_l)
    s = np.sin(k_l)
    matrix = np.empty((2, 2, mode.frequency_hz.size), dtype=np.complex128)
    matrix[0, 0, :] = c
    matrix[0, 1, :] = 1j * zc * s
    matrix[1, 0, :] = 1j * s / zc
    matrix[1, 1, :] = c
    return matrix


def _cascade(transfers: tuple[np.ndarray, ...], n_frequency: int) -> np.ndarray:
    total = np.repeat(np.eye(2, dtype=np.complex128)[:, :, None], n_frequency, axis=2)
    for transfer in transfers:
        total = np.einsum("abf,bcf->acf", total, transfer, optimize=True)
    return total


def _assemble_segment(
    baseline: BaselineCardiovascularState,
    segment: BaselineSegment,
    mesh,
    frequency_hz: np.ndarray,
) -> _SegmentAssembly:
    cells = _segment_cells(mesh)
    transfers: list[np.ndarray] = []
    last_mode = None
    for cell in cells:
        mode = arterial_mode_spectrum(
            frequency_hz,
            area_m2=cell.area_m2,
            beta_pa=cell.beta_pa,
            gamma_pa_s_per_m=cell.gamma_pa_s_per_m,
            density_kg_per_m3=baseline.blood_density_kg_per_m3,
            viscosity_pa_s=baseline.blood_viscosity_pa_s,
        )
        transfers.append(_cell_transfer(mode, cell.length_m))
        last_mode = mode
    if last_mode is None:
        raise NumericalMethodError(f"segment {segment.segment_id!r} has no cardioacoustic cells")
    total = _cascade(tuple(transfers), frequency_hz.size)
    return _SegmentAssembly(
        segment=segment,
        cells=cells,
        transfer_matrices=tuple(transfers),
        total_transfer=total,
        terminal_impedance=last_mode.characteristic_impedance_pa_s_per_m3,
    )


def _segment_dynamic_matrix(mC, dof, xdata, assembly: _SegmentAssembly):
    transfer = assembly.total_transfer
    a = transfer[0, 0, :]
    b = transfer[0, 1, :]
    d = transfer[1, 1, :]
    if np.any(np.abs(b) < 1e-18):
        raise NumericalMethodError(
            f"segment {assembly.segment.segment_id!r} is singular at an exact two-port resonance"
        )
    # Convert the physical transfer relation [p_in, q_in]^T = T
    # [p_out, q_out]^T to a nodal admittance with volume flow positive
    # *into* the element at both ports. For reciprocal T this is symmetric:
    # Y = [[D/B, -1/B], [-1/B, A/B]]. pyva then handles DOF-indexed
    # assembly at the vascular junctions without defining the arterial physics.
    data = np.empty((3, b.size), dtype=np.complex128)
    data[0, :] = d / b
    data[1, :] = -1.0 / b
    data[2, :] = a / b
    ids = [assembly.segment.inlet_node, assembly.segment.outlet_node]
    pdof = dof.DOF(ids, [0, 0], dof.DOFtype(typestr="pressure"))
    qdof = dof.DOF(ids, [1, 1], dof.DOFtype(typestr="volume flow"))
    return mC.DynamicMatrix(data, xdata, pdof, qdof, sym=1, shape=(2, 2, b.size))


def _point_admittance_matrix(mC, dof, xdata, node: int, admittance: np.ndarray):
    pdof = dof.DOF([node], [0], dof.DOFtype(typestr="pressure"))
    qdof = dof.DOF([node], [1], dof.DOFtype(typestr="volume flow"))
    data = np.asarray(admittance, dtype=np.complex128).reshape(1, -1)
    return mC.DynamicMatrix(data, xdata, pdof, qdof, sym=1, shape=(1, 1, admittance.size))


def _reconstruct_segment_pressures(
    assembly: _SegmentAssembly,
    proximal_pressure: np.ndarray,
    distal_pressure: np.ndarray,
) -> tuple[np.ndarray, ...]:
    total = assembly.total_transfer
    a = total[0, 0, :]
    b = total[0, 1, :]
    if np.any(np.abs(b) < 1e-18):
        raise NumericalMethodError(
            f"segment {assembly.segment.segment_id!r} cannot be reconstructed at an exact resonance"
        )
    distal_flow = (proximal_pressure - a * distal_pressure) / b
    state = np.vstack((distal_pressure, distal_flow))
    boundaries: list[np.ndarray | None] = [None] * (len(assembly.cells) + 1)
    boundaries[-1] = distal_pressure
    for index in range(len(assembly.cells) - 1, -1, -1):
        state = np.einsum(
            "abf,bf->af", assembly.transfer_matrices[index], state, optimize=True
        )
        boundaries[index] = state[0, :].copy()
    if not np.allclose(boundaries[0], proximal_pressure, rtol=1e-7, atol=1e-10):
        raise NumericalMethodError(
            f"segment {assembly.segment.segment_id!r} failed transfer-matrix pressure reconstruction"
        )
    return tuple(np.asarray(item, dtype=np.complex128) for item in boundaries)


def solve_pyva_network(
    baseline: BaselineCardiovascularState,
    source: CardioacousticSourceSpectrum,
    *,
    network: NetworkDiscretization | None = None,
    terminal_model: str = "matched",
) -> CardioacousticNetworkSolution:
    """Propagate a prescribed root pressure spectrum through a VascuQuest tree.

    pyva supplies pressure/volume-flow dynamic-matrix assembly at arterial
    junctions. VascuQuest supplies the coupled blood-wall propagation law,
    heterogeneous segment transfer matrices, causal wall state and endothelial
    receiver. The root pressure is imposed exactly so wall states can be
    compared under identical cardiac acoustic excitation.
    """

    if not isinstance(baseline, BaselineCardiovascularState):
        raise TypeError("baseline must be a BaselineCardiovascularState")
    if not isinstance(source, CardioacousticSourceSpectrum):
        raise TypeError("source must be a CardioacousticSourceSpectrum")
    resolved_network = build_network(baseline) if network is None else network
    if not isinstance(resolved_network, NetworkDiscretization):
        raise TypeError("network must be a NetworkDiscretization")
    if terminal_model != "matched":
        raise AdmissibilityError("v1 cardioacoustics supports terminal_model='matched' only")

    mC = require_optional_dependency("pyva.data.matrixClasses", "cardioacoustics")
    dof = require_optional_dependency("pyva.data.dof", "cardioacoustics")
    models = require_optional_dependency("pyva.models", "cardioacoustics")

    frequency = source.frequency_hz
    omega = 2.0 * math.pi * frequency
    xdata = mC.DataAxis(omega, typestr="angular frequency")
    segment_by_id = {segment.segment_id: segment for segment in baseline.segments}
    if tuple(mesh.segment_id for mesh in resolved_network.meshes) != tuple(segment_by_id):
        raise AdmissibilityError(
            "cardioacoustic network must preserve baseline segment identity and order"
        )

    assemblies: dict[str, _SegmentAssembly] = {}
    for mesh in resolved_network.meshes:
        segment = segment_by_id[mesh.segment_id]
        assemblies[mesh.segment_id] = _assemble_segment(
            baseline, segment, mesh, frequency
        )

    node_ids = tuple(
        sorted(
            {
                node
                for segment in baseline.segments
                for node in (segment.inlet_node, segment.outlet_node)
            }
        )
    )
    ptype = dof.DOFtype(typestr="pressure")
    qtype = dof.DOFtype(typestr="volume flow")
    excdof = dof.DOF(list(node_ids), [0], ptype, repetition=True)
    resdof = dof.DOF(list(node_ids), [1], qtype, repetition=True)
    va = models.VAmodel(None, xdata, excdof, resdof, sym=1, dtype=complex)

    for assembly in assemblies.values():
        va += _segment_dynamic_matrix(mC, dof, xdata, assembly)

    for segment_id in baseline.terminal_segment_ids:
        assembly = assemblies[segment_id]
        va += _point_admittance_matrix(
            mC,
            dof,
            xdata,
            assembly.segment.outlet_node,
            1.0 / assembly.terminal_impedance,
        )

    matrix = np.asarray(va.data, dtype=np.complex128)
    if matrix.shape != (len(node_ids), len(node_ids), frequency.size):
        raise NumericalMethodError("pyva assembled an unexpected cardioacoustic matrix shape")
    root = baseline.root_segment.inlet_node
    try:
        root_index = node_ids.index(root)
    except ValueError as exc:
        raise NumericalMethodError("root node is absent from assembled cardioacoustic network") from exc
    unknown = np.asarray([i for i in range(len(node_ids)) if i != root_index], dtype=int)
    pressure = np.zeros((frequency.size, len(node_ids)), dtype=np.complex128)
    pressure[:, root_index] = source.pressure_pa
    for i in range(frequency.size):
        y = matrix[:, :, i]
        rhs = -y[np.ix_(unknown, [root_index])].ravel() * source.pressure_pa[i]
        try:
            pressure[i, unknown] = np.linalg.solve(y[np.ix_(unknown, unknown)], rhs)
        except np.linalg.LinAlgError as exc:
            raise NumericalMethodError(
                f"cardioacoustic network is singular at {frequency[i]:.6g} Hz"
            ) from exc

    node_index = {node: i for i, node in enumerate(node_ids)}
    solved_cells: list[CellCardioacousticSolution] = []
    for segment in baseline.segments:
        assembly = assemblies[segment.segment_id]
        boundaries = _reconstruct_segment_pressures(
            assembly,
            pressure[:, node_index[segment.inlet_node]],
            pressure[:, node_index[segment.outlet_node]],
        )
        for cell, p0, p1 in zip(assembly.cells, boundaries[:-1], boundaries[1:]):
            load = endothelial_load_in_uniform_cell(
                frequency,
                p0,
                p1,
                length_m=cell.length_m,
                area_m2=cell.area_m2,
                beta_pa=cell.beta_pa,
                gamma_pa_s_per_m=cell.gamma_pa_s_per_m,
                density_kg_per_m3=baseline.blood_density_kg_per_m3,
                viscosity_pa_s=baseline.blood_viscosity_pa_s,
                axial_fraction=0.5,
            )
            solved_cells.append(
                CellCardioacousticSolution(
                    segment_id=cell.segment_id,
                    cell_index=cell.cell_index,
                    axial_position_m=cell.axial_position_m,
                    node_in=segment.inlet_node,
                    node_out=segment.outlet_node,
                    load=load,
                )
            )

    return CardioacousticNetworkSolution(
        frequency_hz=frequency,
        node_ids=node_ids,
        node_pressure_pa=pressure,
        cells=tuple(solved_cells),
        source_identity=source.source_identity,
        source_citations=source.citations,
        backend_id=PYVA_BACKEND_ID,
        terminal_model=terminal_model,
    )


__all__ = ["PYVA_BACKEND_ID", "solve_pyva_network"]
