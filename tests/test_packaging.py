"""Batch 0 packaging and public-surface smoke tests."""

from __future__ import annotations

from pathlib import Path
import tomllib

import vascuquest
import vascuquest.errors as errors


EXPECTED_PUBLIC_ERRORS = {
    "AdmissibilityError",
    "CapabilityError",
    "DatasetUnavailableError",
    "IntegrityError",
    "NumericalMethodError",
    "PluginCompatibilityError",
    "PluginError",
    "ReproducibilityError",
    "SchemaError",
    "SelectionError",
    "UnitError",
    "VascuQuestError",
    "VascuQuestInternalError",
}


def _project_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as stream:
        metadata = tomllib.load(stream)
    return metadata["project"]["version"]


def test_package_import_exposes_version() -> None:
    assert isinstance(vascuquest.__version__, str)
    assert vascuquest.__version__


def test_runtime_version_matches_project_metadata() -> None:
    assert vascuquest.__version__ == _project_version()


def test_public_exception_contract_is_exposed() -> None:
    assert set(errors.__all__) == EXPECTED_PUBLIC_ERRORS
    assert EXPECTED_PUBLIC_ERRORS <= set(vascuquest.__all__)

    for name in EXPECTED_PUBLIC_ERRORS:
        exception_type = getattr(vascuquest, name)
        assert issubclass(exception_type, Exception)

    assert issubclass(errors.PluginCompatibilityError, errors.PluginError)
    assert issubclass(errors.PluginError, errors.VascuQuestError)
