from __future__ import annotations

import vascuquest as vq

from vascuquest.domain import EvidenceClass, ScientificResult, ValidityState
from vascuquest.exporters import (
    CSV_EXPORTER_ID,
    JSON_EXPORTER_ID,
    load_result_csv,
    load_result_json,
)
from vascuquest.plugins.descriptor import ComponentKind
from vascuquest.schema import load_canonical_schema


def _scalar_result(session: vq.DatasetSession) -> ScientificResult:
    return ScientificResult(
        dataset_identity=session.identity,
        quantity=load_canonical_schema().quantity("age"),
        values=45.0,
        provenance_ref="sha256:manual-source-age",
        source_unit="years",
        source_label="age [years]",
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.NOT_EVALUATED,
    )


def test_open_dataset_registers_and_executes_builtin_exporters_without_data_access(
    tmp_path,
) -> None:
    session = vq.open_dataset(offline=True)
    result = _scalar_result(session)

    json_path = tmp_path / "age.json"
    csv_path = tmp_path / "age.csv"
    returned_json = session.export(result, JSON_EXPORTER_ID, json_path)
    returned_csv = session.export(result, CSV_EXPORTER_ID, csv_path)

    assert returned_json == json_path
    assert returned_csv["data_path"] == csv_path
    assert returned_csv["metadata_path"].exists()

    rebuilt_json = load_result_json(json_path)
    rebuilt_csv = load_result_csv(csv_path)
    for rebuilt in (rebuilt_json, rebuilt_csv):
        assert rebuilt.dataset_identity == session.identity
        assert rebuilt.quantity == result.quantity
        assert rebuilt.values == 45.0
        assert rebuilt.canonical_unit == "years"
        assert rebuilt.evidence is EvidenceClass.SOURCE
        assert rebuilt.provenance_ref == result.provenance_ref


def test_public_plugin_catalog_lists_builtin_exporters_without_data_acquisition() -> None:
    descriptors = vq.plugins.list(ComponentKind.EXPORTER)
    ids = {descriptor.qualified_id for descriptor in descriptors}
    assert JSON_EXPORTER_ID in ids
    assert CSV_EXPORTER_ID in ids

    json_descriptor = vq.plugins.describe(JSON_EXPORTER_ID, kind=ComponentKind.EXPORTER)
    csv_descriptor = vq.plugins.describe(CSV_EXPORTER_ID, kind=ComponentKind.EXPORTER)
    assert json_descriptor.kind is ComponentKind.EXPORTER
    assert csv_descriptor.kind is ComponentKind.EXPORTER
    assert json_descriptor.protocol_version == 1
    assert csv_descriptor.protocol_version == 1
