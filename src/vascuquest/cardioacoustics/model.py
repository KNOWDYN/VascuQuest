"""Value objects for analytical cardioacoustic propagation in arteries."""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


def _readonly_real(values: object, name: str, *, ndim: int = 1) -> np.ndarray:
    array = np.asarray(values, dtype=float).copy()
    if array.ndim != ndim or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite {ndim}-D array")
    array.setflags(write=False)
    return array


def _readonly_complex(values: object, name: str, *, ndim: int = 1) -> np.ndarray:
    array = np.asarray(values, dtype=np.complex128).copy()
    if array.ndim != ndim or array.size == 0:
        raise ValueError(f"{name} must be a non-empty {ndim}-D array")
    if not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag)):
        raise ValueError(f"{name} must contain finite complex values")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True, eq=False)
class CardioacousticSourceSpectrum:
    """Prescribed root pressure spectrum for endogenous cardiohemic excitation.

    The source is deliberately independent of PWDB haemodynamic harmonics.  It
    represents an externally constrained pressure phasor spectrum, normally
    derived from invasive or otherwise qualified heart-sound measurements.

    The phasor convention used throughout the module is ``Re[p exp(i omega t)]``.
    A forward travelling wave is therefore proportional to ``exp(-i k x)``.
    """

    frequency_hz: np.ndarray
    pressure_pa: np.ndarray
    source_identity: str
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        frequency = _readonly_real(self.frequency_hz, "frequency_hz")
        pressure = _readonly_complex(self.pressure_pa, "pressure_pa")
        if frequency.shape != pressure.shape:
            raise ValueError("frequency_hz and pressure_pa must have identical shape")
        if np.any(frequency <= 0) or np.any(np.diff(frequency) <= 0):
            raise ValueError("frequency_hz must be strictly increasing and positive")
        if not isinstance(self.source_identity, str) or not self.source_identity.strip():
            raise ValueError("source_identity must be a non-empty string")
        if not isinstance(self.citations, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.citations
        ):
            raise ValueError("citations must be a tuple of non-empty strings")
        object.__setattr__(self, "frequency_hz", frequency)
        object.__setattr__(self, "pressure_pa", pressure)

    @classmethod
    def from_amplitude_phase(
        cls,
        frequency_hz: object,
        amplitude_pa: object,
        phase_rad: object,
        *,
        source_identity: str,
        citations: tuple[str, ...] = (),
    ) -> "CardioacousticSourceSpectrum":
        frequency = np.asarray(frequency_hz, dtype=float)
        amplitude = np.asarray(amplitude_pa, dtype=float)
        phase = np.asarray(phase_rad, dtype=float)
        if amplitude.shape != frequency.shape or phase.shape != frequency.shape:
            raise ValueError("amplitude_pa and phase_rad must align with frequency_hz")
        if np.any(~np.isfinite(amplitude)) or np.any(amplitude < 0):
            raise ValueError("amplitude_pa must be finite and non-negative")
        if np.any(~np.isfinite(phase)):
            raise ValueError("phase_rad must be finite")
        return cls(
            frequency_hz=frequency,
            pressure_pa=amplitude * np.exp(1j * phase),
            source_identity=source_identity,
            citations=citations,
        )

    @property
    def amplitude_pa(self) -> np.ndarray:
        values = np.abs(self.pressure_pa)
        values.setflags(write=False)
        return values

    @property
    def phase_rad(self) -> np.ndarray:
        values = np.angle(self.pressure_pa)
        values.setflags(write=False)
        return values


@dataclass(frozen=True, slots=True, eq=False)
class ArterialModeSpectrum:
    """Frequency-dependent local coupled blood-wall mode properties."""

    frequency_hz: np.ndarray
    wavenumber_per_m: np.ndarray
    characteristic_impedance_pa_s_per_m3: np.ndarray
    specific_impedance_pa_s_per_m: np.ndarray
    area_compliance_m2_per_pa: np.ndarray
    womersley_factor: np.ndarray
    series_impedance_pa_s_per_m4: np.ndarray

    def __post_init__(self) -> None:
        frequency = _readonly_real(self.frequency_hz, "frequency_hz")
        arrays = {
            "wavenumber_per_m": _readonly_complex(self.wavenumber_per_m, "wavenumber_per_m"),
            "characteristic_impedance_pa_s_per_m3": _readonly_complex(
                self.characteristic_impedance_pa_s_per_m3,
                "characteristic_impedance_pa_s_per_m3",
            ),
            "specific_impedance_pa_s_per_m": _readonly_complex(
                self.specific_impedance_pa_s_per_m,
                "specific_impedance_pa_s_per_m",
            ),
            "area_compliance_m2_per_pa": _readonly_complex(
                self.area_compliance_m2_per_pa,
                "area_compliance_m2_per_pa",
            ),
            "womersley_factor": _readonly_complex(self.womersley_factor, "womersley_factor"),
            "series_impedance_pa_s_per_m4": _readonly_complex(
                self.series_impedance_pa_s_per_m4,
                "series_impedance_pa_s_per_m4",
            ),
        }
        if any(value.shape != frequency.shape for value in arrays.values()):
            raise ValueError("all arterial mode arrays must align with frequency_hz")
        object.__setattr__(self, "frequency_hz", frequency)
        for name, value in arrays.items():
            object.__setattr__(self, name, value)

    @property
    def phase_speed_m_per_s(self) -> np.ndarray:
        real_k = np.real(self.wavenumber_per_m)
        out = np.divide(
            2.0 * math.pi * self.frequency_hz,
            real_k,
            out=np.full_like(real_k, np.nan, dtype=float),
            where=np.abs(real_k) > 0,
        )
        out.setflags(write=False)
        return out

    @property
    def attenuation_neper_per_m(self) -> np.ndarray:
        out = np.maximum(0.0, -np.imag(self.wavenumber_per_m))
        out.setflags(write=False)
        return out


