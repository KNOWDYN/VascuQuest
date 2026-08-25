"""VascuQuest component descriptors and lazy public plugin catalog."""

from __future__ import annotations

from functools import lru_cache

from .descriptor import ComponentDescriptor, ComponentKind, SUPPORTED_PROTOCOL_VERSION
from .registry import ComponentFactory, PluginLoadFailure, PluginRegistry


@lru_cache(maxsize=1)
def _public_registry() -> PluginRegistry:
    """Build the inspection registry only when plugin inspection is requested."""

    from vascuquest.backends.pwdb3275625 import PWDB3275625Backend
    from vascuquest.errors import DatasetUnavailableError
    from vascuquest.exporters import BUILTIN_EXPORTER_FACTORIES
    from vascuquest.methods import BUILTIN_DERIVATION_FACTORIES

    def unavailable_artifact(artifact_id: str):
        raise DatasetUnavailableError(
            f"plugin inspection does not acquire artifact {artifact_id!r}; open a dataset session"
        )

    registry = PluginRegistry()
    registry.register_factory(
        lambda: PWDB3275625Backend(unavailable_artifact),
        expected_kind=ComponentKind.BACKEND,
        built_in=True,
    )
    for factory in BUILTIN_DERIVATION_FACTORIES:
        registry.register_factory(
            factory,
            expected_kind=ComponentKind.DERIVATION,
            built_in=True,
        )
    for factory in BUILTIN_EXPORTER_FACTORIES:
        registry.register_factory(
            factory,
            expected_kind=ComponentKind.EXPORTER,
            built_in=True,
        )
    registry.discover_installed()
    return registry


def list(kind: ComponentKind | None = None) -> tuple[ComponentDescriptor, ...]:
    """List active built-in/installed plugin descriptors without data acquisition."""

    return _public_registry().list(kind)


def describe(
    qualified_id: str,
    *,
    kind: ComponentKind | None = None,
) -> ComponentDescriptor:
    """Describe one active component without executing scientific work."""

    return _public_registry().describe(qualified_id, kind=kind)


def details(
    qualified_id: str,
    *,
    kind: ComponentKind | None = None,
) -> dict[str, object]:
    """Return declarative component details without executing science or acquiring data.

    The public descriptor remains the stable identity surface. This additive
    inspection view exposes protocol-declared inputs, outputs, parameters,
    assumptions/policies, citations, and validation scope where a component
    category defines them. It returns already-constructed declaration objects;
    it never invokes a component's ``run`` method or a backend source reader.
    """

    registry = _public_registry()
    descriptor = registry.describe(qualified_id, kind=kind)
    component = registry.get(qualified_id, kind=kind)
    payload: dict[str, object] = {
        "kind": descriptor.kind.value,
        "qualified_id": descriptor.qualified_id,
        "name": descriptor.name,
        "implementation_version": descriptor.implementation_version,
        "protocol_version": descriptor.protocol_version,
        "distribution_name": descriptor.distribution_name,
        "distribution_version": descriptor.distribution_version,
        "summary": descriptor.summary,
        "citations": descriptor.citations,
    }

    declarative_attributes = (
        "required_inputs",
        "output_quantity",
        "output_quantities",
        "output_schema",
        "output_evidence",
        "evidence_semantics",
        "parameter_specs",
        "assumptions",
        "missing_data_policy",
        "admissible_domain",
        "validation_scope",
        "deterministic",
        "supported_result_kinds",
        "supported_output_formats",
        "provenance_retention",
    )
    for attribute in declarative_attributes:
        if hasattr(component, attribute):
            payload[attribute] = getattr(component, attribute)

    component_citations = getattr(component, "citations", None)
    if component_citations is not None:
        payload["citations"] = component_citations

    if descriptor.kind is ComponentKind.BACKEND:
        payload["dataset_identity"] = component.identity()
        payload["capabilities"] = tuple(sorted(component.capabilities()))

    return payload


__all__ = [
    "ComponentDescriptor",
    "ComponentFactory",
    "ComponentKind",
    "PluginLoadFailure",
    "PluginRegistry",
    "SUPPORTED_PROTOCOL_VERSION",
    "describe",
    "details",
    "list",
]
