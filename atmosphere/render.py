"""Streaming H.264 assembly."""
import json
import subprocess

import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory

from . import audio


def ffmpeg(*args):
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",*map(str,args)], check=True)


def probe(path):
    return json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams",
                                                "-show_format","-of","json",str(path)]))


def stream(scene, compositor, audio_file, output, frame_indices=None):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temp:
        target = Path(temp)/"render.mp4"
        command = ["ffmpeg","-hide_banner","-v","error","-y","-f","rawvideo",
                   "-pixel_format","rgb24","-video_size",f"{scene.width}x{scene.height}",
                   "-framerate",str(scene.fps),"-i","pipe:0","-i",str(audio_file),"-map","0:v:0",
                   "-map","1:a:0","-c:v","libx264","-preset","veryfast","-crf","18",
                   "-pix_fmt","yuv420p","-c:a","aac","-b:a","256k","-movflags","+faststart",str(target)]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
            try:
                with process.stdin:
                    for index in range(scene.frames) if frame_indices is None else frame_indices:
                        process.stdin.write(compositor.render(index).tobytes())
            except BaseException:
                process.kill()
                raise
            if process.wait():
                raise RuntimeError("FFmpeg failed while encoding")
        target.replace(output)


def seam_preview(video, frames, fps, output):
    span = min(8*fps, frames//2)
    duration = span/fps
    sample_count = frames*(audio.RATE//fps)
    samples = audio.decode(video)[:sample_count]
    half = span*(audio.RATE//fps)
    if len(samples) != sample_count:
        raise ValueError("Cannot create seam preview from incomplete audio")
    seam = np.concatenate([samples[-half:],samples[:half]]*2)
    with TemporaryDirectory(dir=Path(output).parent) as temp:
        temp = Path(temp)
        audio.write(temp/"preview.wav", seam)
        ffmpeg("-i",video,"-filter_complex",
               f"[0:v]split[a][b];[a]trim=start_frame={frames-span}:end_frame={frames},setpts=PTS-STARTPTS[t];"
               f"[b]trim=end_frame={span},setpts=PTS-STARTPTS[h];[t][h]concat=n=2:v=1:a=0[v]",
               "-map","[v]","-an","-c:v","libx264","-preset","veryfast",temp/"transition.mp4")
        ffmpeg("-stream_loop",1,"-i",temp/"transition.mp4","-i",temp/"preview.wav",
               "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-t",duration*4,
               "-movflags","+faststart",output)
