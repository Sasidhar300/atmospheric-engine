"""Measure decoded audiovisual boundaries and write diagnostics."""
import json
from fractions import Fraction
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from .audio import RATE, decode
from .render import probe


def rms(frames):
    return np.sqrt(np.mean(frames.astype("float64")**2))


def audio_metrics(samples):
    count = min(12000, len(samples)//3)
    first, last = samples[:count], samples[-count:]
    step = float(np.max(np.abs(first[0]-last[-1])))
    nearby = np.abs(np.diff(np.concatenate([last,first]), axis=0))
    reference = float(np.percentile(nearby, 99))
    level = abs(20*np.log10((rms(first)+1e-9)/(rms(last)+1e-9)))
    spectrum = [np.abs(np.fft.rfft(side*np.hanning(count)[:,None], axis=0)) for side in (first,last)]
    start, end = [value.ravel() for value in spectrum]
    denominator = np.sqrt(np.sum(start*start)*np.sum(end*end))
    similarity = float((np.sum(start*end)+1e-12)/(denominator+1e-12))
    side = [float(rms(block[:,0]-block[:,1])/(rms(block)+1e-9)) for block in (first,last)]
    return {"seam_sample_step":step, "neighbor_step_p99":reference, "rms_jump_db":float(level),
            "spectral_cosine":similarity, "stereo_width_change":abs(side[0]-side[1]),
            "peak_dbfs":float(20*np.log10(max(float(np.max(np.abs(samples))),1e-9)))}


def plot(path, samples, boundary, changes):
    canvas = Image.new("RGB",(1000,460),"#141e2b")
    draw = ImageDraw.Draw(canvas)
    draw.text((40,23),"Decoded stereo waveform around the seam (±25 ms)",fill="white")
    draw.text((40,253),"Neighboring-frame mean absolute luma change",fill="white")
    draw.line((500,60,500,209),fill="#dd9966",width=2)
    waveform = np.concatenate([samples[-1200:],samples[:1200]])
    peak = max(.01,float(np.max(np.abs(waveform))))
    for ch, color in enumerate(("#6ee1d4","#8eb2f5")):
        draw.line([(40+920*i/(len(waveform)-1),135-62*float(value)/peak)
                   for i,value in enumerate(waveform[:,ch])],fill=color,width=1)
    scale = 115/max(.001,boundary,max(changes))
    for i, value in enumerate(changes):
        x = 40+900*i/max(1,len(changes)-1)
        draw.line((x,400,x,400-value*scale),fill="#6ee1d4",width=2)
    draw.line((40,400-boundary*scale,960,400-boundary*scale),fill="#dd9966",width=2)
    draw.text((40,419),"Amber line = end-to-start seam",fill="#dd9966")
    canvas.save(path)


def check(video, output, expected_frames=None, expected_fps=None, expected_size=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    streams = probe(video)["streams"]
    v = next(s for s in streams if s["codec_type"]=="video")
    a = next(s for s in streams if s["codec_type"]=="audio")
    fps = Fraction(v["avg_frame_rate"])
    frames = int(v["nb_frames"])
    seconds = float(frames/fps)
    # FFmpeg decodes an extra AAC padding frame on some files. Use the declared track duration.
    audio_duration = float(int(a["duration_ts"])*Fraction(a["time_base"]))
    expected_samples = round(audio_duration*RATE)
    samples = decode(video)[:expected_samples]
    raw = subprocess.check_output(["ffmpeg","-v","error","-i",str(video),"-an","-vf",
                                   "scale=160:90:flags=area,format=gray","-f","rawvideo","-"])
    visual = np.frombuffer(raw,np.uint8).reshape(-1,90,160)
    edges = np.concatenate([visual[:min(21,len(visual))],visual[-min(21,len(visual)):]]).astype(np.int16)
    split = len(edges)//2
    nearby = np.concatenate([np.diff(edges[:split],axis=0),np.diff(edges[split:],axis=0)])
    changes = np.mean(np.abs(nearby),axis=(1,2))
    boundary = float(np.mean(np.abs(edges[0]-edges[-1])))
    brightness = abs(float(edges[0].mean()-edges[-1].mean()))
    sound = audio_metrics(samples)
    timing_ok = (len(visual)==frames and len(samples)==expected_samples and
                 abs(audio_duration-seconds)<=1/RATE and abs(float(v["duration"])-seconds)<1e-5 and
                 (expected_frames is None or frames==expected_frames) and
                 (expected_fps is None or fps==expected_fps) and
                 (expected_size is None or (v["width"],v["height"])==expected_size) and
                 a["channels"]==2 and int(a["sample_rate"])==RATE)
    flags = {
        "timing":timing_ok, "audio_click":sound["seam_sample_step"] <= max(.007,2.5*sound["neighbor_step_p99"]),
        "audio_level":sound["rms_jump_db"] <= 3, "audio_spectrum":sound["spectral_cosine"] >= .45,
        "audio_stereo":sound["stereo_width_change"] <= .20, "audio_headroom":sound["peak_dbfs"] < -1,
        "visual_motion":boundary <= max(.06,2.5*float(np.percentile(changes,95))),
        "visual_brightness":brightness <= .7,
    }
    report = {"video":str(video), "frames":frames,"decoded_frames":len(visual),"fps":str(fps),
              "resolution":[v["width"],v["height"]],"video_seconds":seconds,"audio_seconds":audio_duration,
              "decoded_audio_samples":len(samples),"sample_rate":int(a["sample_rate"]),"channels":a["channels"],
              "video_codec":v["codec_name"],"audio_codec":a["codec_name"],"audio":sound,
              "visual":{"seam_mad":boundary,"neighbor_mad_p95":float(np.percentile(changes,95)),
                        "brightness_delta":brightness},
              "checks":flags,"automated_pass":all(flags.values()),"manual_review":"pending"}
    (output/"qc_report.json").write_text(json.dumps(report,indent=2)+"\n")
    plot(output/"seam_diagnostics.png",samples,boundary,changes)
    return report
