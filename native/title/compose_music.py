#!/usr/bin/env python3
"""NiakPS5 original, reproducible ambient soundtrack.

The music is synthesized mathematically. No upstream recordings, melodies,
AI-generated audio files, samples, external accounts or copyrighted loops.
Requires ffmpeg solely to encode generated PCM to Ogg Vorbis for the PS5 mixer.
"""
from __future__ import annotations
import array
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave

SAMPLE_RATE=24000
SECONDS=36
SONGS=(
    ("niak-dawn",44,(0,3,7),((0,3,7),(5,8,12),(3,7,10),(7,10,14))),
    ("niak-orbit",40,(0,4,7),((0,4,7),(7,11,14),(9,12,16),(5,9,12))),
    ("niak-twilight",47,(0,3,7),((0,3,7),(8,12,15),(5,8,12),(10,14,17))),
)
def frequency(midi: float) -> float:
    return 440.0 * 2 ** ((midi-69.0)/12.0)

def render_song(out: Path, base: int, chords) -> None:
    # Slow four-chord progression, small pentatonic motif, no sampled sounds.
    # Stereo is deliberately subtle to keep console menus relaxing.
    with wave.open(str(out),"wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames_per_chord=SAMPLE_RATE*9
        block=array.array("h")
        phase=[0.0]*4
        lead_phase=[0.0,0.0]
        for index in range(SAMPLE_RATE*SECONDS):
            t=index/SAMPLE_RATE
            chord_idx=min(index//frames_per_chord,3)
            chord=chords[chord_idx]
            chord_t=(index%frames_per_chord)/SAMPLE_RATE
            # Slow pad attack/release and broad fade before playlist transition.
            envelope=min(1.0,chord_t/1.8,(9.0-chord_t)/2.2)
            envelope=max(0.0,envelope)
            overall=min(1.0,t/2.5,(SECONDS-t)/3.5)
            notes=(base+chord[0]-12,base+chord[0],base+chord[1],base+chord[2])
            pad=0.0
            for k,note in enumerate(notes):
                phase[k]+=2.0*math.pi*frequency(note)/SAMPLE_RATE
                if phase[k]>2.0*math.pi:phase[k]-=2.0*math.pi
                pad+=math.sin(phase[k])*(0.38 if k==0 else 0.17)
            beat=int(chord_t*1.3)
            motif=(0,2,1,3,2,1,0,1,2,3,1)
            note=base+chord[motif[beat%len(motif)]%3]+12
            lead_t=(chord_t*1.3)%1.0
            bell=(1.0-lead_t)**3
            lead_phase[0]+=2*math.pi*frequency(note)/SAMPLE_RATE
            lead_phase[1]+=2*math.pi*frequency(note)*2/SAMPLE_RATE
            if lead_phase[0]>2*math.pi:lead_phase[0]-=2*math.pi
            if lead_phase[1]>2*math.pi:lead_phase[1]-=2*math.pi
            line=(math.sin(lead_phase[0])+0.18*math.sin(lead_phase[1]))*bell*0.13
            signal=(pad*0.24*envelope+line)*max(0.0,overall)
            drift=math.sin(t*0.44)*0.10
            left=max(-1.0,min(1.0,signal*(1.0-drift)))
            right=max(-1.0,min(1.0,signal*(1.0+drift)))
            block.extend((int(left*26000),int(right*26000)))
            if len(block)>=SAMPLE_RATE*2:
                if sys.byteorder!="little":block.byteswap()
                wav.writeframesraw(block.tobytes())
                block=array.array("h")
        if block:
            if sys.byteorder!="little":block.byteswap()
            wav.writeframesraw(block.tobytes())

def main() -> None:
    if len(sys.argv)!=2:raise SystemExit("Usage: compose_music.py OUTDIR")
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg:raise SystemExit("ffmpeg required to encode original NiakPS5 music")
    output=Path(sys.argv[1])
    output.mkdir(parents=True,exist_ok=True)
    # Remove the template project's pre-existing recorded music, so only
    # tracks uniquely composed for NiakPS5 can enter the retail title package.
    for original in output.glob("*.ogg"):original.unlink()
    with tempfile.TemporaryDirectory(prefix="niak-music-") as work:
        for title,root,_,progression in SONGS:
            raw=Path(work)/(title+".wav")
            render_song(raw,root,progression)
            subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-y",
                            "-i",str(raw),"-ar","48000","-ac","2",
                            "-c:a","libvorbis","-q:a","4",
                            str(output/(title+".ogg"))],check=True)
            if (output/(title+".ogg")).stat().st_size<2000:
                raise RuntimeError("Empty encoded soundtrack "+title)
            print("Original NiakPS5 soundtrack:",title)
if __name__=="__main__":main()
