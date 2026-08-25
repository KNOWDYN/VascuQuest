"""Built-in deterministic reconstructions backed by authoritative PWDB identities.

The only reconstruction implemented in Batch 11 is volumetric flow rate from
aligned PWDB flow-velocity and luminal-area waveforms. The authoritative PWDB
exporter explicitly omits Q from exported common-site signals because it is
``U.*A`` and labels Q as flow rate in m3/s.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import numpy as np

from vascuquest._version import __version__
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import ValidityState, ValueState, Waveform
from vascuquest.errors import AdmissibilityError
from vascuquest.plugins.descriptor import (
    ComponentDescriptor,
    ComponentKind,
    SUPPORTED_PROTOCOL_VERSION,
)
from vascuquest.ports.methods import ExecutionContext, InputRequirement, ParameterSpec


FLOW_RATE_RECONSTRUCTION_ID = "vascuquest:flow-rate-reconstruction"
PWDB_ARTICLE_CITATION = "doi:10.1152/ajpheart.00218.2019"
PWDB_EXPORTER_CITATION = (
    "github:peterhcharlton/pwdb@5a0d472706b5f87fa1962fa5d1b8412f4e432315:"
    "pwdb_v0.1/export_pwdb.m"
)

_FLOW_RATE_QUANTITY = QuantityDefinition(
    canonical_name="flow_rate",
    label="Volumetric flow rate",
    description=(
        "Arterial volumetric flow-rate waveform reconstructed deterministically "
        "as flow velocity multiplied by luminal cross-sectional area."
    ),
    value_kind="numeric",
    schema_version="1",
    physical_dimension="volume_flow_rate",
    canonical_unit="m^3/s",
    allowed_source_units=(),
    applicable_contexts=("measurement_site",),
    source_aliases=(),
    default_evidence=EvidenceClass.RECONSTRUCTED,
    known_source_issues=(),
    citations=(PWDB_ARTICLE_CITATION, PWDB_EXPORTER_CITATION),
)

_REQUIRED_INPUTS = (
    InputRequirement(
        name="flow_velocity",
        quantity="flow_velocity",
        category="waveform_signal",
        accepted_units=("m/s",),
        physical_dimension="velocity",
        required_coordinates=("time",),
        location_kind="measurement_site",
        accepted_evidence=(EvidenceClass.SOURCE,),
    ),
    InputRequirement(
        name="luminal_area",
        quantity="luminal_area",
        category="waveform_signal",
        accepted_units=("m^2",),
        physical_dimension="area",
        required_coordinates=("time",),
        location_kind="measurement_site",
        accepted_evidence=(EvidenceClass.SOURCE,),
    ),
)

_BAD_INPUT_VALIDITY = frozenset(
    {
        ValidityState.OUT_OF_DECLARED_DOMAIN,
        ValidityState.INVALID,
        ValidityState.INVALID_INPUT,
        ValidityState.NUMERICAL_FAILURE,
    }
)


def _readonly_array(values: object, *, dtype: object) -> np.ndarray:
    array = np.asarray(values, dtype=dtype).copy()
    array.setflags(write=False)
    return array


def _validated_mask(mask: object | None, shape: tuple[int, ...], name: str) -> np.ndarray:
    if mask is None:
        result = np.zeros(shape, dtype=bool)
    else:
        result = np.asarray(mask, dtype=bool)
        if result.shape != shape:
            raise AdmissibilityError(f"{name} shape does not match waveform values")
        result = result.copy()
    result.setflags(write=False)
    return result


def _combined_validity(first: Waveform, second: Waveform) -> ValidityState:
    states = (first.validity, second.validity)
    if any(state in _BAD_INPUT_VALIDITY for state in states):
        return ValidityState.INVALID_INPUT
    if any(state is ValidityState.VALID_WITH_WARNING for state in states):
        return ValidityState.VALID_WITH_WARNING
    if all(state is ValidityState.VALID for state in states):
        return ValidityState.VALID
    return ValidityState.NOT_EVALUATED


def _provenance_ref(velocity: Waveform, area: Waveform) -> str:
    payload = {
        "method_id": FLOW_RATE_RECONSTRUCTION_ID,
        "implementation_version": "1.0.0",
        "definition": "Q=U*A",
        "inputs": {
            "flow_velocity": velocity.provenance_ref,
            "luminal_area": area.provenance_ref,
        },
        "output_quantity": "flow_rate",
        "output_unit": "m^3/s",
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_waveform_input(
    value: object,
    *,
    name: str,
    quantity: str,
    unit: str,
    dimension: str,
) -> Waveform:
    if not isinstance(value, Waveform):
        raise AdmissibilityError(f"input {name!r} must be a Waveform")
    if value.quantity.canonical_name != quantity:
        raise AdmissibilityError(
            f"input {name!r} requires quantity {quantity!r}, received "
            f"{value.quantity.canonical_name!r}"
        )
    if value.quantity.canonical_unit != unit:
        raise AdmissibilityError(f"input {name!r} must use canonical unit {unit!r}")
    if value.quantity.physical_dimension != dimension:
        raise AdmissibilityError(f"input {name!r} has incompatible physical dimension")
    if value.evidence is not EvidenceClass.SOURCE:
        raise AdmissibilityError(f"input {name!r} must retain SOURCE evidence")
    if value.value_state is not ValueState.PRESENT:
        raise AdmissibilityError(f"input {name!r} is not present")
    if not isinstance(value.location, MeasurementSite):
        raise AdmissibilityError(
            "Batch 11 flow-rate reconstruction is validated for measurement sites only"
        )
    if value.dimensions != ("time",):
        raise AdmissibilityError(f"input {name!r} must be a one-dimensional time waveform")
    return value


class FlowRateReconstruction:
    """Reconstruct common-site volumetric flow rate using the PWDB identity Q=U*A."""

    @property
    def descriptor(self) -> ComponentDescriptor:
        return ComponentDescriptor(
            kind=ComponentKind.DERIVATION,
            name="PWDB flow-rate reconstruction",
            qualified_id=FLOW_RATE_RECONSTRUCTION_ID,
            implementation_version="1.0.0",
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="vascuquest",
            distribution_version=__version__,
            summary=(
                "Reconstruct aligned common-site volumetric flow rate from SOURCE "
                "flow velocity and luminal area using the PWDB identity Q=U*A."
            ),
            citations=(PWDB_ARTICLE_CITATION, PWDB_EXPORTER_CITATION),
        )

    @property
    def required_inputs(self) -> tuple[InputRequirement, ...]:
        return _REQUIRED_INPUTS

    @property
    def output_quantity(self) -> QuantityDefinition:
        return _FLOW_RATE_QUANTITY

    @property
    def output_evidence(self) -> EvidenceClass:
        return EvidenceClass.RECONSTRUCTED

    @property
    def parameter_specs(self) -> tuple[ParameterSpec, ...]:
        return ()

    @property
    def missing_data_policy(self) -> str:
        return (
            "Require aligned source waveforms; propagate NaN arithmetic and the union "
            "of input missing/padding masks without interpolation or imputation."
        )

    @property
    def citations(self) -> tuple[str, ...]:
        return (PWDB_ARTICLE_CITATION, PWDB_EXPORTER_CITATION)

    @property
    def validation_scope(self) -> str:
        return (
            "Authoritative PWDB identity Q=U*A for exactly aligned measurement-site "
            "SOURCE waveforms in m/s and m^2. Path-resolved use, interpolation, "
            "resampling, and unit conversion are outside the Batch 11 validated scope."
        )

    @property
    def deterministic(self) -> bool:
        return True

    def run(
        self,
        *,
        inputs: Mapping[str, object],
        parameters: Mapping[str, object],
        context: ExecutionContext,
    ) -> Waveform:
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be an ExecutionContext")
        if parameters:
            raise AdmissibilityError("flow-rate reconstruction declares no parameters")
        if set(inputs) != {"flow_velocity", "luminal_area"}:
            raise AdmissibilityError(
                "flow-rate reconstruction requires exactly flow_velocity and luminal_area"
            )

        velocity = _require_waveform_input(
            inputs["flow_velocity"],
            name="flow_velocity",
            quantity="flow_velocity",
            unit="m/s",
            dimension="velocity",
        )
        area = _require_waveform_input(
            inputs["luminal_area"],
            name="luminal_area",
            quantity="luminal_area",
            unit="m^2",
            dimension="area",
        )

        if velocity.dataset_identity != area.dataset_identity:
            raise AdmissibilityError("input waveforms belong to different dataset identities")
        if velocity.subject != area.subject:
            raise AdmissibilityError("input waveforms belong to different virtual subjects")
        if velocity.location != area.location:
            raise AdmissibilityError("input waveforms refer to different measurement sites")

        velocity_values = np.asarray(velocity.values, dtype=float)
        area_values = np.asarray(area.values, dtype=float)
        if velocity_values.ndim != 1 or area_values.ndim != 1:
            raise AdmissibilityError("flow-rate reconstruction requires one-dimensional waveforms")
        if velocity_values.shape != area_values.shape:
            raise AdmissibilityError("input waveform sample shapes do not match")

        velocity_time = np.asarray(velocity.time_coordinate.values, dtype=float)
        area_time = np.asarray(area.time_coordinate.values, dtype=float)
        if velocity_time.shape != velocity_values.shape or area_time.shape != area_values.shape:
            raise AdmissibilityError("time-coordinate shape does not match waveform samples")
        if not np.array_equal(velocity_time, area_time, equal_nan=True):
            raise AdmissibilityError(
                "input time coordinates are not exactly aligned; interpolation is not implicit"
            )
        if velocity.time_coordinate.unit != area.time_coordinate.unit:
            raise AdmissibilityError("input time-coordinate units do not match")

        values = _readonly_array(velocity_values * area_values, dtype=float)
        missing_mask = _readonly_array(
            _validated_mask(velocity.missing_mask, values.shape, "flow-velocity missing mask")
            | _validated_mask(area.missing_mask, values.shape, "luminal-area missing mask"),
            dtype=bool,
        )
        padding_mask = _readonly_array(
            _validated_mask(velocity.padding_mask, values.shape, "flow-velocity padding mask")
            | _validated_mask(area.padding_mask, values.shape, "luminal-area padding mask"),
            dtype=bool,
        )
        warnings = tuple(dict.fromkeys((*velocity.warnings, *area.warnings)))

        return Waveform(
            dataset_identity=velocity.dataset_identity,
            quantity=self.output_quantity,
            values=values,
            provenance_ref=_provenance_ref(velocity, area),
            dimensions=("time",),
            coordinates=velocity.coordinates,
            subject=velocity.subject,
            location=velocity.location,
            evidence=EvidenceClass.RECONSTRUCTED,
            value_state=ValueState.PRESENT,
            validity=_combined_validity(velocity, area),
            warnings=warnings,
            method_id=FLOW_RATE_RECONSTRUCTION_ID,
            missing_mask=missing_mask,
            padding_mask=padding_mask,
        )


def create_flow_rate_reconstruction() -> FlowRateReconstruction:
    """Zero-argument factory used by the built-in plugin registry."""

    return FlowRateReconstruction()


__all__ = [
    "FLOW_RATE_RECONSTRUCTION_ID",
    "FlowRateReconstruction",
    "create_flow_rate_reconstruction",
]
