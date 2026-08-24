"""Unit tests for virtual-subject identity semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.subject import VirtualSubject


def _dataset(*, record_id: str = "3275625") -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id=record_id,
        persistent_identifier=f"10.5281/zenodo.{record_id}",
        schema_version="1",
    )


def _subject(*, record_id: str = "3275625", subject_id: str = "1") -> VirtualSubject:
    return VirtualSubject(SubjectKey(_dataset(record_id=record_id), subject_id))


def test_virtual_subject_exposes_exact_subject_and_dataset_identity() -> None:
    subject = _subject(subject_id="42")

    assert subject.canonical_subject_id == "42"
    assert subject.dataset_identity == _dataset()
    assert subject.key == SubjectKey(_dataset(), "42")


def test_virtual_subject_has_value_semantics() -> None:
    left = _subject()
    right = _subject()
    other_subject = _subject(subject_id="2")
    other_dataset = _subject(record_id="9999999")

    assert left == right
    assert hash(left) == hash(right)
    assert left != other_subject
    assert left != other_dataset


def test_virtual_subject_requires_subject_key() -> None:
    with pytest.raises(TypeError):
        VirtualSubject("1")  # type: ignore[arg-type]


def test_virtual_subject_is_immutable_and_hashable() -> None:
    subject = _subject()

    assert {subject}
    with pytest.raises(FrozenInstanceError):
        subject.key = SubjectKey(_dataset(), "2")  # type: ignore[misc]


def test_virtual_subject_does_not_embed_unlabelled_scientific_attributes() -> None:
    subject = _subject()

    assert not hasattr(subject, "age")
    assert not hasattr(subject, "plausibility")
    assert not hasattr(subject, "model_parameters")
    assert not hasattr(subject, "geometry")
    assert not hasattr(subject, "waveforms")
