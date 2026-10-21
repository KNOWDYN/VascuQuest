# Remote PWDB path access

VascuQuest can read selected PWDB path-resolved subjects directly from the canonical Zenodo MATLAB-v7.3/HDF5 artifacts without downloading each multi-gigabyte file in full.

The capability is implemented by `vascuquest.hemospace.HTTPRangeReader` and `PWDBRemotePathClient`.

## Design

`HTTPRangeReader` presents a seekable read-only file-object interface backed by HTTP `Range` requests. `h5py` therefore resolves only the HDF5 metadata and datasets needed for the requested subjects. If the remote server ignores byte ranges, VascuQuest fails closed rather than falling back to a whole-file download.

`PWDBRemotePathClient` first checks the Zenodo record metadata against the packaged canonical manifest: filename, MD5 checksum and file size must agree. This verifies the canonical remote artifact identity without re-downloading all bytes solely to recompute an MD5.

## Ragged source preservation

Canonical path exports can contain point waveforms whose native lengths are not identical across the complete path. Remote reads therefore return `RaggedPathWaveField` rather than forcing a rectangular matrix.

No padding, interpolation, truncation or smoothing is performed. `RaggedPathWaveField.aligned_segment(segment_no)` converts only a selected native segment to the standard `PathWaveField` contract, and only when every requested signal at every retained segment point has exactly common sample support. Otherwise it raises `IntegrityError`.

This separation is important for blinded studies: full-path source extraction can remain lossless and ragged, while temporal matrix admissibility is tested only after an anatomical segment has been selected independently.

## Example

```python
from vascuquest.hemospace import PWDBRemotePathClient

client = PWDBRemotePathClient(block_size=1 << 20, max_cache_blocks=64)
client.verify_remote_identity()

subjects = ["1", "730", "1459"]
for raw in client.iter_artifact_subjects(
    "path_aorta_brain",
    "aorta_brain",
    subjects,
    signals=("P", "U", "A"),
):
    print(raw.subject_id, raw.point_lengths("P"))
    segment = raw.aligned_segment(15)
    print(segment.field.matrix("U").shape, segment.time_s.shape)
```

For the split `aorta_foot` source, read P, U and A sequentially from their three canonical artifacts and combine the corresponding `RaggedPathWaveField` objects with `merge_ragged_path_fields`.

## Evidence and provenance boundary

The packaged manifest remains the canonical declaration of PWDB record `3275625` / DOI `10.5281/zenodo.3275625`. Remote identity verification checks the authoritative Zenodo record metadata against that manifest. Downstream study subsets should separately hash the exact subject arrays they materialize for permanent reproducibility.
