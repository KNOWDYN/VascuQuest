from vascuquest.disease.model import DiseaseQuantityStatus


def test_quantity_status_contract_is_exact_and_exhaustive() -> None:
    assert tuple(item.value for item in DiseaseQuantityStatus) == (
        "UNCHANGED_CAUSAL_INPUT",
        "MODEL_PARAMETER_MODIFIED",
        "RECOMPUTED",
        "DERIVED_FROM_RECOMPUTED",
        "NOT_SUPPORTED",
    )
