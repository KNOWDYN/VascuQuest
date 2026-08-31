from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.runtime.geometry import RuntimeGeometrySegment


def test_runtime_geometry_retains_internal_disease_profile_and_is_read_only() -> None:
    x = np.asarray([0.01, 0.03, 0.05])
    radius = np.asarray([0.004, 0.002, 0.004])
    area = np.pi * radius * radius
    geometry = RuntimeGeometrySegment(
        segment_id="15",
        inlet_node=1,
        outlet_node=2,
        length_m=0.06,
        x_m=x,
        reference_radius_m=radius,
        reference_area_m2=area,
        beta_pa=np.asarray([1.0e5, 1.1e5, 1.0e5]),
        source_gamma_pa_s_per_m=np.zeros(3),
        peripheral_c=0.0,
        peripheral_r=0.0,
    )
    assert geometry.reference_radius_m[1] < geometry.reference_radius_m[0]
    with pytest.raises(ValueError):
        geometry.reference_radius_m[1] = 0.003
