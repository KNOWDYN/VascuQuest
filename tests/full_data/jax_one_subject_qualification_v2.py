"""Run the one-subject JAX qualification with the production bounded-replay backend."""

from __future__ import annotations

import jax_one_subject_qualification as qualification
from vascuquest.disease.solver.jax_disease_v2 import JaxDiseaseOneDSolver

# Reuse the established real-PWDB operator/full-solution qualification contract,
# replacing only the full JAX solver implementation under test.  The operator
# snapshot remains the shared frozen JAX numerical operator from jax_disease.
qualification.JaxDiseaseOneDSolver = JaxDiseaseOneDSolver


if __name__ == "__main__":
    raise SystemExit(qualification.main())
