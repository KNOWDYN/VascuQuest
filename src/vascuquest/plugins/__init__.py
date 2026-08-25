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


__all__ = [
    "ComponentDescriptor",
    "ComponentFactory",
    "ComponentKind",
    "PluginLoadFailure",
    "PluginRegistry",
    "SUPPORTED_PROTOCOL_VERSION",
    "describe",
    "list",
]
