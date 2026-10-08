"""Lazy optional access to PWDB path-resolved MATLAB v7.3 artifacts.

The reader never loads an entire multi-gigabyte path artifact into memory. It
supports the canonical HDF5-backed MATLAB v7.3 path exports and refuses a
whole-file legacy-MAT fallback.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
from vascuquest.errors import CapabilityError,IntegrityError,SelectionError

PATH_ARTIFACTS={
"aorta_brain":{"P":"path_aorta_brain","U":"path_aorta_brain","A":"path_aorta_brain"},
"aorta_finger":{"P":"path_aorta_finger","U":"path_aorta_finger","A":"path_aorta_finger"},
"aorta_foot":{"P":"path_aorta_foot_p","U":"path_aorta_foot_u","A":"path_aorta_foot_a"},
"aorta_r_subclavian":{"P":"path_aorta_rsubclavian","U":"path_aorta_rsubclavian","A":"path_aorta_rsubclavian"},
}

def _require_h5py()->Any:
    try:import h5py # type: ignore
    except ImportError as exc:raise CapabilityError("PWDB path-resolved HEMOSPACE access requires optional dependency h5py; install VascuQuest with the 'path' extra") from exc
    return h5py

def _subject_index(subject_id:str)->int:
    try:v=int(subject_id,10)
    except (TypeError,ValueError) as exc:raise SelectionError(f"invalid PWDB subject identifier {subject_id!r}") from exc
    if v<1 or str(v)!=subject_id:raise SelectionError(f"invalid PWDB subject identifier {subject_id!r}")
    return v-1

def _flatten(a:np.ndarray)->np.ndarray:return np.asarray(a).reshape(-1,order="F")
def _deref_subject(handle:Any,group:Any,field:str,index:int)->Any:
    if field not in group:raise IntegrityError(f"path-resolved MAT structure lacks field {field!r}")
    node=group[field];raw=np.asarray(node[()]);ref_type=_require_h5py().check_dtype(ref=raw.dtype)
    if ref_type is None:
        if raw.ndim>=1 and raw.shape[0]>index:return np.asarray(raw[index])
        if raw.ndim>=2 and raw.shape[-1]>index:return np.asarray(raw[...,index])
        raise IntegrityError(f"path-resolved MAT field {field!r} has no subject reference axis")
    refs=_flatten(raw)
    if index>=refs.size:raise SelectionError(f"subject index {index+1} exceeds path-resolved MAT population")
    ref=refs[index]
    if not ref:raise IntegrityError(f"path-resolved MAT field {field!r} has an empty subject reference")
    return handle[ref]
def _numeric(obj:Any)->np.ndarray:
    raw=np.asarray(obj[()])
    if _require_h5py().check_dtype(ref=raw.dtype) is not None:raise IntegrityError("expected numeric MATLAB dataset, found cell/reference array")
    a=np.asarray(raw,dtype=float).reshape(-1,order="F")
    if not np.all(np.isfinite(a)):raise IntegrityError("path-resolved numeric source contains non-finite values")
    return a
def _cells(handle:Any,obj:Any)->list[Any]:
    raw=np.asarray(obj[()])
    if _require_h5py().check_dtype(ref=raw.dtype) is None:raise IntegrityError("expected MATLAB cell references")
    result=[]
    for ref in _flatten(raw):
        if not ref:raise IntegrityError("path-resolved MATLAB cell contains empty reference")
        result.append(handle[ref])
    return result
def _char(obj:Any)->str:
    raw=np.asarray(obj[()]).reshape(-1,order="F")
    if raw.dtype.kind in {"u","i"}:return "".join(chr(int(c)) for c in raw if int(c)!=0)
    if raw.dtype.kind in {"S","U"}:return "".join(str(v) for v in raw).strip()
    raise IntegrityError("unsupported MATLAB character representation")

def _read_one(path:Path,path_name:str,subject_id:str,*,signals:tuple[str,...],include_metadata:bool)->tuple[dict[str,object],dict[str,list[np.ndarray]]]:
    h5py=_require_h5py()
    if not h5py.is_hdf5(path):raise CapabilityError(f"{path.name} is not MATLAB v7.3/HDF5; HEMOSPACE refuses a whole-file legacy-MAT load for a large canonical path artifact")
    index=_subject_index(subject_id);metadata={};signal_data={}
    try:
        with h5py.File(path,"r") as handle:
            try:group=handle["data"]["path_waves"][path_name]
            except Exception as exc:raise IntegrityError(f"canonical path artifact {path.name} lacks data/path_waves/{path_name}") from exc
            if include_metadata:
                dist=_numeric(_deref_subject(handle,group,"dist",index));adist=_numeric(_deref_subject(handle,group,"artery_dist",index));onset=_numeric(_deref_subject(handle,group,"onset_time",index));arteries=tuple(_char(x) for x in _cells(handle,_deref_subject(handle,group,"artery",index)));segments=tuple(int(round(float(_numeric(x)[0]))) for x in _cells(handle,_deref_subject(handle,group,"segment_no",index)))
                if len({len(dist),len(adist),len(onset),len(arteries),len(segments)})!=1:raise IntegrityError("path metadata arrays do not have identical point counts")
                metadata={"distance_m":dist,"artery_distance_m":adist,"onset_time_s":onset,"artery":arteries,"segment_no":segments}
            for signal in signals:
                waves=[_numeric(x) for x in _cells(handle,_deref_subject(handle,group,signal,index))]
                if metadata and len(waves)!=len(metadata["distance_m"]):raise IntegrityError(f"path signal {signal!r} point count does not match metadata")
                signal_data[signal]=waves
    except OSError as exc:raise IntegrityError(f"unable to read path-resolved artifact {path}") from exc
    return metadata,signal_data

def _summary(w:np.ndarray)->dict[str,float]:return {"min":float(np.min(w)),"max":float(np.max(w)),"mean":float(np.mean(w)),"amplitude":float(np.max(w)-np.min(w))}

@dataclass(frozen=True,slots=True)
class PathCardiovascularProfile:
    subject_id:str; path_name:str; source_artifacts:tuple[str,...]; distance_m:tuple[float,...]; artery:tuple[str,...]; segment_no:tuple[int,...]; artery_distance_m:tuple[float,...]; onset_time_s:tuple[float,...]; signal_summaries:dict[str,tuple[dict[str,float],...]]; reconstructed_flow_summaries:tuple[dict[str,float],...]|None; apparent_path_pwv_m_per_s:float|None; onset_distance_r2:float|None; pressure_pulse_amplification_terminal_to_root:float|None
    def to_dict(self)->dict[str,object]:return {"kind":"vascuquest.hemospace.path_profile","schema_version":"hemospace-1","subject_id":self.subject_id,"path_name":self.path_name,"reader_qualification":"IMPLEMENTED_REQUIRES_LOCAL_REAL_SOURCE_QUALIFICATION","evidence":{"path_source":"SOURCE","flow_rate":"RECONSTRUCTED","path_pwv_and_amplification":"DERIVED"},"source_artifacts":list(self.source_artifacts),"distance_m":list(self.distance_m),"artery":list(self.artery),"segment_no":list(self.segment_no),"artery_distance_m":list(self.artery_distance_m),"onset_time_s":list(self.onset_time_s),"signal_summaries":{k:list(v) for k,v in self.signal_summaries.items()},"reconstructed_flow_summaries":None if self.reconstructed_flow_summaries is None else list(self.reconstructed_flow_summaries),"apparent_path_pwv_m_per_s":self.apparent_path_pwv_m_per_s,"onset_distance_r2":self.onset_distance_r2,"pressure_pulse_amplification_terminal_to_root":self.pressure_pulse_amplification_terminal_to_root,"assumptions":["Path waves are canonical PWDB source signals exported along predefined arterial paths.","Apparent path PWV is obtained from a linear distance-versus-onset-time relation and is a path-level descriptor, not a clinical tonometry measurement.","Q is reconstructed pointwise as U*A where both source signals are available."]}

def path_profile(resolver:object,subject_id:str,path_name:str)->PathCardiovascularProfile:
    if path_name not in PATH_ARTIFACTS:raise SelectionError(f"unknown PWDB path {path_name!r}; choose from {sorted(PATH_ARTIFACTS)!r}")
    if not callable(resolver):raise TypeError("resolver must be callable")
    grouped={}
    for signal,artifact in PATH_ARTIFACTS[path_name].items():grouped.setdefault(artifact,[]).append(signal)
    artifacts=[];metadata=None;signals={}
    for artifact,source_signals in grouped.items():
        meta,data=_read_one(resolver(artifact),path_name,subject_id,signals=tuple(source_signals),include_metadata=metadata is None);artifacts.append(artifact)
        if metadata is None:metadata=meta
        signals.update(data)
    assert metadata is not None
    distance=np.asarray(metadata["distance_m"],dtype=float);onset=np.asarray(metadata["onset_time_s"],dtype=float);summaries={k:tuple(_summary(w) for w in v) for k,v in signals.items()};qs=None
    if "U" in signals and "A" in signals:
        if len(signals["U"])!=len(signals["A"]):raise IntegrityError("path U and A signals have different point counts")
        qs=tuple(_summary(u*a) for u,a in zip(signals["U"],signals["A"],strict=True))
    pwv=r2=None;valid=np.isfinite(distance)&np.isfinite(onset)
    if np.count_nonzero(valid)>=3:
        d=distance[valid];t=onset[valid]
        if np.ptp(t)>1e-12 and np.ptp(d)>0:
            slope,intercept=np.polyfit(t,d,1);pred=slope*t+intercept;ssr=float(np.sum((d-pred)**2));sst=float(np.sum((d-np.mean(d))**2));pwv=float(slope) if slope>0 else None;r2=1.0-ssr/sst if sst>0 else None
    amp=None
    if "P" in summaries and len(summaries["P"])>=2:
        root=summaries["P"][0]["amplitude"];amp=summaries["P"][-1]["amplitude"]/root if root>0 else None
    return PathCardiovascularProfile(subject_id,path_name,tuple(artifacts),tuple(map(float,distance)),tuple(map(str,metadata["artery"])),tuple(map(int,metadata["segment_no"])),tuple(map(float,metadata["artery_distance_m"])),tuple(map(float,onset)),summaries,qs,pwv,r2,amp)

__all__=["PATH_ARTIFACTS","PathCardiovascularProfile","path_profile"]
