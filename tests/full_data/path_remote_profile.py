"""Temporary operation-level profiler for canonical remote PWDB HDF5 traversal.

This script does not validate or alter scientific values. It profiles the exact
metadata/reference operations used by the Tier-4 oracle and reports elapsed time,
HTTP range-count deltas and transferred-byte deltas after every operation. It is
intended to identify pathological HDF5 traversal before the production reader is
changed again.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time
from typing import Any, Callable, TypeVar

import h5py
import numpy as np

import path_release_validation as validation
from vascuquest.backends.pwdb3275625.http_range import HTTPRangeReader, verify_zenodo_file_identity
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, verify_artifact
from vascuquest.schema import load_manifest

T = TypeVar("T")


def _measure(label: str, remote: HTTPRangeReader | None, fn: Callable[[], T]) -> T:
    before_bytes = 0 if remote is None else remote.bytes_transferred
    before_ranges = 0 if remote is None else remote.range_requests
    print(f"PROFILE START {label}", flush=True)
    started = time.perf_counter()
    value = fn()
    elapsed = time.perf_counter() - started
    after_bytes = 0 if remote is None else remote.bytes_transferred
    after_ranges = 0 if remote is None else remote.range_requests
    print(
        f"PROFILE DONE {label}: {elapsed:.6f}s; "
        f"+{after_bytes - before_bytes} bytes; +{after_ranges - before_ranges} ranges; "
        f"total={after_bytes} bytes/{after_ranges} ranges",
        flush=True,
    )
    return value


def profile(artifact_id: str) -> None:
    if artifact_id not in validation.EXPECTED:
        raise ValueError(f"unsupported path artifact {artifact_id!r}")
    expected = validation.EXPECTED[artifact_id]
    manifest = load_manifest()
    artifact = manifest.artifact(artifact_id)

    paths = DataPaths.default()
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry, manifest=manifest)
    model_config = _measure(
        "acquire model_configurations",
        None,
        lambda: validation._acquire_with_retry(acquirer, "model_configurations"),
    )
    inspection = verify_artifact(model_config, manifest.artifact("model_configurations"))
    assert inspection.state.value == "verified"
    subject_id = validation._subject_for_age(model_config, int(expected["age"]))
    subject_number = int(subject_id)
    print(f"PROFILE subject_id={subject_id} age={expected['age']}", flush=True)

    source = validation._remote_source(artifact)
    metadata = _measure(
        "verify Zenodo identity",
        None,
        lambda: verify_zenodo_file_identity(source),
    )
    remote = HTTPRangeReader(
        source.url,
        size_bytes=metadata.size_bytes,
        block_size=64 * 1024,
        max_blocks=256,
    )
    print(
        f"PROFILE remote_size={metadata.size_bytes}; requested_block=65536; "
        "large-file transport adaptation is applied inside HTTPRangeReader",
        flush=True,
    )

    try:
        handle = _measure("h5py.File(open)", remote, lambda: h5py.File(remote, "r"))
        try:
            data = _measure("handle['data']", remote, lambda: handle["data"])
            path_waves = _measure("data['path_waves']", remote, lambda: data["path_waves"])
            source_path_id = expected["source_path_id"]
            _measure(
                f"source path membership {source_path_id}",
                remote,
                lambda: source_path_id in path_waves,
            )
            group = _measure(
                f"path_waves['{source_path_id}']",
                remote,
                lambda: path_waves[source_path_id],
            )
            dist_refs = _measure("group['dist']", remote, lambda: group["dist"])
            dist_ref = _measure(
                "subject reference from dist",
                remote,
                lambda: validation._subject_ref(dist_refs, subject_number),
            )
            distance_dataset = _measure(
                "resolve distance object reference",
                remote,
                lambda: handle[dist_ref],
            )
            distances = _measure(
                "read distance values",
                remote,
                lambda: validation._numeric(distance_dataset),
            )
            assert bool(np.isfinite(distances).all())
            position_count = int(distances.size)
            print(f"PROFILE position_count={position_count}", flush=True)
            fs_node = _measure("path_waves['fs']", remote, lambda: path_waves["fs"])
            fs = _measure(
                "resolve/read sample rate",
                remote,
                lambda: validation._numeric_scalar(handle, fs_node),
            )
            print(f"PROFILE sample_rate_hz={fs}", flush=True)

            positions = tuple(dict.fromkeys((0, position_count // 2, position_count - 1)))
            for signal in expected["signals"]:
                refs = _measure(
                    f"group['{signal}']",
                    remote,
                    lambda signal=signal: group[signal],
                )
                subject_ref = _measure(
                    f"subject reference {signal}",
                    remote,
                    lambda refs=refs: validation._subject_ref(refs, subject_number),
                )
                subject_cell = _measure(
                    f"resolve subject cell {signal}",
                    remote,
                    lambda subject_ref=subject_ref: handle[subject_ref],
                )
                assert isinstance(subject_cell, h5py.Dataset)
                for position in positions:
                    wave_ref = _measure(
                        f"position reference {signal}@{position}",
                        remote,
                        lambda subject_cell=subject_cell, position=position: validation._ref_at_axis(
                            subject_cell,
                            cardinality=position_count,
                            index_value=int(position),
                        ),
                    )
                    dataset = _measure(
                        f"resolve waveform object {signal}@{position}",
                        remote,
                        lambda wave_ref=wave_ref: handle[wave_ref],
                    )
                    values = _measure(
                        f"read waveform values {signal}@{position}",
                        remote,
                        lambda dataset=dataset: validation._numeric(dataset),
                    )
                    print(
                        f"PROFILE waveform {signal}@{position}: samples={values.size}",
                        flush=True,
                    )
        finally:
            _measure("h5py.File(close)", remote, handle.close)
    finally:
        remote.close()
    print(
        f"PROFILE COMPLETE {artifact_id}: {remote.bytes_transferred} bytes / "
        f"{remote.range_requests} ranges",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-id", default="path_aorta_brain", choices=tuple(validation.EXPECTED))
    args = parser.parse_args()
    profile(args.artifact_id)


if __name__ == "__main__":
    main()
