"""CLI for VascuQuest spectral and wave analysis."""
from __future__ import annotations
import json
from pathlib import Path
import typer
import numpy as np
from vascuquest.domain.result import Waveform
from vascuquest.exporters.json_exporter import load_result_json
from .core import characteristic_impedance, coherence, cross_spectral_density, harmonic_amplitude, harmonic_energy_ratio, harmonic_phase, impedance, power_spectral_density, reflection_magnitude, spectral_entropy, stft_magnitude, transfer_function, wave_intensity, wave_separation

spectral_app = typer.Typer(help="Qualified arterial spectral, impedance and wave analysis.", no_args_is_help=True)

def _wave(path: Path) -> Waveform:
    result=load_result_json(path)
    if not isinstance(result,Waveform): raise typer.BadParameter(f"{path} is not a VascuQuest Waveform")
    return result

def _portable(v):
    if isinstance(v,np.ndarray): return v.tolist()
    if isinstance(v,np.generic): return v.item()
    if isinstance(v,dict): return {k:_portable(x) for k,x in v.items()}
    return v

def _emit(result): typer.echo(json.dumps({"quantity":result.quantity.canonical_name,"values":_portable(result.values),"unit":result.canonical_unit,"method_id":result.method_id,"warnings":list(result.warnings)},sort_keys=True))

@spectral_app.command("harmonics")
def harmonics_cmd(source: Path,count:int=10,phase:bool=False):
    """Compute DFT harmonic amplitude or phase from a native waveform."""
    w=_wave(source); _emit(harmonic_phase(w,n_harmonics=count) if phase else harmonic_amplitude(w,n_harmonics=count))

@spectral_app.command("psd")
def psd_cmd(source: Path): _emit(power_spectral_density(_wave(source)))

@spectral_app.command("coherence")
def coherence_cmd(x:Path,y:Path,nperseg:int|None=None): _emit(coherence(_wave(x),_wave(y),nperseg=nperseg))

@spectral_app.command("impedance")
def impedance_cmd(pressure:Path,flow:Path,harmonics:int=10,phase:bool=False):
    mag,ph=impedance(_wave(pressure),_wave(flow),n_harmonics=harmonics); _emit(ph if phase else mag)

@spectral_app.command("characteristic-impedance")
def zc_cmd(pressure:Path,flow:Path,start:int=3,end:int=10): _emit(characteristic_impedance(_wave(pressure),_wave(flow),harmonic_start=start,harmonic_end=end))

@spectral_app.command("wave-separation")
def separation_cmd(pressure:Path,flow:Path,zc:float,backward:bool=False):
    f,b=wave_separation(_wave(pressure),_wave(flow),characteristic_impedance_pa_s_m3=zc); _emit(b if backward else f)

@spectral_app.command("wave-intensity")
def intensity_cmd(pressure:Path,velocity:Path,wave_speed:float,component:str="net",density:float=1060.0):
    net,f,b=wave_intensity(_wave(pressure),_wave(velocity),wave_speed_m_s=wave_speed,blood_density=density); mapping={"net":net,"forward":f,"backward":b}
    if component not in mapping: raise typer.BadParameter("component must be net, forward, or backward")
    _emit(mapping[component])

@spectral_app.command("stft")
def stft_cmd(source:Path,nperseg:int=64,noverlap:int|None=None): _emit(stft_magnitude(_wave(source),nperseg=nperseg,noverlap=noverlap))

@spectral_app.command("csd")
def csd_cmd(x:Path,y:Path,phase:bool=False,nperseg:int|None=None):
    mag,ph=cross_spectral_density(_wave(x),_wave(y),nperseg=nperseg); _emit(ph if phase else mag)

@spectral_app.command("transfer")
def transfer_cmd(input_waveform:Path,output_waveform:Path,phase:bool=False,nperseg:int|None=None):
    mag,ph=transfer_function(_wave(input_waveform),_wave(output_waveform),nperseg=nperseg); _emit(ph if phase else mag)

@spectral_app.command("entropy")
def entropy_cmd(source:Path): _emit(spectral_entropy(_wave(source)))

@spectral_app.command("harmonic-energy-ratio")
def her_cmd(source:Path,low_end:int=3,high_start:int=4,high_end:int=10): _emit(harmonic_energy_ratio(_wave(source),low_end=low_end,high_start=high_start,high_end=high_end))

@spectral_app.command("reflection-magnitude")
def reflection_cmd(pressure:Path,flow:Path,zc:float): _emit(reflection_magnitude(_wave(pressure),_wave(flow),characteristic_impedance_pa_s_m3=zc))

__all__=["spectral_app"]
