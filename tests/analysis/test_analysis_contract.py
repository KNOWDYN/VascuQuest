import numpy as np
from vascuquest.analysis import wrap_external
from vascuquest.domain import Coordinate, DatasetIdentity, EvidenceClass, QuantityDefinition, ScientificResult


def test_controlled_external_wrapper_requires_explicit_identity_and_provenance():
    identity = DatasetIdentity("external-test", "record-1", "urn:test:record-1", "v1")
    quantity = QuantityDefinition("external_x", "External X", "Controlled external test quantity.", "numeric", "v1", "dimensionless", "1")
    result = wrap_external(
        dataset_identity=identity,
        quantity=quantity,
        values=np.array([1.0, 2.0, 3.0]),
        provenance_ref="external:test:1",
        dimensions=("observation",),
        coordinates=(Coordinate("observation", np.arange(3), "1"),),
        evidence=EvidenceClass.SOURCE,
    )
    assert isinstance(result, ScientificResult)
    assert result.dataset_identity == identity
    assert result.provenance_ref == "external:test:1"
