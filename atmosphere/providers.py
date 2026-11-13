"""Provider adapters. The project store owns authorization and billing."""
import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Protocol
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


@dataclass
class Generated:
    content: bytes
    extension: str
    usage: dict


class Provider(Protocol):
    paid: bool
    estimate_cents: int | None

    def generate(self, spec: dict) -> Generated: ...


class Local:
    paid = False
    estimate_cents = 0

    def generate(self, spec):
        source = Path(spec["file"])
        return Generated(source.read_bytes(), source.suffix.lower(), {})


class Mock(Local):
    def generate(self, spec):
        import io
        import numpy as np
        from PIL import Image
        from scipy.io import wavfile
        buffer = io.BytesIO()
        if spec.get("role") == "music":
            wavfile.write(buffer, 48000, np.zeros((48000,2),np.int16))
            return Generated(buffer.getvalue(), ".wav", {})
        Image.new("RGB", (160,90), "#35516a").save(buffer, format="PNG")
        return Generated(buffer.getvalue(), ".png", {})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(url, token_name, payload=None, extra=None, key_header="Authorization"):
    token = os.environ[token_name]
    headers = {key_header: f"Bearer {token}" if key_header == "Authorization" else token}
    headers.update(extra or {})
    with build_opener(NoRedirect()).open(Request(url, payload, headers), timeout=120) as result:
        return result.status, result.headers, result.read()


def send_json(url, key, payload, header="Authorization"):
    return send(url,key,json.dumps(payload).encode(),{"Content-Type":"application/json"},header)


class OpenAI:
    paid = True
    estimate_cents = None

    def generate(self, spec):
        model = spec.get("model","gpt-image-2.6-flare")
        if model not in {"gpt-image-2.6-flare","gpt-image-2.6-sunburst"}:
            raise ValueError("Unsupported OpenAI image model")
        payload = {key:spec[key] for key in ("prompt","size","quality","complexity","background") if key in spec}
        payload.update(model=model, n=1, output_format="png")
        _, headers, body = send_json("https://api.openai.com/v1/images/generations","OPENAI_API_KEY",payload)
        body = json.loads(body)
        return Generated(base64.b64decode(body["data"][0]["b64_json"]),".png",
                         {"request_id":headers.get("x-request-id"),"tokens":body.get("usage")})


class Stability:
    paid = True
    estimate_cents = 8
    url = "https://api.stability.ai/v2beta/audio"

    def generate(self, spec):
        boundary = uuid4().hex
        fields = dict(prompt=spec["prompt"],duration=spec["duration"],model="stable-audio-3",output_format="wav")
        fields.update({key:spec[key] for key in ("seed","steps","cfg_scale") if key in spec})
        body = "".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
                       for key,value in fields.items()) + f"--{boundary}--\r\n"
        status, _, result = send(self.url+"/stable-audio/text-to-audio","STABILITY_API_KEY",body.encode(),
                                 {"Content-Type":f"multipart/form-data; boundary={boundary}","Accept":"audio/*"})
        if status != 202:
            raise RuntimeError(f"Expected queued generation, got HTTP {status}")
        generation = json.loads(result)["id"]
        for _ in range(60):
            status, _, result = send(self.url+"/results/"+quote(generation,safe=""),"STABILITY_API_KEY",
                                     extra={"Accept":"audio/*"})
            if status == 200:
                return Generated(result,".wav",{"generation_id":generation})
            if status != 202:
                break
            time.sleep(10)
        raise RuntimeError(f"Result unavailable for generation {generation}")


class ElevenLabs:
    paid = True
    estimate_cents = None

    def generate(self, spec):
        _, headers, body = send_json("https://api.elevenlabs.io/v1/music?output_format=mp3_48000_192",
                                     "ELEVENLABS_API_KEY",
                                     dict(model_id="music_v2_5",prompt=spec["prompt"],
                                          music_length_ms=round(spec["duration"]*1000),force_instrumental=True),
                                     "xi-api-key")
        return Generated(body,".mp3",{"song_id":headers.get("song-id")})


PROVIDERS = {"local":Local(), "mock":Mock(), "openai":OpenAI(),
             "stability":Stability(), "elevenlabs":ElevenLabs()}
