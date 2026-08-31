"""In-process store for generated Virtual Disease population datasets."""

from __future__ import annotations

from .dataset import RuntimeDiseaseDataset


class RuntimeDiseaseStore:
    """Content-addressed runtime-only store; it never writes PWDB or disk state."""

    __slots__ = ("_datasets",)

    def __init__(self) -> None:
        self._datasets: dict[str, RuntimeDiseaseDataset] = {}

    def put(self, dataset: RuntimeDiseaseDataset) -> RuntimeDiseaseDataset:
        if not isinstance(dataset, RuntimeDiseaseDataset):
            raise TypeError("dataset must be a RuntimeDiseaseDataset")
        existing = self._datasets.get(dataset.run_id)
        if existing is not None:
            if (
                existing.identity != dataset.identity
                or existing.parent_identity != dataset.parent_identity
                or existing.cohort.canonical_subject_ids
                != dataset.cohort.canonical_subject_ids
                or existing.run_identity != dataset.run_identity
            ):
                raise ValueError("content-addressed disease run ID collision")
            return existing
        self._datasets[dataset.run_id] = dataset
        return dataset

    def get(self, run_id: str) -> RuntimeDiseaseDataset:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be non-empty")
        try:
            return self._datasets[run_id]
        except KeyError as exc:
            raise KeyError(f"runtime disease store has no run {run_id!r}") from exc

    def contains(self, run_id: str) -> bool:
        if not isinstance(run_id, str) or not run_id:
            return False
        return run_id in self._datasets

    def run_ids(self) -> tuple[str, ...]:
        return tuple(self._datasets)

    def clear(self) -> None:
        self._datasets.clear()


__all__ = ["RuntimeDiseaseStore"]
