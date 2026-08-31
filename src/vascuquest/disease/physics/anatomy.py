"""Frozen PWDB 116-artery anatomy targets used by Virtual Disease v1.

Segment identities follow the public PWDB ``116_artery_model.txt`` input
network. Measurement-site mappings are intentionally not used as substitutes
for anatomical disease targets.
"""

from __future__ import annotations

from vascuquest.errors import AdmissibilityError

PWDB_116_ARTERY_MODEL_SOURCE = (
    "https://github.com/peterhcharlton/pwdb/blob/master/"
    "pwdb_v0.1/Input%20Data/116_artery_model.txt"
)

CAROTID_TARGET_SEGMENTS = {
    ("right", "common_carotid"): "5",
    ("right", "internal_carotid"): "12",
    ("left", "common_carotid"): "15",
    ("left", "internal_carotid"): "16",
}

ILIAC_TARGET_SEGMENTS = {
    ("left", "common_iliac"): "42",
    ("right", "common_iliac"): "43",
    ("left", "external_iliac"): "44",
    ("right", "external_iliac"): "50",
}

SEGMENT_NAMES = {
    "5": "Right Common Carotid Artery",
    "12": "Right Internal Carotid Artery",
    "15": "Left Common Carotid Artery",
    "16": "Left Internal Carotid Artery",
    "28": "Abdominal Aorta I",
    "35": "Abdominal Aorta II",
    "37": "Abdominal Aorta III",
    "39": "Abdominal Aorta IV",
    "41": "Abdominal Aorta V",
    "42": "Left Common Iliac Artery",
    "43": "Right Common Iliac Artery",
    "44": "Left External Iliac Artery",
    "50": "Right External Iliac Artery",
}

AAA_PATH_SEGMENTS = ("28", "35", "37", "39", "41")

# Paths used only for a model-space carotid-femoral characteristic travel-time
# calculation. The final tuple member is sampled at half segment length.
LEFT_CAROTID_TRAVEL_PATH = (
    ("1", 1.0),
    ("2", 1.0),
    ("15", 0.5),
)
LEFT_FEMORAL_TRAVEL_PATH = (
    ("1", 1.0),
    ("2", 1.0),
    ("14", 1.0),
    ("18", 1.0),
    ("27", 1.0),
    ("28", 1.0),
    ("35", 1.0),
    ("37", 1.0),
    ("39", 1.0),
    ("41", 1.0),
    ("42", 1.0),
    ("44", 1.0),
    ("46", 0.5),
)

# Bilateral large-conduit set. The left paths above are a subset, which makes
# their characteristic travel times scale exactly under a uniform beta factor.
LARGE_ARTERY_STIFFENING_SEGMENTS = frozenset(
    {
        "1", "2", "3", "5", "12", "14", "15", "16", "18", "27",
        "28", "35", "37", "39", "41", "42", "43", "44", "46", "50", "52",
    }
)


def carotid_segment(side: str, artery: str) -> str:
    try:
        return CAROTID_TARGET_SEGMENTS[(side, artery)]
    except KeyError as exc:
        raise AdmissibilityError(
            f"unsupported carotid anatomy target side={side!r}, artery={artery!r}"
        ) from exc


def iliac_segment(side: str, artery: str) -> str:
    try:
        return ILIAC_TARGET_SEGMENTS[(side, artery)]
    except KeyError as exc:
        raise AdmissibilityError(
            f"unsupported iliac anatomy target side={side!r}, artery={artery!r}"
        ) from exc


__all__ = [
    "AAA_PATH_SEGMENTS",
    "CAROTID_TARGET_SEGMENTS",
    "ILIAC_TARGET_SEGMENTS",
    "LARGE_ARTERY_STIFFENING_SEGMENTS",
    "LEFT_CAROTID_TRAVEL_PATH",
    "LEFT_FEMORAL_TRAVEL_PATH",
    "PWDB_116_ARTERY_MODEL_SOURCE",
    "SEGMENT_NAMES",
    "carotid_segment",
    "iliac_segment",
]
