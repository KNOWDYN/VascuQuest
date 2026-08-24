"""Deterministic registry for built-in and installed VascuQuest components."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata as importlib_metadata
import inspect
from typing import Callable, Iterable

from vascuquest.errors import PluginCompatibilityError, PluginError
from vascuquest.ports import (
    DatasetBackend,
    Derivation,
    DiscoveryMethod,
    ResearchOperator,
    ResultExporter,
)

from .descriptor import ComponentDescriptor, ComponentKind, SUPPORTED_PROTOCOL_VERSION


ComponentFactory = Callable[[], object]


class _DuplicateComponentError(PluginError):
    """Internal marker for a registry conflict that must not be isolated."""


@dataclass(frozen=True, slots=True)
class PluginLoadFailure:
    """One isolated installed-plugin discovery/load failure."""

    entry_point_group: str
    entry_point_name: str
    distribution_name: str | None
    distribution_version: str | None
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class _RegisteredComponent:
    descriptor: ComponentDescriptor
    factory: ComponentFactory
    component: object
    built_in: bool


_PROTOCOLS: dict[ComponentKind, type[object]] = {
    ComponentKind.BACKEND: DatasetBackend,
    ComponentKind.DERIVATION: Derivation,
    ComponentKind.OPERATOR: ResearchOperator,
    ComponentKind.DISCOVERY: DiscoveryMethod,
    ComponentKind.EXPORTER: ResultExporter,
}


def _validate_zero_argument_factory(factory: object) -> ComponentFactory:
    if not callable(factory):
        raise PluginError("plugin entry point must resolve to a callable factory")
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError) as exc:
        raise PluginError("unable to verify plugin factory signature") from exc
    if signature.parameters:
        raise PluginError("plugin factory must declare zero parameters")
    return factory


def _entry_point_distribution(entry_point: object) -> tuple[str | None, str | None]:
    distribution = getattr(entry_point, "dist", None)
    if distribution is None:
        return None, None
    name: str | None = None
    metadata = getattr(distribution, "metadata", None)
    if metadata is not None:
        try:
            raw_name = metadata.get("Name")
        except AttributeError:
            raw_name = None
        if isinstance(raw_name, str) and raw_name:
            name = raw_name
    version = getattr(distribution, "version", None)
    if not isinstance(version, str) or not version:
        version = None
    return name, version


class PluginRegistry:
    """One lightweight registry with category views for all five plugin kinds."""

    __slots__ = ("_components", "_failures")

    def __init__(self) -> None:
        self._components: dict[tuple[ComponentKind, str], _RegisteredComponent] = {}
        self._failures: list[PluginLoadFailure] = []

    @property
    def failures(self) -> tuple[PluginLoadFailure, ...]:
        """Installed-plugin failures isolated during discovery."""

        return tuple(self._failures)

    def register_factory(
        self,
        factory: ComponentFactory,
        *,
        expected_kind: ComponentKind | None = None,
        built_in: bool = False,
    ) -> ComponentDescriptor:
        """Instantiate, validate, and register one zero-argument component factory."""

        validated_factory = _validate_zero_argument_factory(factory)
        try:
            component = validated_factory()
        except Exception as exc:
            raise PluginError("plugin factory failed during component construction") from exc
        return self._register_component(
            validated_factory,
            component,
            expected_kind=expected_kind,
            built_in=built_in,
        )

    def _register_component(
        self,
        factory: ComponentFactory,
        component: object,
        *,
        expected_kind: ComponentKind | None,
        built_in: bool,
    ) -> ComponentDescriptor:
        descriptor = getattr(component, "descriptor", None)
        if not isinstance(descriptor, ComponentDescriptor):
            raise PluginError("plugin component must expose a ComponentDescriptor")
        if expected_kind is not None and descriptor.kind is not expected_kind:
            raise PluginCompatibilityError(
                "plugin descriptor kind does not match its registration category"
            )
        if descriptor.protocol_version != SUPPORTED_PROTOCOL_VERSION:
            raise PluginCompatibilityError(
                f"component {descriptor.qualified_id!r} declares unsupported protocol major "
                f"{descriptor.protocol_version}; supported major is {SUPPORTED_PROTOCOL_VERSION}"
            )

        protocol = _PROTOCOLS[descriptor.kind]
        if not isinstance(component, protocol):
            raise PluginCompatibilityError(
                f"component {descriptor.qualified_id!r} does not conform to the "
                f"{descriptor.kind.value} protocol"
            )

        key = (descriptor.kind, descriptor.qualified_id)
        if key in self._components:
            raise _DuplicateComponentError(
                f"duplicate active component ID {descriptor.qualified_id!r} "
                f"in category {descriptor.kind.value!r}"
            )

        self._components[key] = _RegisteredComponent(
            descriptor=descriptor,
            factory=factory,
            component=component,
            built_in=built_in,
        )
        return descriptor

    def list(self, kind: ComponentKind | None = None) -> tuple[ComponentDescriptor, ...]:
        """List active descriptors in deterministic category/ID order."""

        if kind is not None and not isinstance(kind, ComponentKind):
            raise TypeError("kind must be a ComponentKind or None")
        descriptors = [
            registered.descriptor
            for (registered_kind, _), registered in self._components.items()
            if kind is None or registered_kind is kind
        ]
        return tuple(sorted(descriptors, key=lambda item: (item.kind.value, item.qualified_id)))

    def describe(
        self,
        qualified_id: str,
        *,
        kind: ComponentKind | None = None,
    ) -> ComponentDescriptor:
        """Return one active descriptor, rejecting ambiguous cross-category IDs."""

        matches = self._matching_components(qualified_id, kind=kind)
        return matches[0].descriptor

    def get(
        self,
        qualified_id: str,
        *,
        kind: ComponentKind | None = None,
    ) -> object:
        """Return one already-constructed validated component instance."""

        matches = self._matching_components(qualified_id, kind=kind)
        return matches[0].component

    def _matching_components(
        self,
        qualified_id: str,
        *,
        kind: ComponentKind | None,
    ) -> tuple[_RegisteredComponent, ...]:
        if not isinstance(qualified_id, str) or not qualified_id or qualified_id != qualified_id.strip():
            raise ValueError("qualified_id must be a non-empty trimmed string")
        if kind is not None and not isinstance(kind, ComponentKind):
            raise TypeError("kind must be a ComponentKind or None")

        matches = tuple(
            registered
            for (registered_kind, registered_id), registered in self._components.items()
            if registered_id == qualified_id and (kind is None or registered_kind is kind)
        )
        if not matches:
            raise PluginError(f"component {qualified_id!r} is not registered")
        if len(matches) > 1:
            raise PluginError(
                f"component ID {qualified_id!r} is ambiguous across plugin categories; "
                "specify kind"
            )
        return matches

    def discover_installed(self) -> tuple[PluginLoadFailure, ...]:
        """Discover installed entry-point factories without scanning arbitrary paths.

        Ordinary load/compatibility failures are isolated and recorded so one
        broken optional plugin cannot disable unrelated components. Duplicate
        active IDs are different: they raise immediately because retaining one
        environment-order winner would violate deterministic registration.
        """

        self._failures.clear()
        entry_points = importlib_metadata.entry_points()

        for kind in ComponentKind:
            if hasattr(entry_points, "select"):
                selected: Iterable[object] = entry_points.select(
                    group=kind.entry_point_group
                )
            else:  # pragma: no cover - compatibility with legacy metadata shims
                selected = entry_points.get(kind.entry_point_group, ())

            for entry_point in sorted(
                selected,
                key=lambda item: (str(getattr(item, "name", "")), str(getattr(item, "value", ""))),
            ):
                name = str(getattr(entry_point, "name", "<unnamed>"))
                dist_name, dist_version = _entry_point_distribution(entry_point)
                try:
                    loaded = entry_point.load()
                    factory = _validate_zero_argument_factory(loaded)
                    component = factory()
                    self._register_component(
                        factory,
                        component,
                        expected_kind=kind,
                        built_in=False,
                    )
                except _DuplicateComponentError:
                    raise
                except Exception as exc:
                    self._failures.append(
                        PluginLoadFailure(
                            entry_point_group=kind.entry_point_group,
                            entry_point_name=name,
                            distribution_name=dist_name,
                            distribution_version=dist_version,
                            error_type=type(exc).__name__,
                            message=str(exc),
                        )
                    )

        return self.failures


__all__ = [
    "ComponentFactory",
    "PluginLoadFailure",
    "PluginRegistry",
]