@dataclass(frozen=True, slots=True, eq=False)
class EndothelialLoadSpectrum:
    """Mechanical spectrum delivered to the endothelial interface."""

    frequency_hz: np.ndarray
    pressure_pa: np.ndarray
    tangential_traction_pa: np.ndarray
    wall_displacement_m: np.ndarray
    volume_flow_m3_per_s: np.ndarray

    def __post_init__(self) -> None:
        frequency = _readonly_real(self.frequency_hz, "frequency_hz")
        arrays = {
            "pressure_pa": _readonly_complex(self.pressure_pa, "pressure_pa"),
            "tangential_traction_pa": _readonly_complex(
                self.tangential_traction_pa, "tangential_traction_pa"
            ),
            "wall_displacement_m": _readonly_complex(
                self.wall_displacement_m, "wall_displacement_m"
            ),
            "volume_flow_m3_per_s": _readonly_complex(
                self.volume_flow_m3_per_s, "volume_flow_m3_per_s"
            ),
        }
        if any(value.shape != frequency.shape for value in arrays.values()):
            raise ValueError("all endothelial load arrays must align with frequency_hz")
        object.__setattr__(self, "frequency_hz", frequency)
        for name, value in arrays.items():
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, eq=False)
class CellCardioacousticSolution:
    segment_id: str
    cell_index: int
    axial_position_m: float
    node_in: int
    node_out: int
    load: EndothelialLoadSpectrum

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id.strip():
            raise ValueError("segment_id must be non-empty")
        if isinstance(self.cell_index, bool) or not isinstance(self.cell_index, int) or self.cell_index < 0:
            raise ValueError("cell_index must be a non-negative integer")
        if not math.isfinite(float(self.axial_position_m)) or float(self.axial_position_m) < 0:
            raise ValueError("axial_position_m must be finite and non-negative")
        if not isinstance(self.node_in, int) or not isinstance(self.node_out, int):
            raise TypeError("cell node identifiers must be integers")
        if not isinstance(self.load, EndothelialLoadSpectrum):
            raise TypeError("load must be an EndothelialLoadSpectrum")


@dataclass(frozen=True, slots=True, eq=False)
class CardioacousticNetworkSolution:
    """Frequency-domain solution of one VascuQuest arterial network."""

    frequency_hz: np.ndarray
    node_ids: tuple[int, ...]
    node_pressure_pa: np.ndarray
    cells: tuple[CellCardioacousticSolution, ...]
    source_identity: str
    source_citations: tuple[str, ...]
    backend_id: str
    terminal_model: str

    def __post_init__(self) -> None:
        frequency = _readonly_real(self.frequency_hz, "frequency_hz")
        pressure = _readonly_complex(self.node_pressure_pa, "node_pressure_pa", ndim=2)
        if pressure.shape != (frequency.size, len(self.node_ids)):
            raise ValueError("node_pressure_pa shape must be (frequency, node)")
        if len(self.node_ids) != len(set(self.node_ids)):
            raise ValueError("node_ids must be unique")
        if not isinstance(self.cells, tuple) or any(
            not isinstance(item, CellCardioacousticSolution) for item in self.cells
        ):
            raise TypeError("cells must contain CellCardioacousticSolution values")
        if not isinstance(self.source_citations, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.source_citations
        ):
            raise ValueError("source_citations must be a tuple of non-empty strings")
        for value, name in (
            (self.source_identity, "source_identity"),
            (self.backend_id, "backend_id"),
            (self.terminal_model, "terminal_model"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        object.__setattr__(self, "frequency_hz", frequency)
        object.__setattr__(self, "node_pressure_pa", pressure)


__all__ = [
    "ArterialModeSpectrum",
    "CardioacousticNetworkSolution",
    "CardioacousticSourceSpectrum",
    "CellCardioacousticSolution",
    "EndothelialLoadSpectrum",
]
