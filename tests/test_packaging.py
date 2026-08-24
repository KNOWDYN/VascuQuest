"""Batch 0 packaging and public-surface smoke tests."""

from __future__ import annotations

from importlib.metadata import version as distribution_version
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


def test_source_runtime_and_distribution_versions_agree() -> None:
    project_version = _project_version()
    assert vascuquest.__version__ == project_version
    assert distribution_version("vascuquest") == project_version


def test_public_exception_contract_is_exposed() -> None:
    assert set(errors.__all__) == EXPECTED_PUBLIC_ERRORS
    assert EXPECTED_PUBLIC_ERRORS <= set(vascuquest.__all__)

    assert issubclass(errors.VascuQuestError, Exception)
    for name in EXPECTED_PUBLIC_ERRORS - {"VascuQuestError"}:
        exception_type = getattr(vascuquest, name)
        assert issubclass(exception_type, errors.VascuQuestError)

    assert issubclass(errors.PluginCompatibilityError, errors.PluginError)
