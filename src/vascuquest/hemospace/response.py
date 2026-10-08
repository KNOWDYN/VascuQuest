"""Zero-recompute healthy-to-disease HEMOSPACE response records."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,math
from pathlib import Path
from vascuquest.disease import inspect_parameterized_cohort_bundle
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.result import Waveform
from vascuquest.errors import CapabilityError,IntegrityError,SelectionError
from vascuquest.exporters.json_exporter import load_result_json
from .derivations import site_derivations,wave_summary
from .model import KnowledgeItem

def _sha256(path:Path)->str:
    d=hashlib.sha256()
    with path.open("rb") as h:
        for block in iter(lambda:h.read(1024*1024),b""):d.update(block)
    return d.hexdigest()

@dataclass(frozen=True,slots=True)
class ResponseItem:
    canonical_id:str; label:str; section:str; location:str|None; unit:str|None; baseline_value:float; disease_value:float; absolute_change:float; relative_change_percent:float|None; evidence:str="MODELLED"
    def to_dict(self)->dict[str,object]:return {"canonical_id":self.canonical_id,"label":self.label,"section":self.section,"location":self.location,"unit":self.unit,"baseline_value":self.baseline_value,"disease_value":self.disease_value,"absolute_change":self.absolute_change,"relative_change_percent":self.relative_change_percent,"evidence":self.evidence}

@dataclass(frozen=True,slots=True)
class DiseaseResponseRecord:
    subject_id:str; parent_dataset_identifier:str; cohort_run_id:str; subject_disease_run_id:str; condition:str; severity_parameter:str; severity_value:float; disease_parameters:dict[str,object]; items:tuple[ResponseItem,...]; warnings:tuple[str,...]
    def to_dict(self)->dict[str,object]:return {"kind":"vascuquest.hemospace.disease_response_record","schema_version":"hemospace-1","subject_id":self.subject_id,"parent_dataset_identifier":self.parent_dataset_identifier,"cohort_run_id":self.cohort_run_id,"subject_disease_run_id":self.subject_disease_run_id,"condition":self.condition,"severity_parameter":self.severity_parameter,"severity_value":self.severity_value,"disease_parameters":dict(self.disease_parameters),"response_items":[x.to_dict() for x in self.items],"warnings":list(self.warnings),"interpretation":"paired_counterfactual_model_response_not_clinical_treatment_effect"}

def _verify_subject_bundle(root:Path,manifest:dict[str,object],subject_id:str)->dict[str,object]:
    if subject_id not in tuple(str(v) for v in manifest.get("completed_subject_ids",[])):raise SelectionError(f"subject {subject_id!r} is not complete in parameterized disease bundle")
    expected=dict(manifest.get("subject_manifests",{})).get(subject_id)
    if not isinstance(expected,str):raise IntegrityError(f"bundle has no subject-manifest hash for {subject_id!r}")
    sr=root/"subjects"/subject_id; mp=sr/"subject_manifest.json"
    if not mp.exists() or _sha256(mp)!=expected:raise IntegrityError(f"disease subject manifest checksum mismatch for {subject_id!r}")
    try:sm=json.loads(mp.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise IntegrityError(f"invalid disease subject manifest for {subject_id!r}") from exc
    if sm.get("canonical_subject_id")!=subject_id:raise IntegrityError("disease subject manifest changed the canonical PWDB subject ID")
    if not (sr/"COMPLETE").exists():raise IntegrityError(f"disease subject bundle {subject_id!r} lacks COMPLETE marker")
    for raw in sm.get("files",[]):
        item=dict(raw)
        if item.get("kind")!="scientific_result":continue
        p=sr/str(item.get("path"))
        if not p.exists() or p.stat().st_size!=int(item.get("bytes",-1)) or _sha256(p)!=str(item.get("sha256")):raise IntegrityError(f"disease result integrity failure: {p}")
    return sm

def _modelled_items(subject_root:Path,sm:dict[str,object])->list[KnowledgeItem]:
    waves:dict[str,dict[str,Waveform]]={}; flows:dict[str,Waveform]={}; items=[]
    for raw in sm.get("files",[]):
        e=dict(raw)
        if e.get("kind")!="scientific_result":continue
        result=load_result_json(subject_root/str(e["path"]))
        if not isinstance(result,Waveform) or not isinstance(result.location,MeasurementSite) or not result.coordinates:continue
        site=result.location.canonical_site_id; q=result.quantity.canonical_name; summary=wave_summary(result.values,result.coordinates[0].values,result.missing_mask,result.padding_mask)
        if q=="flow_rate":summary["cycle_volume_m3"]=summary.pop("integral")
        items.append(KnowledgeItem(f"waveform_summary_{site.lower()}_{q}",f"{site} {q.replace('_',' ')} waveform summary","disease_waveform",summary,result.quantity.canonical_unit,"MODELLED",location=site,method="summary of persisted VascuQuest Virtual Disease waveform; no solver rerun",notes=("Counterfactual model output, not a clinical observation.",)))
        if q=="flow_rate":flows[site]=result
        elif q in {"pressure","flow_velocity","luminal_area"}:waves.setdefault(site,{})[q]=result
    for site,group in waves.items():
        try:derived=site_derivations(site,group,flows.get(site))
        except ValueError:continue
        for x in derived:items.append(KnowledgeItem(x.canonical_id,x.label,x.section,x.value,x.unit,"MODELLED",location=x.location,method=f"{x.method}; evaluated on persisted Virtual Disease output",assumptions=x.assumptions,notes=x.notes+("Counterfactual model output, not a clinical observation.",)))
    return items

def _numeric_pairs(baseline_items:tuple[KnowledgeItem,...],disease_items:list[KnowledgeItem])->tuple[ResponseItem,...]:
    baseline={x.canonical_id:x for x in baseline_items}; out=[]
    def add(cid,label,section,location,unit,b,d):
        change=d-b; rel=None if abs(b)<=1e-30 else 100.0*change/b; out.append(ResponseItem(cid,label,section,location,unit,b,d,change,rel))
    for disease in disease_items:
        healthy=baseline.get(disease.canonical_id)
        if healthy is None:continue
        if isinstance(healthy.value,(int,float)) and isinstance(disease.value,(int,float)):
            b=float(healthy.value);d=float(disease.value)
            if math.isfinite(b) and math.isfinite(d):add(disease.canonical_id,disease.label,disease.section,disease.location,disease.unit,b,d)
        elif isinstance(healthy.value,dict) and isinstance(disease.value,dict):
            for key in sorted(set(healthy.value)&set(disease.value)):
                bv=healthy.value[key];dv=disease.value[key]
                if not isinstance(bv,(int,float)) or not isinstance(dv,(int,float)):continue
                b=float(bv);d=float(dv)
                if not math.isfinite(b) or not math.isfinite(d):continue
                unit="s" if key.startswith("time_to_") or key.endswith("_s") else "m^3" if key=="cycle_volume_m3" else None if key=="integral" else disease.unit
                add(f"{disease.canonical_id}.{key}",f"{disease.label}: {key}",disease.section,disease.location,unit,b,d)
    return tuple(out)

def response_from_bundle(session:object,bundle:str|Path,subject_id:str)->DiseaseResponseRecord:
    root=Path(bundle).expanduser();manifest=inspect_parameterized_cohort_bundle(root)
    if manifest.get("format")!="vascuquest-parameterized-disease-cohort-bundle":raise IntegrityError("not a VascuQuest parameterized disease cohort bundle")
    sm=_verify_subject_bundle(root,manifest,subject_id);baseline=session.record(subject_id,depth="comprehensive");modelled=_modelled_items(root/"subjects"/subject_id,sm);items=_numeric_pairs(baseline.items,modelled)
    if not items:raise CapabilityError("no aligned healthy/modelled HEMOSPACE response endpoints were available; the healthy common-site waveform artifact may be unavailable")
    parent=dict(manifest.get("parent_dataset_identity",{}))
    return DiseaseResponseRecord(subject_id,str(parent.get("persistent_identifier",session.identity.persistent_identifier)),str(sm.get("cohort_run_id",manifest.get("cohort_run_id",""))),str(sm.get("subject_disease_run_id","")),str(sm.get("condition",manifest.get("condition",""))),str(sm.get("severity_parameter",manifest.get("severity_parameter",""))),float(sm.get("severity_value")),dict(sm.get("disease_parameters",{})),items,("The disease state is MODELLED and not a clinical observation.","Absolute/relative changes are paired counterfactual model responses, not clinical treatment effects.","No disease solver was executed by HEMOSPACE; persisted verified bundle results were consumed."))

__all__=["DiseaseResponseRecord","ResponseItem","response_from_bundle"]
