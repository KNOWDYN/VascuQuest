"""Fail-fast Colab preflight for the JAX split-solver qualification.

This script deliberately imports heavyweight qualification dependencies one at a
time with visible timing.  It is intended to diagnose stale/orphan Colab
processes, GPU initialization stalls, and unexpectedly slow imports before the
expensive numerical qualification is launched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time


def _stamp(message: str) -> None:
    print(f"[preflight +{time.perf_counter() - STARTED:8.3f}s] {message}", flush=True)


def _run_text(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    text = (completed.stdout or "") + (completed.stderr or "")
    return text.strip()


STARTED = time.perf_counter()
_stamp(f"Python started: {sys.executable} {sys.version.split()[0]}")

# A previously interrupted subprocess.run() can leave its child alive in a
# notebook runtime.  Report such processes before touching JAX.
ps = _run_text(["ps", "-eo", "pid,ppid,etime,stat,cmd"])
stale = [
    line
    for line in ps.splitlines()
    if (
        "jax_split_one_subject_qualification.py" in line
        or "jax_split_temporal_refinement.py" in line
    )
    and "jax_split_colab_preflight.py" not in line
]
if stale:
    _stamp("STALE QUALIFICATION PROCESS(ES) DETECTED:")
    for line in stale:
        print(line, flush=True)
    raise RuntimeError(
        "A previous qualification child process is still alive. Terminate/reset "
        "the Colab runtime before qualification; do not start another JAX solve."
    )
_stamp("No stale qualification child process detected")

nvidia = _run_text([
    "nvidia-smi",
    "--query-compute-apps=pid,process_name,used_memory",
    "--format=csv,noheader,nounits",
])
_stamp("nvidia-smi compute-process snapshot:")
print(nvidia if nvidia else "<no compute processes reported>", flush=True)

_t = time.perf_counter()
import numpy as np  # noqa: E402
_stamp(f"NumPy import PASS ({time.perf_counter() - _t:.3f}s), version={np.__version__}")

_t = time.perf_counter()
import jax  # noqa: E402
_stamp(f"JAX import PASS ({time.perf_counter() - _t:.3f}s), version={jax.__version__}")

jax.config.update("jax_enable_x64", True)
_t = time.perf_counter()
devices = jax.devices()
_stamp(f"JAX device discovery PASS ({time.perf_counter() - _t:.3f}s): {devices}")
if not any(device.platform == "gpu" for device in devices):
    raise RuntimeError("No JAX GPU device is available in this runtime")

_t = time.perf_counter()
import vascuquest as vq  # noqa: E402,F401
_stamp(f"vascuquest import PASS ({time.perf_counter() - _t:.3f}s)")

_t = time.perf_counter()
import jax_one_subject_qualification as reference  # noqa: E402,F401
_stamp(f"reference qualification module import PASS ({time.perf_counter() - _t:.3f}s)")

_t = time.perf_counter()
from vascuquest.disease.solver.disease_finite_volume import DiseaseOneDSolver  # noqa: E402,F401
_stamp(f"NumPy disease solver import PASS ({time.perf_counter() - _t:.3f}s)")

_t = time.perf_counter()
from vascuquest.disease.solver.jax_split_disease import (  # noqa: E402
    JAX_SPLIT_SCHEME_ID,
    JaxDiseaseOneDSolver,
)
_stamp(
    f"JAX split solver import PASS ({time.perf_counter() - _t:.3f}s), "
    f"scheme={JAX_SPLIT_SCHEME_ID}"
)

# Force a tiny synchronized XLA execution so import success is not confused with
# a backend that stalls on first device use.
_t = time.perf_counter()
x = jax.jit(lambda value: value * value + 1.0)(jax.numpy.asarray([1.0, 2.0]))
x.block_until_ready()
_stamp(f"tiny synchronized JIT/device execution PASS ({time.perf_counter() - _t:.3f}s)")

_stamp("JAX SPLIT COLAB PREFLIGHT: PASS")
