"""Virtual-subject domain model.

A VascuQuest virtual subject is one simulation instance in an exact virtual-
population dataset. It is not a patient, observed participant, or biological
individual followed longitudinally.

Scientifically interpreted subject attributes such as age, model parameters,
and plausibility remain canonical quantities/results governed by the schema.
They are deliberately not stored here as unlabeled raw scalar fields.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import DatasetIdentity, SubjectKey


@dataclass(frozen=True, slots=True)
class VirtualSubject:
    """Immutable identity of one canonical virtual simulation instance."""

    key: SubjectKey

    def __post_init__(self) -> None:
        if not isinstance(self.key, SubjectKey):
            raise TypeError("key must be a SubjectKey")

    @property
    def dataset_identity(self) -> DatasetIdentity:
        """Exact dataset identity containing this simulation instance."""

        return self.key.dataset_identity

    @property
    def canonical_subject_id(self) -> str:
        """Canonical subject identifier within ``dataset_identity``."""

        return self.key.canonical_subject_id


__all__ = ["VirtualSubject"]
