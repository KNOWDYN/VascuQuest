from pathlib import Path
import numpy as np
import pytest
pytest.importorskip("matplotlib")
from vascuquest.domain import Coordinate, DatasetIdentity, EvidenceClass, MeasurementSite, QuantityDefinition, SubjectKey, Waveform
from vascuquest.plot import FigureSpec, InsetSpec, LayerSpec, PanelSpec, render


def _wave(label, phase=0.0):
    identity = DatasetIdentity("PWDB", "3275625", "10.5281/zenodo.3275625", "v1")
    subject = SubjectKey(identity, "1"); location = MeasurementSite("AorticRoot")
    t = np.linspace(0, 1, 200, endpoint=False)
    q = QuantityDefinition(label, label, label, "waveform", "v1", "pressure", "mmHg")
    return Waveform(identity, q, np.sin(2*np.pi*t+phase), f"prov:{label}", ("time",), (Coordinate("time",t,"s"),), subject=subject, location=location, evidence=EvidenceClass.SOURCE)


def test_legend_is_outside_all_axes_including_inset(tmp_path: Path):
    a,b=_wave("A"),_wave("B",0.4)
    inset=InsetSpec((0.55,0.55,0.4,0.35),(LayerSpec("line",a,label="Inset A"),))
    spec=FigureSpec((PanelSpec("A",(LayerSpec("line",a,label="A"),LayerSpec("line",b,label="B")),insets=(inset,)),))
    fig=render(spec,tmp_path/"figure.svg")
    fig.canvas.draw(); renderer=fig.canvas.get_renderer()
    assert fig.legends
    legend_box=fig.legends[0].get_window_extent(renderer)
    axes=[*fig.axes]
    for ax in list(fig.axes): axes.extend(getattr(ax,"child_axes",()))
    assert all(not legend_box.overlaps(ax.get_tightbbox(renderer)) for ax in axes)
    assert (tmp_path/"figure.svg").exists()
