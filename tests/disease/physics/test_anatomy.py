from __future__ import annotations

from vascuquest.disease.physics.anatomy import carotid_segment, iliac_segment


def test_frozen_carotid_targets_match_pwdb_116_artery_model() -> None:
    assert carotid_segment("right", "common_carotid") == "5"
    assert carotid_segment("right", "internal_carotid") == "12"
    assert carotid_segment("left", "common_carotid") == "15"
    assert carotid_segment("left", "internal_carotid") == "16"


def test_frozen_iliac_targets_match_pwdb_116_artery_model() -> None:
    assert iliac_segment("left", "common_iliac") == "42"
    assert iliac_segment("right", "common_iliac") == "43"
    assert iliac_segment("left", "external_iliac") == "44"
    assert iliac_segment("right", "external_iliac") == "50"
