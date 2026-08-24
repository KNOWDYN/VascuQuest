"""Structural port for scientific result exporters.

Exporters serialize results without performing scientific calculations or
changing their meaning. The protocol deliberately leaves concrete destinations
and file formats to exporter implementations.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from vascuquest.domain.result import ScientificResult


@runtime_checkable
class ResultExporter(Protocol):
    """Serialize a structured scientific result without changing its semantics."""

    @property
    def descriptor(self) -> object:
        """Component metadata validated by the plugin registry."""

        ...

    @property
    def supported_result_kinds(self) -> tuple[str, ...]:
        """Canonical result kinds accepted by this exporter."""

        ...

    @property
    def supported_output_formats(self) -> tuple[str, ...]:
        """Output formats implemented by this exporter."""

        ...

    @property
    def provenance_retention(self) -> str:
        """Describe how required provenance/metadata are retained."""

        ...

    def export(
        self,
        result: ScientificResult,
        destination: object,
        options: Mapping[str, object],
    ) -> object:
        """Export one result and return implementation-defined destination metadata."""

        ...


__all__ = ["ResultExporter"]
