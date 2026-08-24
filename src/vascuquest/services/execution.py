"""Application dispatch for registered scientific components.

No scientific equation is implemented here. The service resolves components,
normalizes declared inputs/parameters, validates canonical compatibility, and
then delegates to the registered component implementation.
"""

from __future__ import annotations

from collections.abc import Mapping

from vascuquest._version import __version__
from vascuquest.domain.cohort import Cohort
from vascuquest.domain.location import VascularLocation
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import AdmissibilityError, CapabilityError
from vascuquest.plugins.descriptor import ComponentKind
from vascuquest.plugins.registry import PluginRegistry
from vascuquest.ports.methods import (
    Derivation,
    DiscoveryMethod,
    ExecutionContext,
    InputRequirement,
    ParameterSpec,
    ResearchOperator,
)

from .retrieval import QuantitySubjects, RetrievalService


class ExecutionService:
    """Resolve and execute only registered, protocol-valid scientific components."""

    __slots__ = ("_registry", "_retrieval")

    def __init__(self, registry: PluginRegistry, retrieval: RetrievalService) -> None:
        if not isinstance(registry, PluginRegistry):
            raise TypeError("registry must be a PluginRegistry")
        if not isinstance(retrieval, RetrievalService):
            raise TypeError("retrieval must be a RetrievalService")
        self._registry = registry
        self._retrieval = retrieval

    def derive(
        self,
        method: str,
        *,
        inputs: Mapping[str, ScientificResult] | None = None,
        subjects: QuantitySubjects = None,
        location: VascularLocation | None = None,
        parameters: Mapping[str, object] | None = None,
    ) -> ScientificResult:
        component = self._registry.get(method, kind=ComponentKind.DERIVATION)
        if not isinstance(component, Derivation):
            raise CapabilityError(f"registered component {method!r} is not a derivation")
        resolved_inputs = self._resolve_inputs(
            component.required_inputs,
            inputs=inputs,
            subjects=subjects,
            location=location,
        )
        normalized = _normalize_parameters(component.parameter_specs, parameters)
        result = component.run(
            inputs=resolved_inputs,
            parameters=normalized,
            context=ExecutionContext(runtime_version=__version__),
        )
        return self._validate_output(result, expected_evidence=component.output_evidence)

    def model(
        self,
        operator: str,
        *,
        inputs: Mapping[str, ScientificResult] | None = None,
        subjects: QuantitySubjects = None,
        location: VascularLocation | None = None,
        parameters: Mapping[str, object] | None = None,
    ) -> ScientificResult:
        component = self._registry.get(operator, kind=ComponentKind.OPERATOR)
        if not isinstance(component, ResearchOperator):
            raise CapabilityError(f"registered component {operator!r} is not a research operator")
        resolved_inputs = self._resolve_inputs(
            component.required_inputs,
            inputs=inputs,
            subjects=subjects,
            location=location,
        )
        normalized = _normalize_parameters(component.parameter_specs, parameters)
        result = component.run(
            inputs=resolved_inputs,
            parameters=normalized,
            context=ExecutionContext(runtime_version=__version__),
        )
        return self._validate_output(result, expected_evidence=component.output_evidence)

    def discover(
        self,
        method: str,
        *,
        cohort: Cohort,
        inputs: Mapping[str, ScientificResult] | None = None,
        parameters: Mapping[str, object] | None = None,
    ) -> ScientificResult:
        if not isinstance(cohort, Cohort):
            raise TypeError("cohort must be a Cohort")
        component = self._registry.get(method, kind=ComponentKind.DISCOVERY)
        if not isinstance(component, DiscoveryMethod):
            raise CapabilityError(f"registered component {method!r} is not a discovery method")
        resolved_inputs = self._resolve_inputs(
            component.required_inputs,
            inputs=inputs,
            subjects=cohort,
            location=None,
        )
        normalized = _normalize_parameters(component.parameter_specs, parameters)
        result = component.run(
            cohort=cohort,
            inputs=resolved_inputs,
            parameters=normalized,
            context=ExecutionContext(runtime_version=__version__),
        )
        return self._validate_output(result, expected_evidence=None)

    def _resolve_inputs(
        self,
        requirements: tuple[InputRequirement, ...],
        *,
        inputs: Mapping[str, ScientificResult] | None,
        subjects: QuantitySubjects,
        location: VascularLocation | None,
    ) -> dict[str, ScientificResult]:
        supplied = {} if inputs is None else dict(inputs)
        unknown = set(supplied) - {requirement.name for requirement in requirements}
        if unknown:
            raise AdmissibilityError(f"undeclared scientific inputs supplied: {sorted(unknown)!r}")

        resolved: dict[str, ScientificResult] = {}
        for requirement in requirements:
            result = supplied.get(requirement.name)
            if result is None:
                if requirement.quantity is None:
                    raise CapabilityError(
                        f"input {requirement.name!r} must be supplied explicitly because "
                        "its requirement is category-based"
                    )
                result = self._retrieval.get(
                    requirement.quantity,
                    subjects=subjects,
                    location=location,
                )
            _validate_requirement(requirement, result)
            resolved[requirement.name] = result
        return resolved

    @staticmethod
    def _validate_output(
        result: object,
        *,
        expected_evidence: object | None,
    ) -> ScientificResult:
        if not isinstance(result, ScientificResult):
            raise AdmissibilityError("scientific component did not return a ScientificResult")
        if expected_evidence is not None and result.evidence is not expected_evidence:
            raise AdmissibilityError(
                "scientific component output evidence does not match its declared evidence class"
            )
        return result


