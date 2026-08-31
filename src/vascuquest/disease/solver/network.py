"""PWDB-compatible arterial wall coefficients and network discretisation.

The constitutive quantities follow the parameterisation used by the PWDB
input generator and the Nektar1D beta-law convention. Source radii are
interpreted as diastolic radii, consistent with the PWDB publication.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState, BaselineSegment

from .model import SegmentMesh, SolverOptions


def wall_eh_n_per_m(
    state: BaselineCardiovascularState,
    radius_m: np.ndarray | float,
) -> np.ndarray:
    """Return ``Eh`` in N/m using the exact PWDB input-generator relation.

    Upstream PWDB writes::

        Eh = 0.1*(k1*exp(k2*100*r)+k3)*r

    with ``r`` in metres and ``k`` in the exported model-configuration units.
    """

    radius = np.asarray(radius_m, dtype=float)
    return 0.1 * (
        state.stiffness_k1_g_per_s2_per_cm
        * np.exp(state.stiffness_k2_per_cm * 100.0 * radius)
        + state.stiffness_k3_g_per_s2_per_cm
    ) * radius


def wall_gamma_source(
    state: BaselineCardiovascularState,
    radius_m: np.ndarray | float,
) -> np.ndarray:
    """Return the exact Voigt-wall ``Gamma`` coefficient written by PWDB.

    The resulting SI unit is Pa s / m. The expression is retained verbatim
    from the public PWDB Nektar input generator after unit conversion.
    """

    radius = np.asarray(radius_m, dtype=float)
    return (
        4.0
        / math.pi
        * (
            state.wall_gamma_b1_g_cm_per_s / (2.0 * 100.0 * radius)
            + state.wall_gamma_b0_g_per_s
        )
        / 1000.0
        / (2.0 * radius) ** 2
    )


class ThinWallLaw:
    """PWDB/Nektar beta-law expressed relative to diastolic area and pressure.

    ``beta_pa`` is the pressure-scale form ``4 Eh / (3 R_d)``. It is
    algebraically equivalent to Nektar's ``beta`` coefficient multiplying
    ``sqrt(A) - sqrt(A_d)``.
    """

    @staticmethod
    def pressure_pa(
        area_m2: np.ndarray | float,
        reference_area_m2: np.ndarray | float,
        beta_pa: np.ndarray | float,
        reference_pressure_pa: float,
    ) -> np.ndarray:
        area = np.asarray(area_m2, dtype=float)
        a0 = np.asarray(reference_area_m2, dtype=float)
        beta = np.asarray(beta_pa, dtype=float)
        return reference_pressure_pa + beta * (np.sqrt(area / a0) - 1.0)

    @staticmethod
    def area_from_pressure(
        pressure_pa: np.ndarray | float,
        reference_area_m2: np.ndarray | float,
        beta_pa: np.ndarray | float,
        reference_pressure_pa: float,
    ) -> np.ndarray:
        pressure = np.asarray(pressure_pa, dtype=float)
        a0 = np.asarray(reference_area_m2, dtype=float)
        beta = np.asarray(beta_pa, dtype=float)
        factor = 1.0 + (pressure - reference_pressure_pa) / beta
        factor = np.maximum(factor, 1e-6)
        return a0 * factor * factor

    @staticmethod
    def wave_speed_m_per_s(
        area_m2: np.ndarray | float,
        reference_area_m2: np.ndarray | float,
        beta_pa: np.ndarray | float,
        density_kg_per_m3: float,
    ) -> np.ndarray:
        area = np.asarray(area_m2, dtype=float)
        a0 = np.asarray(reference_area_m2, dtype=float)
        beta = np.asarray(beta_pa, dtype=float)
        return np.sqrt(beta / (2.0 * density_kg_per_m3)) * np.power(area / a0, 0.25)

    @staticmethod
    def pressure_potential(
        area_m2: np.ndarray | float,
        reference_area_m2: np.ndarray | float,
        beta_pa: np.ndarray | float,
        density_kg_per_m3: float,
    ) -> np.ndarray:
        """Pressure contribution to the conservative momentum flux.

        The reference-state potential is subtracted so a tapered, heterogeneous
        artery at uniform diastolic pressure is a discrete zero-flow equilibrium.
        """

        area = np.asarray(area_m2, dtype=float)
        a0 = np.asarray(reference_area_m2, dtype=float)
        beta = np.asarray(beta_pa, dtype=float)
        coefficient = beta / (3.0 * density_kg_per_m3 * np.sqrt(a0))
        return coefficient * (np.power(area, 1.5) - np.power(a0, 1.5))


class VoigtWallLaw:
    """Voigt wall-pressure correction used by the PWDB/Nektar model.

    With continuity, Nektar's term ``-Gamma/sqrt(A) * dQ/dx`` is equivalent
    to ``Gamma/sqrt(A) * dA/dt``. The native solver treats its momentum effect
    explicitly as a diffusion-like source and uses this helper for reporting
    total pressure during reconstruction.
    """

    @staticmethod
    def total_pressure_pa(
        elastic_pressure_pa: np.ndarray,
        area_m2: np.ndarray,
        flow_m3_per_s: np.ndarray,
        x_m: np.ndarray,
        gamma_pa_s_per_m: np.ndarray,
    ) -> np.ndarray:
        elastic = np.asarray(elastic_pressure_pa, dtype=float)
        area = np.asarray(area_m2, dtype=float)
        flow = np.asarray(flow_m3_per_s, dtype=float)
        x = np.asarray(x_m, dtype=float)
        gamma = np.asarray(gamma_pa_s_per_m, dtype=float)
        if area.shape != flow.shape or elastic.shape != area.shape:
            raise ValueError("elastic pressure, area and flow histories must share shape")
        if area.ndim != 2 or area.shape[1] != x.size or gamma.shape != x.shape:
            raise ValueError("Voigt wall arrays are not spatially aligned")
        edge_order = 2 if x.size >= 3 else 1
        dqdx = np.gradient(flow, x, axis=1, edge_order=edge_order)
        return elastic - gamma[None, :] * dqdx / np.sqrt(area)


@dataclass(frozen=True, slots=True)
class NetworkDiscretization:
    meshes: tuple[SegmentMesh, ...]

    def mesh(self, segment_id: str) -> SegmentMesh:
        for item in self.meshes:
            if item.segment_id == segment_id:
                return item
        raise KeyError(segment_id)


def _segment_mesh(
    state: BaselineCardiovascularState,
    segment: BaselineSegment,
    options: SolverOptions,
) -> SegmentMesh:
    cells = max(
        options.minimum_cells_per_segment,
        int(math.ceil(segment.length_m / options.target_dx_m)),
    )
    edges = np.linspace(0.0, segment.length_m, cells + 1)
    x = 0.5 * (edges[:-1] + edges[1:])
    dx = np.diff(edges)
    fraction = x / segment.length_m
    radius = segment.inlet_radius_m + fraction * (
        segment.outlet_radius_m - segment.inlet_radius_m
    )
    a0 = math.pi * radius * radius
    eh = wall_eh_n_per_m(state, radius)
    beta = 4.0 * eh / (3.0 * radius)
    gamma = wall_gamma_source(state, radius)
    return SegmentMesh(
        segment_id=segment.segment_id,
        x_m=x,
        dx_m=dx,
        reference_area_m2=a0,
        beta_pa=beta,
        source_gamma_pa_s_per_m=gamma,
    )


def build_network(
    state: BaselineCardiovascularState,
    options: SolverOptions | None = None,
) -> NetworkDiscretization:
    if not isinstance(state, BaselineCardiovascularState):
        raise TypeError("state must be a BaselineCardiovascularState")
    resolved = SolverOptions() if options is None else options
    if not isinstance(resolved, SolverOptions):
        raise TypeError("options must be SolverOptions")
    return NetworkDiscretization(
        tuple(_segment_mesh(state, segment, resolved) for segment in state.segments)
    )


__all__ = [
    "NetworkDiscretization",
    "ThinWallLaw",
    "VoigtWallLaw",
    "build_network",
    "wall_eh_n_per_m",
    "wall_gamma_source",
]
