# Atmosphere Engine

Local, headless audiovisual production for seamless ambience loops. *Rain Above Meridian* is a 90-second futuristic apartment demonstration with original procedural illustration, warm stereo synthesis, and independent rain and wind. The illustration is a test asset. Preview and production use the same clock and scene recipe.

## Setup and render

On Apple Silicon macOS, install Python 3.11+ and FFmpeg with H.264 encoding. If FFmpeg is missing, install Homebrew from [brew.sh](https://brew.sh/) if needed, then run `brew install ffmpeg`.

```sh
./setup.sh
source .venv/bin/activate
python -m atmosphere demo --preview
python -m atmosphere demo --duration 90
python -m unittest discover -s tests -v
```

Python streams RGB frames into FFmpeg. Pillow imports still images, NumPy manages deterministic clocks and synthesis, OpenCV composites each frame, and SciPy writes stereo WAVs and fits external music. FFmpeg encodes H.264/AAC and decodes the result for QC. The renderer uses CPU processing on Apple Silicon. Blender is a possible future adapter. The generated illustration and short candidates are stored under `outputs/project` with source and license metadata. Place your own source files under `assets/` or supply their paths directly.

## Production with reviewed media

```sh
python -m atmosphere candidates
python -m atmosphere generate local background --file assets/room.png --license "Original illustration by …"
python -m atmosphere generate local music --file assets/score.wav --license "Original composition by …"
python -m atmosphere assets
python -m atmosphere review ART_ID approved --note "Checked scene composition, provenance and window alignment"
python -m atmosphere review MUSIC_ID approved --note "Listened to the score and checked its publication rights"
python -m atmosphere render --artwork ART_ID --music MUSIC_ID --preview
python -m atmosphere review PREVIEW_ID approved --note "Watched and listened to the end-to-start transition"
python -m atmosphere render --scene scenes/rainy_apartment.yaml --artwork ART_ID --music MUSIC_ID --duration 90
```

Copy and edit the scene YAML for a different room. Use normalized polygon points in `windows` and `occlusion` or import a grayscale mask and pass `--mask ID`. A supplied mask replaces the window polygons and keeps the occlusion polygons. Use PNG or JPEG artwork matching the scene aspect ratio (16:9 for this pilot) and independently reviewed RGBA layers with `--foreground ID` or `--overlay ID`. Configure their parallax using `layer_depths`. Set `camera_pixels: 0` for a locked camera. Tune the intensity of rain, haze, light flicker and reflections in `effects`.

Play `music.wav`, `rain.wav`, `wind.wav`, and `final_audio.wav` independently. For environmental recordings, import the named stem and pass `--stem rain=ID` (repeat for other stems). The scene controls gain, cutoff frequencies, stereo width, cyclic gain automation and crossfade length per stem. The local score uses programmable eight-section note events with circular delay. External scores must be a single reviewed take at least as long as the render. Prefer a single take with compatible ends and two seconds of extra audio for the circular crossfade. The preview reports ending chroma similarity for review. A procedural candidate is a short audition of a recipe. Listen to the assembled preview before approving it. Use `review ID rejected --note "…"` to retain rejected asset versions without reusing them.

## Provider interface and spending

A provider implements `generate(spec) -> Generated` with output bytes, file extension and usage metadata, plus `paid` and `estimate_cents`. Extend the registry in `atmosphere/providers.py`. The CLI also includes a seeded procedural composer and illustration generator. The mock provider supplies test fixtures. The project store hashes job parameters and imported content, keeps immutable versions, and preserves approved assets during regeneration.

```sh
python -m atmosphere generate openai background --dry-run
python -m atmosphere generate stability music --duration 18 --dry-run
python -m atmosphere generate elevenlabs music --duration 18 --dry-run
python -m atmosphere costs
```

Generation requires explicit `--authorize-job JOB_HASH --reserve-cents AMOUNT` using the exact dry-run parameters. Credentials come from `OPENAI_API_KEY`, `STABILITY_API_KEY`, and `ELEVENLABS_API_KEY`. The default project budget is US$5. The ledger reserves against that budget before any paid submission. Unknown pricing requires a manually determined reservation. The budget limits local reservations. Providers may independently bill more than a reservation. Reconcile confirmed charges with `python -m atmosphere reconcile JOB_HASH ACTUAL_CENTS`. Ambiguous failures retain their reservations. Use a new `--regenerate LABEL`, dry-run and authorization to submit another request. Stability polls the existing job with GET. The adapters were exercised offline and no live request was made.

OpenAI uses the GPT Image 2.6 Flare or Sunburst model, PNG output and an editable prompt template. The API reference lists 1536×1024 as a standard landscape size. For a 16:9 render, crop the downloaded artwork deliberately and import the cropped version. Use `--size`, `--model`, `--quality`, `--complexity`, and `--background` to plan image requests. Official references are available for [OpenAI Images](https://developers.openai.com/api/reference/resources/images/methods/generate), [Stable Audio 3.0](https://docs.stability.ai/api-reference/stable-audio/text-to-audio), [Stability pricing](https://docs.stability.ai/pricing), and [Eleven Music](https://elevenlabs.io/docs/api-reference/music/compose/).

## Quality and release review

```sh
python -m atmosphere qc --video outputs/pilot_90s.mp4 --output outputs/recheck
```

- Watch `seam_preview.mp4` at normal speed. Its 32 seconds contain two copies of the last eight seconds followed by the first eight. Check window masks, occlusion, rain, lighting, reflections and camera motion at 0:08 and 0:24.
- Listen through each transition on headphones and speakers. Check for clicks, bass or stereo jumps, distracting repeats, and whether the score suits the scene.
- Inspect `qc_report.json` and `seam_diagnostics.png`. The report checks decoded frame count, audio duration, sample steps, RMS, spectrum, stereo width, headroom, luma and boundary motion versus adjacent frames. The thresholds are heuristics and the manual approval is a separate decision.

For publication, replace the demonstration artwork with a reviewed cinematic still and scene-specific layers, then review the complete score, independent stems, and loop by listening and watching.

## Continuing across coding agents

Start with `make status`, then open the [current handoff](docs/HANDOFF.md). See [shared workflows and client setup](docs/AGENT_SETUP.md) for targeted tests, Graphify and Codex, Antigravity, Gemini CLI and Claude Code setup.
