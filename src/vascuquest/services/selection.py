"""Deterministic virtual-subject selection without a custom query language."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from vascuquest.domain.cohort import Cohort
from vascuquest.errors import SelectionError
from vascuquest.ports.backend import DatasetBackend, QuantityRequest


class SelectionService:
    """Build reproducible cohorts from explicit IDs and exact-match filters."""

    __slots__ = ("_backend",)

    def __init__(self, backend: DatasetBackend) -> None:
        if not isinstance(backend, DatasetBackend):
            raise TypeError("backend must conform to DatasetBackend")
        self._backend = backend

    def select(
        self,
        *,
        subject_ids: Iterable[str] | None = None,
        where: Mapping[str, object] | None = None,
    ) -> Cohort:
        all_subjects = self._backend.subjects()
        identity = self._backend.identity()
        canonical_order = tuple(subject.canonical_subject_id for subject in all_subjects)
        available = set(canonical_order)

        requested: set[str] | None = None
        selection_specification: list[str] = []
        if subject_ids is not None:
            raw_ids = tuple(subject_ids)
            if any(not isinstance(value, str) or not value or value != value.strip() for value in raw_ids):
                raise SelectionError("subject_ids must contain non-empty trimmed strings")
            if len(set(raw_ids)) != len(raw_ids):
                raise SelectionError("subject_ids must not contain duplicates")
            unknown = tuple(value for value in raw_ids if value not in available)
            if unknown:
                raise SelectionError(f"unknown subject IDs: {unknown!r}")
            requested = set(raw_ids)
            selection_specification.append("subject_ids=" + ",".join(raw_ids))

        selected = tuple(
            subject_id
            for subject_id in canonical_order
            if requested is None or subject_id in requested
        )

        normalized_where = {} if where is None else dict(where)
        if any(not isinstance(key, str) or not key or key != key.strip() for key in normalized_where):
            raise SelectionError("where keys must be non-empty canonical quantity identifiers")

        inclusion_filters: list[str] = []
        for quantity in sorted(normalized_where):
            expected = normalized_where[quantity]
            current = Cohort(
                dataset_identity=identity,
                canonical_subject_ids=selected,
                ordering_rule="canonical_backend_subject_order",
            )
            result = self._backend.get_quantity(
                QuantityRequest(quantity=quantity, cohort=current)
            )
            if result.dimensions != ("subject",):
                raise SelectionError(
                    f"selection quantity {quantity!r} is not a subject-wise scalar"
                )
            try:
                values = tuple(result.values)
            except TypeError as exc:
                raise SelectionError(
                    f"selection quantity {quantity!r} did not return subject-wise values"
                ) from exc
            if len(values) != len(selected):
                raise SelectionError(
                    f"selection quantity {quantity!r} returned misaligned subject values"
                )
            selected = tuple(
                subject_id
                for subject_id, value in zip(selected, values, strict=True)
                if value is not None and value == expected
            )
            inclusion_filters.append(f"{quantity}={expected!r}")

        return Cohort(
            dataset_identity=identity,
            canonical_subject_ids=selected,
            ordering_rule="canonical_backend_subject_order",
            selection_specification=tuple(selection_specification),
            inclusion_filters=tuple(inclusion_filters),
        )


__all__ = ["SelectionService"]
