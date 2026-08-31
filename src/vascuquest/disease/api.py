"""Public convenience API for generating Virtual Disease populations."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from vascuquest.bootstrap import open_dataset
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry
from vascuquest.disease.catalogue import specification
from vascuquest.disease.model import DiseaseCondition, DiseasePopulationRequest
from vascuquest.disease.runtime.dataset import RuntimeDiseaseDataset
from vascuquest.disease.runtime.generator import VirtualDiseasePopulationGenerator
from vascuquest.disease.runtime.store import RuntimeDiseaseStore
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.errors import DatasetUnavailableError


def generate_population(
    *,
    patients: int,
    age_group: int,
    condition: DiseaseCondition | str,
    parameters: Mapping[str, object] | None = None,
    seed: int = 0,
    dataset: str = "pwdb:3275625",
    source: str | Path | None = None,
    offline: bool = False,
    solver_options: SolverOptions | None = None,
    store: RuntimeDiseaseStore | None = None,
) -> RuntimeDiseaseDataset:
    """Generate one deterministic counterfactual disease population.

    The canonical PWDB source dataset remains immutable. Selected PWDB subject
    numbers are preserved under a new content-addressed ``PWDB-VD`` dataset
    identity, and every generated result retains ``MODELLED`` evidence.
    """

    request = DiseasePopulationRequest(
        patients=patients,
        age_group=age_group,
        specification=specification(condition, parameters),
        seed=seed,
    )
    session = open_dataset(dataset, source=source, offline=offline)

    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    if source is not None:
        source_path = Path(source).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise DatasetUnavailableError(
                f"source must identify an existing local PWDB directory: {source_path}"
            )
        try:
            registry.register_local(source_path)
        except ValueError as exc:
            raise DatasetUnavailableError(str(exc)) from exc

    generator = VirtualDiseasePopulationGenerator(
        ArtifactAcquirer(paths, registry),
        offline=offline,
        solver_options=solver_options,
        store=store,
    )
    return generator.generate(session, request)


__all__ = ["generate_population"]
