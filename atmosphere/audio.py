"""Sample-aligned synthesis, stem processing, and circular transitions."""
import subprocess

import numpy as np
from scipy.io import wavfile

RATE = 48000
CHORDS = [(50,57,60,64,65), (46,53,57,60,64), (53,60,64,67,69),
          (48,55,58,62,64), (43,50,53,57,62), (46,53,57,60,65),
          (45,52,55,58,61), (50,57,60,64,65)]
KEYS = ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")


def write(path, audio):
    wavfile.write(path, RATE, np.int16(np.clip(audio, -.9999, .9999)*32767))


def decode(path):
    data = subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-map","0:a:0",
                                    "-f","f32le","-ar",str(RATE),"-ac","2","-"])
    return np.frombuffer(data, "<f4").reshape(-1, 2)


def compose(duration, brief, seed, variant=0):
    count = round(duration*RATE)
    result = np.zeros((count,2), np.float32)
    key = KEYS.index(brief["key"].split()[0])
    rng = np.random.default_rng(seed+variant)
    tempo = float(brief["tempo"])
    beat = 60/tempo
    sections = 3 if duration <= 25 else len(CHORDS)
    chord_time = duration/sections
    for section, chord in enumerate(CHORDS[:sections]):
        pad = [(note, section*chord_time-chord_time*.27, chord_time*1.54, .047, False)
               for note in chord]
        melody = [(chord[-1]+12, section*chord_time+beat*(1+section%3),
                   min(chord_time*.64, beat*4), .038, True)]
        for note, onset, length, gain, bell in pad+melody:
            time = np.arange(round(length*RATE))/RATE
            envelope = np.sin(np.pi*time/length)**(2 if not bell else 1.2)
            if bell:
                envelope *= np.exp(-3*time/length)
            hz = 440*2**((note+key-2-69)/12)
            phase = rng.uniform(0, 2*np.pi)
            pan = rng.uniform(-.4,.4)
            for channel in range(2):
                phase_time = 2*np.pi*hz*time*(1 + (channel-.5)*.0017) + phase
                tone = np.sin(phase_time)+(.18 if bell else .12)*np.sin(phase_time*2)
                if bell:
                    tone += .09*np.sin(phase_time*3.003)
                samples = (tone*envelope*gain*(1+pan*(channel*2-1))).astype(np.float32)
                start = round(onset*RATE) % count
                first = min(len(samples), count-start)
                result[start:start+first,channel] += samples[:first]
                result[:len(samples)-first,channel] += samples[first:]
    dry = result.copy()
    for delay, gain in ((.21,.19),(.37,.12),(.61,.07),(.89,.035)):
        result += gain*np.roll(dry[:, ::-1], round(delay*RATE), axis=0)
    return result


def bridge(source, count, fade_seconds=2):
    """Loop one coherent take by overlapping adjacent copies at the edit."""
    if len(source) < 2:
        raise ValueError("Audio source must contain at least two samples")
    if fade_seconds < 0:
        raise ValueError("Fade duration must be nonnegative")
    if len(source) == count and fade_seconds == 0:
        return source.copy()
    fade = min(round(fade_seconds*RATE), len(source)//4, count//4)
    if fade < 2:
        return source[np.arange(count) % len(source)].copy()
    if len(source) >= count+fade:
        excerpt = source[:count+fade]
        span = count
    else:
        excerpt = source[:min(len(source), count)]
        repeats = max(2, int(np.ceil(count/(len(excerpt)-fade))))
        span = int(np.ceil(count/repeats))
        if span+fade > len(excerpt):
            raise ValueError("Source too short for requested loop overlap")
        excerpt = excerpt[:span+fade]
    weight = (.5-.5*np.cos(np.linspace(0,np.pi,fade)))[:,None]
    loop = excerpt[fade:span+fade].copy()
    loop[-fade:] = excerpt[span:span+fade]*(1-weight) + excerpt[:fade]*weight
    # Non-integral repeats need a final overlap at the exact project boundary.
    if count % span:
        tiled = loop[np.arange(count+fade) % span]
        loop = tiled[fade:].copy()
        loop[-fade:] = tiled[count:count+fade]*(1-weight) + tiled[:fade]*weight
        return loop
    return loop[np.arange(count) % span].copy()


def fit_music(source, count):
    """Use one coherent performance and preserve its duration with an offset overlap."""
    fade = min(RATE*2, count//4)
    if len(source) >= count+fade:
        return bridge(source, count, fade/RATE)
    if len(source) < count:
        raise ValueError("Music take must be at least as long as the render")
    # Crossfade around an interior cut after a modest time stretch. The
    # crossfade spans the seam in playback while retaining the full arrangement.
    from scipy.signal import resample
    return bridge(resample(source[:count], count+fade, axis=0), count, fade/RATE)

def environment(name, settings, duration, seed, source=None):
    count = round(duration*RATE)
    low, high = settings.get("low_hz", 40), settings.get("high_hz", 15000)
    if not 0 < low < high < RATE/2:
        raise ValueError(f"Invalid filter for {name}")
    if source is None and name not in {"rain","wind","traffic","fire","hum"}:
        raise ValueError(f"Unknown procedural stem {name}")
    frequencies = np.fft.rfftfreq(count, 1/RATE)
    response = (1/np.sqrt(1+(low/np.maximum(frequencies,.1))**6)
                / np.sqrt(1+(frequencies/high)**6))
    if source is None:
        rng = np.random.default_rng(seed)
        bed = rng.standard_normal((count, 2), dtype=np.float32)
    else:
        bed = bridge(decode(source), count, settings.get("fade", 2))
    for ch in range(2):
        bed[:,ch] = np.fft.irfft(np.fft.rfft(bed[:,ch])*response, n=count)
    if name == "hum" and not source:
        bed += (.7*np.sin(2*np.pi*round(duration*65)*np.arange(count)/count))[:,None]
    if source is None:
        bed /= max(float(np.std(bed)), .001)*5
    mid = bed.mean(axis=1, keepdims=True)
    bed = mid+(bed-mid)*settings.get("width", .8)
    automation = np.cos(2*np.pi*np.arange(count)/count)
    bed *= (1+settings.get("automation", .1)*automation[:,None])*settings.get("gain", .1)
    return bed


def mix(stems):
    audio = sum(stems)
    return audio * min(1, .82/max(float(np.max(np.abs(audio))), .001))


def harmonic_similarity(source, seconds=2):
    """Cosine similarity of pitch classes at the two ends of one take."""
    def chroma(samples):
        mono = samples.mean(axis=1)
        freq = np.fft.rfftfreq(len(mono), 1/RATE)
        valid = (freq>=55)&(freq<=2400)
        bins = np.rint(69+12*np.log2(freq[valid]/440)).astype(int)%12
        energy = np.abs(np.fft.rfft(mono*np.hanning(len(mono))))[valid]**2
        return np.bincount(bins, energy, minlength=12)
    count = min(round(seconds*RATE), len(source)//2)
    start, end = chroma(source[:count]), chroma(source[-count:])
    return float(np.sum(start*end) / max(1e-12, np.sqrt(np.sum(start*start)*np.sum(end*end))))
