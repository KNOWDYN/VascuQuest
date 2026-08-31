from __future__ import annotations

import vascuquest as vq
from vascuquest.disease import (
    RuntimeDiseaseDataset,
    VirtualDiseasePopulationGenerator,
    generate_population,
    write_runtime_bundle,
)


def test_virtual_disease_is_exposed_through_public_python_namespace() -> None:
    assert vq.disease.generate_population is generate_population
    assert vq.disease.write_runtime_bundle is write_runtime_bundle
    assert vq.disease.RuntimeDiseaseDataset is RuntimeDiseaseDataset
    assert vq.disease.VirtualDiseasePopulationGenerator is VirtualDiseasePopulationGenerator
    assert callable(vq.disease.presets)
    assert callable(vq.disease.specification)
