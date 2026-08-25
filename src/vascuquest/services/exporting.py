"""Application service for registered result exporters."""

from __future__ import annotations

from collections.abc import Mapping

from vascuquest.domain.result import ScientificResult
from vascuquest.errors import CapabilityError
from vascuquest.plugins.descriptor import ComponentKind
from vascuquest.plugins.registry import PluginRegistry
from vascuquest.ports.exporter import ResultExporter


class ExportingService:
    """Resolve an exporter and serialize a result without recomputing science."""

    __slots__ = ("_registry",)

    def __init__(self, registry: PluginRegistry) -> None:
        if not isinstance(registry, PluginRegistry):
            raise TypeError("registry must be a PluginRegistry")
        self._registry = registry

    def export(
        self,
        result: ScientificResult,
        exporter: str,
        destination: object,
        *,
        options: Mapping[str, object] | None = None,
    ) -> object:
        if not isinstance(result, ScientificResult):
            raise TypeError("result must be a ScientificResult")
        component = self._registry.get(exporter, kind=ComponentKind.EXPORTER)
        if not isinstance(component, ResultExporter):
            raise CapabilityError(f"registered component {exporter!r} is not an exporter")
        normalized = {} if options is None else dict(options)
        if any(not isinstance(key, str) or not key or key != key.strip() for key in normalized):
            raise ValueError("export option names must be non-empty trimmed strings")
        return component.export(result, destination, normalized)


__all__ = ["ExportingService"]
