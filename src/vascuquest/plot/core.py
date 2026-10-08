"""Declarative publication-grade scientific plotting for VascuQuest results."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
import math
import numpy as np

from vascuquest.analysis.core import require_optional_dependency
from vascuquest.domain.result import ScientificResult, Waveform
from vascuquest.errors import AdmissibilityError

_ALLOWED_KINDS = {"line", "scatter", "step", "hist", "heatmap", "hexbin", "ecdf"}

@dataclass(frozen=True, slots=True)
class LegendPolicy:
    mode: str = "auto"
    min_pad_fraction: float = 0.015
    max_pad_fraction: float = 0.04
    max_right_fraction: float = 0.28
    max_entries_right: int = 14
    max_entries_per_column_bottom: int = 6
    def __post_init__(self) -> None:
        if self.mode not in {"auto", "right", "bottom"}: raise ValueError("legend mode must be auto, right, or bottom")
        if not 0 < self.min_pad_fraction <= self.max_pad_fraction < 0.2: raise ValueError("legend padding fractions must satisfy 0 < min <= max < 0.2")

@dataclass(frozen=True, slots=True)
class LayerSpec:
    kind: str
    y: ScientificResult
    x: ScientificResult | None = None
    label: str | None = None
    alpha: float | None = None
    marker: str | None = None
    linewidth: float | None = None
    bins: int = 30
    transform: str = "identity"
    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS: raise ValueError(f"unsupported plot layer kind {self.kind!r}")
        if not isinstance(self.y, ScientificResult): raise TypeError("LayerSpec.y must be a ScientificResult")
        if self.x is not None and not isinstance(self.x, ScientificResult): raise TypeError("LayerSpec.x must be a ScientificResult when supplied")
        if self.transform not in {"identity", "ecdf", "hexbin"}: raise ValueError("transform must be identity, ecdf, or hexbin")
        if self.kind in {"ecdf", "hexbin"} and self.transform == "identity": object.__setattr__(self, "transform", self.kind)
    def reference(self) -> dict[str, Any]:
        def ref(r):
            if r is None: return None
            return {"quantity":r.quantity.canonical_name,"provenance_ref":r.provenance_ref,"method_id":r.method_id}
        return {"kind":self.kind,"x":ref(self.x),"y":ref(self.y),"label":self.label,"transform":self.transform,"alpha":self.alpha,"marker":self.marker,"linewidth":self.linewidth,"bins":self.bins}

@dataclass(frozen=True, slots=True)
class InsetSpec:
    bounds: tuple[float,float,float,float]
    layers: tuple[LayerSpec,...]
    title: str | None = None
    xlim: tuple[float,float] | None = None
    ylim: tuple[float,float] | None = None
    def __post_init__(self) -> None:
        if len(self.bounds)!=4 or any(not math.isfinite(float(x)) for x in self.bounds): raise ValueError("inset bounds must be four finite axes-fraction values")
        x,y,w,h=self.bounds
        if w<=0 or h<=0 or x<0 or y<0 or x+w>1 or y+h>1: raise ValueError("inset bounds must lie inside parent axes")

@dataclass(frozen=True, slots=True)
class PanelSpec:
    panel_id: str
    layers: tuple[LayerSpec,...]
    title: str | None = None
    xlabel: str | None = None
    ylabel: str | None = None
    xscale: str = "linear"
    yscale: str = "linear"
    xlim: tuple[float,float] | None = None
    ylim: tuple[float,float] | None = None
    insets: tuple[InsetSpec,...] = ()
    def __post_init__(self) -> None:
        if not self.panel_id.strip(): raise ValueError("panel_id must be non-empty")
        if not self.layers: raise ValueError("every panel must contain at least one layer")
        if self.xscale not in {"linear","log"} or self.yscale not in {"linear","log"}: raise ValueError("panel scales must be linear or log")

@dataclass(frozen=True, slots=True)
class FigureSpec:
    panels: tuple[PanelSpec,...]
    ncols: int = 1
    width: float = 7.0
    height_per_row: float = 3.2
    title: str | None = None
    legend: LegendPolicy = field(default_factory=LegendPolicy)
    dpi: int = 160
    def __post_init__(self) -> None:
        if not self.panels: raise ValueError("figure requires at least one panel")
        if self.ncols<1 or self.ncols>len(self.panels): raise ValueError("ncols must lie between 1 and number of panels")
        ids=[p.panel_id for p in self.panels]
        if len(ids)!=len(set(ids)): raise ValueError("panel_id values must be unique")
        if self.width<=0 or self.height_per_row<=0 or self.dpi<=0: raise ValueError("figure dimensions and dpi must be positive")
    def to_dict(self) -> dict[str,Any]:
        return {"kind":"vascuquest.figure_spec","schema_version":"1","ncols":self.ncols,"width":self.width,"height_per_row":self.height_per_row,"title":self.title,"dpi":self.dpi,"legend":{k:getattr(self.legend,k) for k in self.legend.__dataclass_fields__},"panels":[{"panel_id":p.panel_id,"title":p.title,"xlabel":p.xlabel,"ylabel":p.ylabel,"xscale":p.xscale,"yscale":p.yscale,"xlim":p.xlim,"ylim":p.ylim,"layers":[l.reference() for l in p.layers],"insets":[{"bounds":i.bounds,"title":i.title,"xlim":i.xlim,"ylim":i.ylim,"layers":[l.reference() for l in i.layers]} for i in p.insets]} for p in self.panels]}

def _coordinate_for(result: ScientificResult) -> np.ndarray:
    values=np.asarray(result.values)
    if isinstance(result,Waveform): return np.asarray(result.time_coordinate.values,dtype=float)
    if result.dimensions:
        dimension=result.dimensions[0]
        for coordinate in result.coordinates:
            if coordinate.name==dimension:
                x=np.asarray(coordinate.values)
                if x.ndim==1 and values.ndim>=1 and x.size==values.shape[0]: return x
    if values.ndim==0: return np.asarray([0.0])
    return np.arange(values.shape[0],dtype=float)

def _xy(layer: LayerSpec) -> tuple[np.ndarray,np.ndarray]:
    y=np.asarray(layer.y.values)
    if y.ndim==0: y=y.reshape(1)
    x=_coordinate_for(layer.y) if layer.x is None else np.asarray(layer.x.values)
    if x.ndim==0: x=x.reshape(1)
    if layer.kind!="heatmap" and (x.ndim!=1 or y.ndim!=1 or x.size!=y.size): raise AdmissibilityError("line/scatter/step/hexbin layers require aligned one-dimensional x and y values")
    return x,y

def _render_layer(ax,layer:LayerSpec):
    kwargs={}
    if layer.alpha is not None: kwargs["alpha"]=layer.alpha
    if layer.linewidth is not None: kwargs["linewidth"]=layer.linewidth
    if layer.marker is not None: kwargs["marker"]=layer.marker
    label=layer.label or layer.y.quantity.label
    if layer.kind=="hist":
        ax.hist(np.asarray(layer.y.values,dtype=float).reshape(-1),bins=layer.bins,label=label,alpha=layer.alpha); return
    if layer.kind=="heatmap":
        data=np.asarray(layer.y.values,dtype=float)
        if data.ndim!=2: raise AdmissibilityError("heatmap layers require a two-dimensional result")
        image=ax.imshow(data,aspect="auto",origin="lower",rasterized=data.size>10000); image.set_label(label); return
    x,y=_xy(layer)
    if layer.transform=="ecdf" or layer.kind=="ecdf":
        ys=np.sort(np.asarray(y,dtype=float)); p=np.arange(1,ys.size+1)/ys.size; ax.step(ys,p,where="post",label=label,**kwargs); return
    if layer.transform=="hexbin" or layer.kind=="hexbin":
        if layer.x is None: raise AdmissibilityError("hexbin requires explicit x and y results")
        ax.hexbin(np.asarray(x,dtype=float),np.asarray(y,dtype=float),gridsize=max(10,min(60,int(math.sqrt(x.size)))),mincnt=1); return
    kwargs["rasterized"]=bool(y.size>2000 and layer.kind=="scatter")
    if layer.kind=="line": ax.plot(x,y,label=label,**kwargs)
    elif layer.kind=="step": ax.step(x,y,where="mid",label=label,**kwargs)
    elif layer.kind=="scatter": ax.scatter(x,y,label=label,**kwargs)
    else: raise ValueError(f"unhandled layer kind {layer.kind!r}")

def _panel(ax,panel:PanelSpec):
    for layer in panel.layers: _render_layer(ax,layer)
    ax.set_xscale(panel.xscale); ax.set_yscale(panel.yscale)
    if panel.title: ax.set_title(panel.title)
    if panel.xlabel: ax.set_xlabel(panel.xlabel)
    if panel.ylabel: ax.set_ylabel(panel.ylabel)
    if panel.xlim: ax.set_xlim(*panel.xlim)
    if panel.ylim: ax.set_ylim(*panel.ylim)
    for inset in panel.insets:
        child=ax.inset_axes(inset.bounds)
        for layer in inset.layers: _render_layer(child,layer)
        if inset.title: child.set_title(inset.title,fontsize="small")
        if inset.xlim: child.set_xlim(*inset.xlim)
        if inset.ylim: child.set_ylim(*inset.ylim)

def _all_axes(fig):
    axes=[]
    def visit(ax):
        axes.append(ax)
        for child in getattr(ax,"child_axes",()): visit(child)
    for ax in fig.axes: visit(ax)
    return axes

def _deduplicated_legend(fig):
    handles=[]; labels=[]; seen=set()
    for ax in _all_axes(fig):
        h,l=ax.get_legend_handles_labels()
        for handle,label in zip(h,l):
            if label and not label.startswith("_") and label not in seen:
                seen.add(label); handles.append(handle); labels.append(label)
    return handles,labels

def _overlaps_axes(fig,legend,renderer)->bool:
    lb=legend.get_window_extent(renderer).expanded(1.01,1.03)
    for ax in _all_axes(fig):
        try: tb=ax.get_tightbbox(renderer)
        except Exception: tb=ax.get_window_extent(renderer)
        if tb is not None and lb.overlaps(tb): return True
    return False

def _outside_legend(fig,policy:LegendPolicy):
    handles,labels=_deduplicated_legend(fig)
    if not handles: return None
    fig.canvas.draw(); probe=fig.legend(handles,labels,loc="center",frameon=False); fig.canvas.draw(); renderer=fig.canvas.get_renderer(); fig_box=fig.get_window_extent(renderer); legend_box=probe.get_window_extent(renderer); legend_w=legend_box.width/fig_box.width; legend_h=legend_box.height/fig_box.height; probe.remove()
    mode=policy.mode
    if mode=="auto": mode="bottom" if (len(labels)>policy.max_entries_right or legend_h>0.72 or legend_w>policy.max_right_fraction) else "right"
    pad=policy.min_pad_fraction; legend=None
    if mode=="right":
        reserve=min(policy.max_right_fraction,legend_w+2.0*pad); reserve=max(reserve,legend_w+pad)
        for _ in range(6):
            if legend is not None: legend.remove()
            right_edge=max(0.52,1.0-reserve); fig.subplots_adjust(right=right_edge); legend=fig.legend(handles,labels,loc="center left",bbox_to_anchor=(right_edge+pad,0.5),borderaxespad=0.0,frameon=False); fig.canvas.draw(); renderer=fig.canvas.get_renderer()
            if not _overlaps_axes(fig,legend,renderer): return legend
            pad=min(policy.max_pad_fraction,pad+0.005); reserve=min(policy.max_right_fraction,legend_w+2.0*pad)
        return legend
    ncol=max(1,math.ceil(len(labels)/policy.max_entries_per_column_bottom))
    for _ in range(6):
        if legend is not None: legend.remove()
        reserved=min(0.34,legend_h+2.0*pad); fig.subplots_adjust(bottom=reserved); legend=fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(0.5,pad),ncol=ncol,borderaxespad=0.0,frameon=False); fig.canvas.draw(); renderer=fig.canvas.get_renderer()
        if not _overlaps_axes(fig,legend,renderer): return legend
        pad=min(policy.max_pad_fraction,pad+0.005)
    return legend

def render(spec:FigureSpec,destination:str|Path|None=None):
    matplotlib=require_optional_dependency("matplotlib","plot"); matplotlib.use("Agg",force=True); plt=require_optional_dependency("matplotlib.pyplot","plot"); rows=math.ceil(len(spec.panels)/spec.ncols); fig,axes=plt.subplots(rows,spec.ncols,figsize=(spec.width,spec.height_per_row*rows),dpi=spec.dpi,squeeze=False); flat=list(axes.flat)
    for ax,panel in zip(flat,spec.panels): _panel(ax,panel)
    for ax in flat[len(spec.panels):]: ax.remove()
    if spec.title: fig.suptitle(spec.title)
    fig.subplots_adjust(wspace=0.32,hspace=0.38); _outside_legend(fig,spec.legend)
    if destination is not None:
        path=Path(destination)
        if path.suffix.lower() not in {".pdf",".svg",".png"}: raise ValueError("figure destination must end in .pdf, .svg, or .png")
        path.parent.mkdir(parents=True,exist_ok=True); fig.savefig(path,dpi=spec.dpi,bbox_inches="tight")
    return fig

def write_spec(spec:FigureSpec,destination:str|Path)->Path:
    path=Path(destination); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(spec.to_dict(),sort_keys=True,indent=2)+"\n",encoding="utf-8"); return path

__all__=["FigureSpec","InsetSpec","LayerSpec","LegendPolicy","PanelSpec","render","write_spec"]
