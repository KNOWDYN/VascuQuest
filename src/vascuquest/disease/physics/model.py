"""Immutable causal disease-physics state for Virtual Disease PR 3."""

from __future__ import annotations

from dataclasses import dataclass
import math

from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.disease.model import DiseaseSpecification
from vascuquest.disease.solver.losses import LocalizedPressureLoss
from vascuquest.disease.solver.network import NetworkDiscretization


@dataclass(frozen=True, slots=True)
class DiseasePhysicsModel:
    """A transformed solver input state, not a runtime disease dataset.

    The healthy parent state is retained by reference and remains immutable.
    Disease causality is carried only by the transformed network and explicit
    pressure-loss terms.
    """

    baseline: BaselineCardiovascularState
    specification: DiseaseSpecification
    network: NetworkDiscretization
    pressure_losses: tuple[LocalizedPressureLoss, ...]
    modified_segment_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    citations: tuple[str, ...]
    baseline_cfpwv_m_per_s: float | None = None
    target_cfpwv_m_per_s: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, BaselineCardiovascularState):
            raise TypeError("baseline must be a BaselineCardiovascularState")
        if not isinstance(self.specification, DiseaseSpecification):
            raise TypeError("specification must be a DiseaseSpecification")
        if not isinstance(self.network, NetworkDiscretization):
            raise TypeError("network must be a NetworkDiscretization")
        if not isinstance(self.pressure_losses, tuple) or any(
            not isinstance(item, LocalizedPressureLoss) for item in self.pressure_losses
        ):
            raise TypeError("pressure_losses must be a tuple of LocalizedPressureLoss values")
        if not isinstance(self.modified_segment_ids, tuple):
            raise TypeError("modified_segment_ids must be a tuple")
        if len(self.modified_segment_ids) != len(set(self.modified_segment_ids)):
            raise ValueError("modified_segment_ids must be unique")
        baseline_ids = tuple(segment.segment_id for segment in self.baseline.segments)
        network_ids = tuple(mesh.segment_id for mesh in self.network.meshes)
        if network_ids != baseline_ids:
            raise ValueError("disease network must preserve parent segment identity and order")
        if any(segment_id not in baseline_ids for segment_id in self.modified_segment_ids):
            raise ValueError("modified_segment_ids must belong to the parent network")
        for collection, name in (
            (self.assumptions, "assumptions"),
            (self.citations, "citations"),
        ):
            if not isinstance(collection, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in collection
            ):
                raise ValueError(f"{name} must be a tuple of non-empty strings")
        for value, name in (
            (self.baseline_cfpwv_m_per_s, "baseline_cfpwv_m_per_s"),
            (self.target_cfpwv_m_per_s, "target_cfpwv_m_per_s"),
        ):
            if value is not None and (
                not math.isfinite(float(value)) or float(value) <= 0
            ):
                raise ValueError(f"{name} must be None or positive and finite")
        if (self.baseline_cfpwv_m_per_s is None) != (self.target_cfpwv_m_per_s is None):
            raise ValueError("cfPWV metadata must be supplied as a complete baseline/target pair")


__all__ = ["DiseasePhysicsModel"]
