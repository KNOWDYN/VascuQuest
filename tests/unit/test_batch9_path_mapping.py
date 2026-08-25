from __future__ import annotations

import pytest

from vascuquest.backends.pwdb3275625.path_reader import (
    PATH_ARTIFACT_SPECS,
    PATH_CAPABILITIES,
    artifact_id_for_path_signal,
)
from vascuquest.errors import CapabilityError
from vascuquest.schema import load_manifest


def test_path_module_import_and_mapping_do_not_require_h5py() -> None:
    manifest = load_manifest()
    expected = {
        capability
        for artifact in manifest.artifacts
        if artifact.role == "path_resolved_waveform_data"
        for capability in artifact.capabilities_provided
    }
    assert PATH_CAPABILITIES == expected
    assert set(PATH_ARTIFACT_SPECS) == {
        "path_aorta_brain",
        "path_aorta_finger",
        "path_aorta_foot_a",
        "path_aorta_foot_p",
        "path_aorta_foot_u",
        "path_aorta_rsubclavian",
    }


def test_path_signal_artifact_mapping_matches_authoritative_export_split() -> None:
    assert artifact_id_for_path_signal("aorta_foot", "P") == "path_aorta_foot_p"
    assert artifact_id_for_path_signal("aorta_foot", "U") == "path_aorta_foot_u"
    assert artifact_id_for_path_signal("aorta_foot", "A") == "path_aorta_foot_a"

    assert artifact_id_for_path_signal("aorta_brain", "P") == "path_aorta_brain"
    assert artifact_id_for_path_signal("aorta_brain", "U") == "path_aorta_brain"
    assert artifact_id_for_path_signal("aorta_brain", "A") == "path_aorta_brain"
    assert artifact_id_for_path_signal("aorta_finger", "P") == "path_aorta_finger"
    assert artifact_id_for_path_signal("aorta_r_subclavian", "A") == "path_aorta_rsubclavian"

    with pytest.raises(CapabilityError, match="unsupported PWDB path signal"):
        artifact_id_for_path_signal("aorta_foot", "PPG")
    with pytest.raises(CapabilityError, match="not available"):
        artifact_id_for_path_signal("unknown_path", "P")
