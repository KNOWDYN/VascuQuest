import vascuquest as vq
from vascuquest.plugins import ComponentKind


def test_public_plugin_catalog_exposes_builtin_backend_without_data_access():
    descriptor = vq.plugins.describe(
        "vascuquest:pwdb3275625",
        kind=ComponentKind.BACKEND,
    )
    assert descriptor.kind is ComponentKind.BACKEND
    assert descriptor.qualified_id == "vascuquest:pwdb3275625"
    assert descriptor.protocol_version == 1
    assert descriptor in vq.plugins.list(ComponentKind.BACKEND)


def test_open_dataset_status_advertises_batch9_path_backend_without_data_access():
    session = vq.open_dataset(offline=True)
    status = session.status()
    assert status.identity.record_id == "3275625"
    assert status.path_resolved_supported is True
    assert status.path_validation_state == "validated_and_available"
