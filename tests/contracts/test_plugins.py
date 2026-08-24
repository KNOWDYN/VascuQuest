"""Contract tests for VascuQuest component descriptors and plugin registry."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.errors import PluginCompatibilityError, PluginError
from vascuquest.plugins import (
    ComponentDescriptor,
    ComponentKind,
    PluginRegistry,
    SUPPORTED_PROTOCOL_VERSION,
)
import vascuquest.plugins.registry as registry_module


EXPECTED_GROUPS = {
    ComponentKind.BACKEND: "vascuquest.backends",
    ComponentKind.DERIVATION: "vascuquest.derivations",
    ComponentKind.OPERATOR: "vascuquest.operators",
    ComponentKind.DISCOVERY: "vascuquest.discovery",
    ComponentKind.EXPORTER: "vascuquest.exporters",
}


def _descriptor(
    kind: ComponentKind,
    qualified_id: str,
    *,
    protocol_version: int = SUPPORTED_PROTOCOL_VERSION,
) -> ComponentDescriptor:
    return ComponentDescriptor(
        kind=kind,
        name=qualified_id.split(":", 1)[1],
        qualified_id=qualified_id,
        implementation_version="1.2.3",
        protocol_version=protocol_version,
        distribution_name="example-plugin",
        distribution_version="1.2.3",
        summary="Synthetic contract-test component.",
        citations=(),
    )


def _quantity() -> QuantityDefinition:
    return QuantityDefinition(
        canonical_name="example_quantity",
        label="Example quantity",
        description="Synthetic contract-test quantity.",
        value_kind="numeric",
        schema_version="1",
        physical_dimension="dimensionless",
        canonical_unit="1",
        allowed_source_units=("1",),
        applicable_contexts=("measurement_site",),
        source_aliases=(),
        default_evidence=EvidenceClass.SOURCE,
    )


class _Backend:
    def __init__(self, descriptor: ComponentDescriptor) -> None:
        self.descriptor = descriptor

    def identity(self):
        return DatasetIdentity("PWDB", "3275625", "10.5281/zenodo.3275625", "1")

    def capabilities(self):
        return frozenset()

    def subjects(self, request=None):
        return ()

    def locations(self, request=None):
        return ()

    def get_quantity(self, request):
        raise NotImplementedError

    def get_waveform(self, request):
        raise NotImplementedError

    def geometry(self, request):
        raise NotImplementedError


class _Derivation:
    def __init__(self, descriptor: ComponentDescriptor) -> None:
        self.descriptor = descriptor
        self.required_inputs = ()
        self.output_quantity = _quantity()
        self.output_evidence = EvidenceClass.DERIVED
        self.parameter_specs = ()
        self.missing_data_policy = "fail"
        self.citations = ()
        self.validation_scope = "synthetic contract only"
        self.deterministic = True

    def run(self, *, inputs, parameters, context):
        raise NotImplementedError


class _Operator:
    def __init__(self, descriptor: ComponentDescriptor) -> None:
        self.descriptor = descriptor
        self.required_inputs = ()
        self.output_quantities = (_quantity(),)
        self.parameter_specs = ()
        self.assumptions = ()
        self.admissible_domain = "synthetic contract only"
        self.citations = ()
        self.output_evidence = EvidenceClass.MODELLED
        self.deterministic = True

    def run(self, *, inputs, parameters, context):
        raise NotImplementedError


class _Discovery:
    def __init__(self, descriptor: ComponentDescriptor) -> None:
        self.descriptor = descriptor
        self.required_inputs = ()
        self.parameter_specs = ()
        self.missing_data_policy = "fail"
        self.output_schema = "synthetic structured result"
        self.evidence_semantics = "synthetic contract only"
        self.validation_scope = "synthetic contract only"
        self.deterministic = True

    def run(self, *, cohort, inputs, parameters, context):
        raise NotImplementedError


class _Exporter:
    def __init__(self, descriptor: ComponentDescriptor) -> None:
        self.descriptor = descriptor
        self.supported_result_kinds = ("scientific_result",)
        self.supported_output_formats = ("synthetic",)
        self.provenance_retention = "full metadata"

    def export(self, result, destination, options):
        return destination


def _factory_for(kind: ComponentKind, qualified_id: str, *, protocol_version: int = 1):
    descriptor = _descriptor(kind, qualified_id, protocol_version=protocol_version)
    component_type = {
        ComponentKind.BACKEND: _Backend,
        ComponentKind.DERIVATION: _Derivation,
        ComponentKind.OPERATOR: _Operator,
        ComponentKind.DISCOVERY: _Discovery,
        ComponentKind.EXPORTER: _Exporter,
    }[kind]

    def factory():
        return component_type(descriptor)

    return factory


def test_exactly_five_component_kinds_map_to_frozen_entry_point_groups() -> None:
    assert tuple(ComponentKind) == (
        ComponentKind.BACKEND,
        ComponentKind.DERIVATION,
        ComponentKind.OPERATOR,
        ComponentKind.DISCOVERY,
        ComponentKind.EXPORTER,
    )
    assert {kind: kind.entry_point_group for kind in ComponentKind} == EXPECTED_GROUPS


def test_component_descriptor_is_immutable_and_uses_namespaced_identity() -> None:
    descriptor = _descriptor(ComponentKind.BACKEND, "example:backend")
    assert descriptor.qualified_id == "example:backend"

    with pytest.raises(FrozenInstanceError):
        descriptor.summary = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError):
        _descriptor(ComponentKind.BACKEND, "not-namespaced")
    with pytest.raises(TypeError):
        _descriptor(ComponentKind.BACKEND, "example:backend", protocol_version=True)  # type: ignore[arg-type]


def test_registry_accepts_all_five_protocol_categories_and_lists_deterministically() -> None:
    registry = PluginRegistry()
    for kind in reversed(tuple(ComponentKind)):
        registry.register_factory(_factory_for(kind, f"example:{kind.value}"))

    descriptors = registry.list()
    assert len(descriptors) == 5
    assert descriptors == tuple(
        sorted(descriptors, key=lambda item: (item.kind.value, item.qualified_id))
    )
    for kind in ComponentKind:
        descriptor = registry.describe(f"example:{kind.value}", kind=kind)
        assert descriptor.kind is kind
        assert registry.get(descriptor.qualified_id, kind=kind).descriptor == descriptor


def test_duplicate_component_id_is_rejected_without_replacement() -> None:
    registry = PluginRegistry()
    factory = _factory_for(ComponentKind.BACKEND, "example:backend")
    first = registry.register_factory(factory, built_in=True)

    with pytest.raises(PluginError):
        registry.register_factory(_factory_for(ComponentKind.BACKEND, "example:backend"))

    assert registry.describe("example:backend", kind=ComponentKind.BACKEND) == first


def test_incompatible_protocol_major_is_rejected_before_execution() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginCompatibilityError):
        registry.register_factory(
            _factory_for(ComponentKind.DERIVATION, "example:future", protocol_version=2)
        )


def test_registration_category_must_match_descriptor_kind() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginCompatibilityError):
        registry.register_factory(
            _factory_for(ComponentKind.EXPORTER, "example:wrong-group"),
            expected_kind=ComponentKind.BACKEND,
        )


def test_factory_must_have_exact_zero_parameter_signature() -> None:
    registry = PluginRegistry()

    def bad_factory(optional=None):
        return _Backend(_descriptor(ComponentKind.BACKEND, "example:bad"))

    with pytest.raises(PluginError):
        registry.register_factory(bad_factory)


def test_nonconforming_component_is_rejected() -> None:
    registry = PluginRegistry()
    descriptor = _descriptor(ComponentKind.BACKEND, "example:incomplete")

    class Incomplete:
        def __init__(self):
            self.descriptor = descriptor

    def factory():
        return Incomplete()

    with pytest.raises(PluginCompatibilityError):
        registry.register_factory(factory)


class _FakeDistribution:
    def __init__(self, name: str, version: str) -> None:
        self.metadata = {"Name": name}
        self.version = version


class _FakeEntryPoint:
    def __init__(self, group: str, name: str, loaded, *, value: str = "pkg:factory") -> None:
        self.group = group
        self.name = name
        self.value = value
        self._loaded = loaded
        self.dist = _FakeDistribution("fake-dist", "9.9")

    def load(self):
        if isinstance(self._loaded, BaseException):
            raise self._loaded
        return self._loaded


class _FakeEntryPoints(tuple):
    def select(self, *, group: str):
        return tuple(item for item in self if item.group == group)


def test_broken_optional_entry_point_is_isolated_from_valid_plugins(monkeypatch) -> None:
    good = _FakeEntryPoint(
        ComponentKind.BACKEND.entry_point_group,
        "good",
        _factory_for(ComponentKind.BACKEND, "example:good"),
    )
    broken = _FakeEntryPoint(
        ComponentKind.DERIVATION.entry_point_group,
        "broken",
        RuntimeError("optional dependency missing"),
    )
    monkeypatch.setattr(
        registry_module.importlib_metadata,
        "entry_points",
        lambda: _FakeEntryPoints((broken, good)),
    )

    registry = PluginRegistry()
    failures = registry.discover_installed()

    assert registry.describe("example:good", kind=ComponentKind.BACKEND).qualified_id == "example:good"
    assert len(failures) == 1
    assert failures[0].entry_point_name == "broken"
    assert failures[0].distribution_name == "fake-dist"
    assert failures[0].distribution_version == "9.9"
    assert failures[0].error_type == "RuntimeError"


def test_duplicate_ids_during_discovery_fail_instead_of_selecting_order_winner(monkeypatch) -> None:
    first = _FakeEntryPoint(
        ComponentKind.BACKEND.entry_point_group,
        "a-first",
        _factory_for(ComponentKind.BACKEND, "example:duplicate"),
    )
    second = _FakeEntryPoint(
        ComponentKind.BACKEND.entry_point_group,
        "b-second",
        _factory_for(ComponentKind.BACKEND, "example:duplicate"),
    )
    monkeypatch.setattr(
        registry_module.importlib_metadata,
        "entry_points",
        lambda: _FakeEntryPoints((second, first)),
    )

    with pytest.raises(PluginError):
        PluginRegistry().discover_installed()


def test_registry_exposes_no_arbitrary_file_path_plugin_loader() -> None:
    public_names = {name for name in dir(PluginRegistry) if not name.startswith("_")}
    assert "load_path" not in public_names
    assert "register_path" not in public_names
    assert "install" not in public_names