def _normalize_parameters(
    specs: tuple[ParameterSpec, ...],
    provided: Mapping[str, object] | None,
) -> dict[str, object]:
    values = {} if provided is None else dict(provided)
    if any(not isinstance(key, str) or not key or key != key.strip() for key in values):
        raise AdmissibilityError("parameter names must be non-empty trimmed strings")
    spec_by_name = {spec.name: spec for spec in specs}
    unknown = set(values) - set(spec_by_name)
    if unknown:
        raise AdmissibilityError(f"unknown parameters: {sorted(unknown)!r}")

    normalized: dict[str, object] = {}
    for spec in specs:
        if spec.name in values:
            value = values[spec.name]
        elif spec.required:
            raise AdmissibilityError(f"required parameter {spec.name!r} is missing")
        else:
            value = spec.default
        if spec.allowed_values and value not in spec.allowed_values:
            raise AdmissibilityError(
                f"parameter {spec.name!r} is outside its declared allowed values"
            )
        normalized[spec.name] = value
    return normalized


def _validate_requirement(
    requirement: InputRequirement,
    result: ScientificResult,
) -> None:
    if not isinstance(result, ScientificResult):
        raise AdmissibilityError(f"input {requirement.name!r} is not a ScientificResult")
    if (
        requirement.quantity is not None
        and result.quantity.canonical_name != requirement.quantity
    ):
        raise AdmissibilityError(
            f"input {requirement.name!r} requires quantity {requirement.quantity!r}, "
            f"received {result.quantity.canonical_name!r}"
        )
    if (
        requirement.physical_dimension is not None
        and result.quantity.physical_dimension != requirement.physical_dimension
    ):
        raise AdmissibilityError(
            f"input {requirement.name!r} has incompatible physical dimension"
        )
    if (
        requirement.accepted_units
        and result.quantity.canonical_unit not in requirement.accepted_units
    ):
        raise AdmissibilityError(f"input {requirement.name!r} has incompatible canonical unit")
    if requirement.cohort_required and result.cohort is None:
        raise AdmissibilityError(f"input {requirement.name!r} requires cohort context")
    if requirement.accepted_evidence and result.evidence not in requirement.accepted_evidence:
        raise AdmissibilityError(f"input {requirement.name!r} has incompatible evidence class")
    missing_coordinates = set(requirement.required_coordinates) - set(result.dimensions)
    if missing_coordinates:
        raise AdmissibilityError(
            f"input {requirement.name!r} lacks required coordinates {sorted(missing_coordinates)!r}"
        )


__all__ = ["ExecutionService"]
