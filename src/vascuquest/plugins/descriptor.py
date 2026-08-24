"""Immutable metadata identifying VascuQuest extension components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


SUPPORTED_PROTOCOL_VERSION = 1
_COMPONENT_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$"
)


class ComponentKind(str, Enum):
    """The exactly five public VascuQuest v1 plugin categories."""

    BACKEND = "backend"
    DERIVATION = "derivation"
    OPERATOR = "operator"
    DISCOVERY = "discovery"
    EXPORTER = "exporter"

    @property
    def entry_point_group(self) -> str:
        """Return the canonical Python packaging entry-point group."""

        return {
            ComponentKind.BACKEND: "vascuquest.backends",
            ComponentKind.DERIVATION: "vascuquest.derivations",
            ComponentKind.OPERATOR: "vascuquest.operators",
            ComponentKind.DISCOVERY: "vascuquest.discovery",
            ComponentKind.EXPORTER: "vascuquest.exporters",
        }[self]


@dataclass(frozen=True, slots=True)
class ComponentDescriptor:
    """Stable identity and implementation metadata for one component."""

    kind: ComponentKind
    name: str
    qualified_id: str
    implementation_version: str
    protocol_version: int
    distribution_name: str
    distribution_version: str
    summary: str
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ComponentKind):
            raise TypeError("kind must be a ComponentKind")
        for field_name in (
            "name",
            "qualified_id",
            "implementation_version",
            "distribution_name",
            "distribution_version",
            "summary",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string")
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            if value != value.strip():
                raise ValueError(
                    f"{field_name} must not contain leading or trailing whitespace"
                )
        if not _COMPONENT_ID_RE.fullmatch(self.qualified_id):
            raise ValueError(
                "qualified_id must use '<namespace>:<component>' machine-identifier syntax"
            )
        if isinstance(self.protocol_version, bool) or not isinstance(
            self.protocol_version, int
        ):
            raise TypeError("protocol_version must be an integer major version")
        if self.protocol_version < 1:
            raise ValueError("protocol_version must be a positive integer")
        if not isinstance(self.citations, tuple):
            raise TypeError("citations must be a tuple of strings")
        seen: set[str] = set()
        for citation in self.citations:
            if not isinstance(citation, str):
                raise TypeError("citations must contain only strings")
            if not citation or citation != citation.strip():
                raise ValueError("citations must contain non-empty trimmed strings")
            if citation in seen:
                raise ValueError("citations must not contain duplicate values")
            seen.add(citation)


__all__ = [
    "ComponentDescriptor",
    "ComponentKind",
    "SUPPORTED_PROTOCOL_VERSION",
]
