from __future__ import annotations

import numpy as np

from vascuquest.disease.baseline.model import MMHG_TO_PA
from vascuquest.disease.baseline.pwdb_reader import PWDBModelConfigurationReader


def test_model_configuration_reader_normalizes_exported_pwdb_fields(tmp_path) -> None:
    path = tmp_path / "pwdb_model_configs.csv"
    path.write_text(
        "Subject Number, age [years], hr [bpm], sv [ml], pft [ms], rfv [ml], "
        "dbp [mmHg], mbp [mmHg], viscosity [Pa s], alpha [-], p_out [mmHg], "
        "density [kg /m^3], lvet [ms], pvr [Pa s/m^3], b0 [g/s], b1 [g cm/s], "
        "k1 [g/s^2/cm], k2 [/cm], k3 [g/s^2/cm]\n"
        "7, 55, 70, 75, 85, 1.2, 80, 95, 0.004, 1.1, 5, 1050, 280, "
        "1.2e9, 0.2, 0.3, 1000, -20, 900000\n",
        encoding="utf-8",
    )
    config = PWDBModelConfigurationReader(path).read_subject("7")
    assert config.canonical_subject_id == "7"
    assert config.age_years == 55
    assert config.heart_rate_bpm == 70
    assert np.isclose(config.peak_flow_time_s, 0.085)
    assert np.isclose(config.lvet_s, 0.280)
    assert np.isclose(config.diastolic_pressure_pa, 80 * MMHG_TO_PA)
    assert np.isclose(config.mean_pressure_pa, 95 * MMHG_TO_PA)
    assert np.isclose(config.outlet_pressure_pa, 5 * MMHG_TO_PA)
    assert config.source_member == "pwdb_model_configs.csv"
