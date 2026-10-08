"""Qualified deterministic derivations used by HEMOSPACE.

The functions in this module operate only on already available PWDB/VascuQuest
quantities. They do not create unencoded biology or clinical labels.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from .model import KnowledgeItem


def finite_series(values: object, times: object, missing_mask: object | None = None, padding_mask: object | None = None) -> tuple[np.ndarray, np.ndarray]:
    array = np.asarray(values, dtype=float).reshape(-1)
    time = np.asarray(times, dtype=float).reshape(-1)
    if array.shape != time.shape:
        raise ValueError("waveform values and time coordinate must have identical shapes")
    valid = np.isfinite(array) & np.isfinite(time)
    if missing_mask is not None:
        valid &= ~np.asarray(missing_mask, dtype=bool).reshape(-1)
    if padding_mask is not None:
        valid &= ~np.asarray(padding_mask, dtype=bool).reshape(-1)
    if np.count_nonzero(valid) < 2:
        raise ValueError("waveform has fewer than two finite source samples")
    return array[valid], time[valid]


def wave_summary(values: object, times: object, missing_mask: object | None = None, padding_mask: object | None = None) -> dict[str, float]:
    v, t = finite_series(values, times, missing_mask, padding_mask)
    peak_index = int(np.argmax(v)); trough_index = int(np.argmin(v))
    duration = float(t[-1] - t[0]); integral = float(np.trapezoid(v, t)) if duration > 0 else 0.0
    return {"min": float(np.min(v)), "max": float(np.max(v)), "mean": float(np.mean(v)), "amplitude": float(np.max(v)-np.min(v)), "time_to_max_s": float(t[peak_index]-t[0]), "time_to_min_s": float(t[trough_index]-t[0]), "integral": integral}


def _knowledge(canonical_id: str, label: str, section: str, value: object, unit: str | None, *, location: str, method: str, assumptions: tuple[str, ...] = (), notes: tuple[str, ...] = ()) -> KnowledgeItem:
    return KnowledgeItem(canonical_id, label, section, value, unit, "DERIVED", location=location, method=method, assumptions=assumptions, notes=notes)


def _aligned_wave(wave: object) -> tuple[np.ndarray, np.ndarray]:
    coordinates = getattr(wave, "coordinates")
    if not coordinates:
        raise ValueError("waveform has no time coordinate")
    return finite_series(getattr(wave, "values"), coordinates[0].values, getattr(wave, "missing_mask", None), getattr(wave, "padding_mask", None))


def _align_by_time(*series: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
    if not series:
        raise ValueError("at least one series is required")
    reference_t = series[0][1]; arrays: list[np.ndarray] = [series[0][0]]
    for values, times in series[1:]:
        if reference_t.shape != times.shape or not np.allclose(reference_t, times, rtol=0.0, atol=1e-12):
            raise ValueError("source waveforms do not share an identical time grid")
        arrays.append(values)
    return reference_t, arrays


def site_derivations(site_id: str, waves: Mapping[str, object], flow_wave: object | None) -> list[KnowledgeItem]:
    items: list[KnowledgeItem] = []; slug = site_id.lower()
    velocity = waves.get("flow_velocity")
    if velocity is not None:
        u, _ = _aligned_wave(velocity); u_mean=float(np.mean(u)); u_max=float(np.max(u)); u_min=float(np.min(u))
        if abs(u_mean)>1e-15:
            items.append(_knowledge(f"velocity_pulsatility_index_{slug}", f"{site_id} velocity pulsatility index", "flow", (u_max-u_min)/abs(u_mean), "1", location=site_id, method="(U_max - U_min) / abs(U_mean)", notes=("Dimensionless waveform pulsatility descriptor; not a clinical diagnosis.",)))
        if abs(u_max)>1e-15:
            items.append(_knowledge(f"velocity_resistive_index_{slug}", f"{site_id} velocity resistive index", "flow", (u_max-u_min)/u_max, "1", location=site_id, method="(U_max - U_min) / U_max", notes=("Waveform-derived index; interpretation is limited to the represented virtual circulation.",)))
    area=waves.get("luminal_area"); pressure=waves.get("pressure")
    if area is not None:
        a,_=_aligned_wave(area); amin=float(np.min(a)); amax=float(np.max(a))
        if amin>0:
            items.append(_knowledge(f"area_strain_{slug}", f"{site_id} area strain", "arterial_mechanics", (amax-amin)/amin, "1", location=site_id, method="(A_max - A_min) / A_min", assumptions=("Source luminal-area waveform represents the same local cross-section through the cycle.",)))
    if area is not None and pressure is not None:
        p,tp=_aligned_wave(pressure); a,ta=_aligned_wave(area); _,(p,a)=_align_by_time((p,tp),(a,ta)); dp=float(np.max(p)-np.min(p)); da=float(np.max(a)-np.min(a)); amin=float(np.min(a))
        if dp>0:
            items.append(_knowledge(f"area_compliance_{slug}", f"{site_id} local area compliance", "arterial_mechanics", da/dp, "m^2/mmHg", location=site_id, method="(A_max - A_min) / (P_max - P_min)", assumptions=("Pressure and area are contemporaneous source waves at the same PWDB measurement site.",)))
            if amin>0:
                items.append(_knowledge(f"area_distensibility_{slug}", f"{site_id} local area distensibility", "arterial_mechanics", da/(amin*dp), "1/mmHg", location=site_id, method="(A_max - A_min) / (A_min * (P_max - P_min))", assumptions=("Uses diastolic/minimum area as the reference area.",)))
    if flow_wave is not None:
        q,tq=_aligned_wave(flow_wave); qmean=float(np.mean(q)); qmax=float(np.max(q)); qmin=float(np.min(q))
        if abs(qmean)>1e-18:
            items.append(_knowledge(f"flow_pulsatility_index_{slug}", f"{site_id} volumetric-flow pulsatility index", "flow", (qmax-qmin)/abs(qmean), "1", location=site_id, method="(Q_max - Q_min) / abs(Q_mean)"))
        positive=np.maximum(q,0.0); negative=np.minimum(q,0.0); forward=float(np.trapezoid(positive,tq)); reverse=float(-np.trapezoid(negative,tq)); net=float(np.trapezoid(q,tq))
        items.extend([
            _knowledge(f"forward_cycle_volume_{slug}", f"{site_id} forward cycle volume", "flow", forward, "m^3", location=site_id, method="integral(max(Q, 0) dt)"),
            _knowledge(f"reverse_cycle_volume_{slug}", f"{site_id} reverse cycle volume", "flow", reverse, "m^3", location=site_id, method="-integral(min(Q, 0) dt)"),
            _knowledge(f"net_cycle_volume_{slug}", f"{site_id} net cycle volume", "flow", net, "m^3", location=site_id, method="integral(Q dt)"),
        ])
        if forward>0:
            items.append(_knowledge(f"reverse_flow_fraction_{slug}", f"{site_id} reverse-flow fraction", "flow", reverse/forward, "1", location=site_id, method="reverse_cycle_volume / forward_cycle_volume"))
    if pressure is not None and flow_wave is not None:
        p,tp=_aligned_wave(pressure); q,tq=_aligned_wave(flow_wave); time,(p,q)=_align_by_time((p,tp),(q,tq)); p_pa=p*133.32236842105263
        items.extend([
            _knowledge(f"mean_hydraulic_power_{slug}", f"{site_id} mean hydraulic power", "energetic", float(np.mean(p_pa*q)), "W", location=site_id, method="mean(P_Pa * Q_m3_per_s)", notes=("Hydraulic energy transport, not myocardial metabolic power.",)),
            _knowledge(f"hydraulic_energy_per_cycle_{slug}", f"{site_id} hydraulic energy per cycle", "energetic", float(np.trapezoid(p_pa*q,time)), "J", location=site_id, method="integral(P_Pa * Q dt)", notes=("Hydraulic energy crossing the represented section during one simulated cycle.",)),
        ])
        if len(time)>=8:
            dt=np.diff(time)
            if np.all(dt>0) and np.max(dt)-np.min(dt)<=max(1e-12,1e-6*float(np.mean(dt))):
                pf=np.fft.rfft(p_pa-float(np.mean(p_pa))); qf=np.fft.rfft(q-float(np.mean(q))); freq=np.fft.rfftfreq(len(time),d=float(np.mean(dt))); harmonics=[]
                for index in range(1,min(6,len(freq))):
                    if abs(qf[index])<=1e-18: continue
                    z=pf[index]/qf[index]; harmonics.append({"harmonic":float(index),"frequency_hz":float(freq[index]),"magnitude_pa_s_per_m3":float(abs(z)),"phase_deg":float(np.degrees(np.angle(z)))})
                if harmonics:
                    items.append(_knowledge(f"pressure_flow_impedance_harmonics_{slug}", f"{site_id} pressure-flow impedance harmonics", "wave_reflection", harmonics, None, location=site_id, method="FFT(P-mean(P)) / FFT(Q-mean(Q)), harmonics 1..5", assumptions=("Pressure and flow are periodic, contemporaneous, uniformly sampled source/reconstructed waves.","The result is a local frequency-domain pressure-flow relation; it is not a direct clinical impedance measurement.")))
    return items


def scalar_derivation_catalogue() -> tuple[dict[str,str], ...]:
    return (
        {"canonical_id":"cardiac_cycle_duration","method":"60 / heart_rate_bpm","evidence":"DERIVED"},
        {"canonical_id":"cardiac_output_from_hr_sv","method":"HR * SV / 1000","evidence":"RECONSTRUCTED"},
        {"canonical_id":"cardiac_output_reconstruction_discrepancy","method":"100*(CO_HR_SV-CO_source)/CO_source","evidence":"DERIVED"},
        {"canonical_id":"reconstructed_pulse_pressure_*","method":"SBP - DBP","evidence":"RECONSTRUCTED"},
        {"canonical_id":"mean_systemic_hydraulic_power","method":"MBP_Pa * CO_m3_per_s","evidence":"DERIVED"},
        {"canonical_id":"pwdb_physiological_plausibility","method":"reconstruct upstream PWDB plausibility gate from source haemodynamics","evidence":"RECONSTRUCTED"},
    )


def waveform_derivation_catalogue() -> tuple[dict[str,str], ...]:
    return tuple({"canonical_id":cid,"method":method,"evidence":"DERIVED"} for cid,method in (
        ("velocity_pulsatility_index_*","(Umax-Umin)/abs(Umean)"),("velocity_resistive_index_*","(Umax-Umin)/Umax"),("area_strain_*","(Amax-Amin)/Amin"),("area_compliance_*","dA/dP over cycle extrema"),("area_distensibility_*","dA/(Amin*dP)"),("flow_pulsatility_index_*","(Qmax-Qmin)/abs(Qmean)"),("forward_cycle_volume_*","integral(max(Q,0)dt)"),("reverse_cycle_volume_*","-integral(min(Q,0)dt)"),("reverse_flow_fraction_*","reverse/forward cycle volume"),("mean_hydraulic_power_*","mean(P*Q)"),("hydraulic_energy_per_cycle_*","integral(P*Q dt)"),("pressure_flow_impedance_harmonics_*","FFT(P)/FFT(Q), harmonics 1..5"),
    ))

__all__=["finite_series","scalar_derivation_catalogue","site_derivations","wave_summary","waveform_derivation_catalogue"]
