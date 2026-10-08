"""Phenotype-driven HEMOSPACE cohort and endovascular study planning."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, re
import numpy as np
from vascuquest.errors import SelectionError
from .catalogue import SCALAR_SOURCE_ARTIFACTS, semantics_for
from .source_table import HemospaceSubjectCSVTable

_CRITERION_RE=re.compile(r"^(?P<name>[a-zA-Z0-9_]+)\s*(?P<op><=|>=|==|!=|<|>)\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$")

@dataclass(frozen=True,slots=True)
class Criterion:
    canonical_id:str; operator:str; value:float
    @classmethod
    def parse(cls,expression:str)->"Criterion":
        if not isinstance(expression,str): raise TypeError("criterion expression must be a string")
        m=_CRITERION_RE.match(expression.strip())
        if m is None: raise SelectionError("criterion must have form canonical_id>=number, canonical_id==number, etc.")
        return cls(m.group("name"),m.group("op"),float(m.group("value")))
    def matches(self,actual:float)->bool:
        return {"<":actual<self.value,"<=":actual<=self.value,">":actual>self.value,">=":actual>=self.value,"==":actual==self.value,"!=":actual!=self.value}[self.operator]
    def to_dict(self)->dict[str,object]: return {"canonical_id":self.canonical_id,"operator":self.operator,"value":self.value}

@dataclass(frozen=True,slots=True)
class TrialProfile:
    profile_id:str; title:str; research_question:str; disease_conditions:tuple[str,...]; recommended_covariates:tuple[str,...]; effect_modifiers:tuple[str,...]; source_endpoints:tuple[str,...]; modelled_response_endpoints:tuple[str,...]; forbidden_claims:tuple[str,...]
    def to_dict(self)->dict[str,object]: return {"profile_id":self.profile_id,"title":self.title,"research_question":self.research_question,"disease_conditions":list(self.disease_conditions),"recommended_covariates":list(self.recommended_covariates),"effect_modifiers":list(self.effect_modifiers),"source_endpoints":list(self.source_endpoints),"modelled_response_endpoints":list(self.modelled_response_endpoints),"forbidden_claims":list(self.forbidden_claims)}

TRIAL_PROFILES={
"carotid-stenosis":TrialProfile("carotid-stenosis","Carotid stenosis physiological effect modification","Which baseline cardiovascular phenotypes magnify or attenuate the haemodynamic response to an identical carotid stenosis?",("carotid_stenosis",),("simulation_age","haemodynamic_co","haemodynamic_mbp_a","haemodynamic_svr","haemodynamic_pwv_cf","haemodynamic_dia_car"),("arterial_stiffness_variation","large_artery_diameter_variation","stroke_volume_variation","mean_blood_pressure_variation","heart_rate_variation"),("pulse_wave_carotid_sbp_v","pulse_wave_carotid_pp","pulse_wave_carotid_qmean_v","pulse_wave_carotid_umax_v"),("Carotid pressure/flow/velocity change","distal pressure change","pulse-pressure change","hydraulic-energy change"),("stroke risk","plaque vulnerability","treatment efficacy","patient-specific prognosis")),
"iliac-stenosis":TrialProfile("iliac-stenosis","Iliac stenosis physiological effect modification","Which systemic and lower-limb haemodynamic phenotypes make an identical iliac stenosis most consequential?",("iliac_stenosis",),("simulation_age","haemodynamic_co","haemodynamic_svr","haemodynamic_mbp_drop_ankle","haemodynamic_pwv_fa"),("large_artery_diameter_variation","arterial_stiffness_variation","stroke_volume_variation","mean_blood_pressure_variation","peripheral_vascular_compliance_variation"),("pulse_wave_commoniliac_qmean_v","pulse_wave_femoral_qmean_v","pulse_wave_anttibial_qmean_v","pulse_wave_femoral_pp"),("Iliac/femoral flow change","distal pressure change","reverse-flow change","hydraulic-energy change"),("limb ischemia diagnosis","clinical revascularization threshold","device efficacy","patient-specific prognosis")),
"aaa":TrialProfile("aaa","Fusiform abdominal aortic aneurysm systemic phenotype","How does baseline systemic physiology modify the one-dimensional haemodynamic response to an identical idealized fusiform AAA?",("fusiform_abdominal_aortic_aneurysm",),("simulation_age","haemodynamic_pwv_a","haemodynamic_pp_a","haemodynamic_co","haemodynamic_dia_abd_a"),("arterial_stiffness_variation","large_artery_diameter_variation","stroke_volume_variation","mean_blood_pressure_variation","proximal_aortic_length_variation"),("pulse_wave_abdaorta_sbp_v","pulse_wave_abdaorta_pp","pulse_wave_abdaorta_qmean_v","pulse_wave_abdaorta_amax_v"),("abdominal-aortic pressure change","flow change","area-pulsatility change","hydraulic-energy change"),("rupture risk","intraluminal thrombus","wall shear stress","three-dimensional sac recirculation","clinical prognosis")),
"large-artery-stiffening":TrialProfile("large-artery-stiffening","Large-artery stiffening response phenotype","Which baseline physiological factors determine system-wide haemodynamic sensitivity to an imposed conduit-stiffness increase?",("large_artery_stiffening",),("simulation_age","haemodynamic_pwv_a","haemodynamic_pwv_cf","haemodynamic_pp_amp","haemodynamic_aix","haemodynamic_co"),("arterial_stiffness_variation","mean_blood_pressure_variation","large_artery_diameter_variation","stroke_volume_variation","peripheral_vascular_compliance_variation"),("haemodynamic_pp_a","haemodynamic_pp_b","haemodynamic_pp_amp","haemodynamic_aix","haemodynamic_tr"),("central/peripheral pulse-pressure change","wave-timing change","flow-pulsatility change","hydraulic-energy change"),("clinical arterial-age diagnosis","future event risk","patient-specific treatment recommendation")),
}

@dataclass(frozen=True,slots=True)
class HemospaceCohort:
    dataset_family:str; dataset_record_id:str; dataset_identifier:str; canonical_subject_ids:tuple[str,...]; criteria:tuple[Criterion,...]; profile_id:str|None; selection_id:str
    @property
    def count(self)->int:return len(self.canonical_subject_ids)
    def to_dict(self)->dict[str,object]:return {"kind":"vascuquest.hemospace.cohort","schema_version":"hemospace-1","selection_id":self.selection_id,"dataset":{"family":self.dataset_family,"record_id":self.dataset_record_id,"persistent_identifier":self.dataset_identifier},"profile_id":self.profile_id,"criteria":[x.to_dict() for x in self.criteria],"count":self.count,"canonical_subject_ids":list(self.canonical_subject_ids),"population_interpretation":"designed_virtual_population_not_epidemiological"}

def profile(profile_id:str)->TrialProfile:
    try:return TRIAL_PROFILES[profile_id]
    except KeyError as exc:raise SelectionError(f"unknown HEMOSPACE trial profile {profile_id!r}; choose from {sorted(TRIAL_PROFILES)!r}") from exc

def _source_index(session:object)->tuple[dict[str,tuple[HemospaceSubjectCSVTable,str]],tuple[str,...]]:
    index={}; order=None
    for scope,artifact_id in SCALAR_SOURCE_ARTIFACTS:
        table=HemospaceSubjectCSVTable(session._resolve(artifact_id)); ids=table.subject_ids()
        if order is None: order=ids
        elif ids!=order: raise SelectionError(f"HEMOSPACE source table {scope!r} does not preserve canonical subject ordering")
        for field in table.fieldnames:
            if field in {"Subject Number","SUBJECT NUMBER"}:continue
            cid=semantics_for(scope,field).canonical_id
            if cid not in index:index[cid]=(table,field)
    assert order is not None
    return index,order

def select_cohort(session:object,criteria:tuple[Criterion,...]|list[Criterion]|tuple[str,...]|list[str],*,profile_id:str|None=None)->HemospaceCohort:
    parsed=tuple(x if isinstance(x,Criterion) else Criterion.parse(x) for x in criteria)
    if profile_id is not None: profile(profile_id)
    index,order=_source_index(session); selected=list(order)
    for criterion in parsed:
        if criterion.canonical_id not in index: raise SelectionError(f"unknown scalar HEMOSPACE canonical_id {criterion.canonical_id!r}")
        table,field=index[criterion.canonical_id]; selected=[sid for sid in selected if (c:=table.numeric(sid,field)).value is not None and criterion.matches(float(c.value))]
    identity=session.identity; payload={"dataset":identity.persistent_identifier,"criteria":[x.to_dict() for x in parsed],"profile_id":profile_id,"subject_ids":selected}; selection_id=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return HemospaceCohort(identity.dataset_family,identity.record_id,identity.persistent_identifier,tuple(selected),parsed,profile_id,selection_id)

def describe_cohort(session:object,cohort:HemospaceCohort,*,canonical_ids:tuple[str,...]|None=None)->dict[str,object]:
    if not isinstance(cohort,HemospaceCohort):raise TypeError("cohort must be a HemospaceCohort")
    index,_=_source_index(session)
    requested=list(canonical_ids or ("simulation_age","large_artery_diameter_variation","heart_rate_variation","proximal_aortic_length_variation","lvet_variation","mean_blood_pressure_variation","peripheral_vascular_compliance_variation","arterial_stiffness_variation","reverse_flow_volume_variation","stroke_volume_variation","peak_flow_time_variation"))
    if canonical_ids is None and cohort.profile_id is not None:
        p=profile(cohort.profile_id); requested.extend(p.recommended_covariates); requested.extend(p.effect_modifiers)
    summaries={}
    for cid in dict.fromkeys(requested):
        if cid not in index:continue
        table,field=index[cid]; vals=[float(c.value) for sid in cohort.canonical_subject_ids if (c:=table.numeric(sid,field)).value is not None]
        if not vals:continue
        a=np.asarray(vals); entry={"n":int(a.size),"mean":float(np.mean(a)),"std":float(np.std(a,ddof=1)) if a.size>1 else 0.0,"min":float(np.min(a)),"max":float(np.max(a))}; unique=np.unique(a)
        if unique.size<=20:entry["levels"]={format(float(v),".12g"):int(np.count_nonzero(a==v)) for v in unique}
        summaries[cid]=entry
    return {"kind":"vascuquest.hemospace.cohort_description","selection_id":cohort.selection_id,"count":cohort.count,"profile":None if cohort.profile_id is None else profile(cohort.profile_id).to_dict(),"summaries":summaries,"warnings":["PWDB is a designed virtual population; these summaries are not epidemiological prevalence estimates."]}

__all__=["Criterion","HemospaceCohort","TRIAL_PROFILES","TrialProfile","describe_cohort","profile","select_cohort"]
