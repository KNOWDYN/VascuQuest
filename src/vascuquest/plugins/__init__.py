"""VascuQuest component descriptors and installed-plugin registry."""

from .descriptor import ComponentDescriptor, ComponentKind, SUPPORTED_PROTOCOL_VERSION
from .registry import ComponentFactory, PluginLoadFailure, PluginRegistry

__all__ = [
    "ComponentDescriptor",
    "ComponentFactory",
    "ComponentKind",
    "PluginLoadFailure",
    "PluginRegistry",
    "SUPPORTED_PROTOCOL_VERSION",
]
