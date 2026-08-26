"""Tier-4 entry point with bounded large-file oracle transport tuning.

The scientific oracle, assertions, provenance checks, Python/CLI parity checks,
and performance thresholds remain defined by ``path_release_validation``. This
entry point changes only HTTP-range granularity for the independent oracle so
multi-gigabyte HDF5 metadata traversal does not amplify into thousands of tiny
requests. The cache remains bounded to 64 MiB and no whole-file fallback exists.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import path_release_validation as validation

# 2 MiB ranges amortize remote HDF5 metadata/reference seeks while remaining
# sparse relative to the 5.9–8.2 GiB canonical PWDB path artifacts. Thirty-two
# blocks bound the oracle's in-memory byte-range cache to 64 MiB.
validation.RANGE_BLOCK_BYTES = 2 * 1024 * 1024
validation.RANGE_CACHE_BLOCKS = 32


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-id", required=True, choices=tuple(validation.EXPECTED))
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    validation.run(args.artifact_id, args.report)


if __name__ == "__main__":
    main()
