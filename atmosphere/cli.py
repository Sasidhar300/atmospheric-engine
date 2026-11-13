"""Local production and review commands."""
import argparse
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from subprocess import CalledProcessError
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from . import audio, qc, render, visuals
from .config import load
from .project import Project, fingerprint
from .providers import Generated, PROVIDERS

DEFAULT_SCENE = "scenes/rainy_apartment.yaml"


def stage_originals(project, scene):
    art_spec = {"role":"background","seed":scene.seed,"license":"Original procedural demo illustration"}
    existing = {row["job"]:row for row in project.rows("asset")}
    art_job = fingerprint(["procedural",art_spec])
    if art_job not in existing:
        png = io.BytesIO()
        visuals.illustration(seed=scene.seed).save(png,format="PNG")
        art_id = project.register("procedural",art_spec,Generated(png.getvalue(),".png",{}))
    else:
        art_id = existing[art_job]["id"]
    candidates = []
    with TemporaryDirectory() as directory:
        wav = Path(directory)/"music.wav"
        for variant in (0,1):
            brief = scene.data["music"]
            spec = dict(role="music", license="Original procedural synthesis", brief=brief, variant=variant,
                        seed=scene.seed, duration=18, target_duration=scene.duration)
            job = fingerprint(["procedural",spec])
            if job in existing:
                candidates.append(existing[job]["id"])
                continue
            audio.write(wav,audio.compose(18,brief,scene.seed,variant))
            candidates.append(project.register("procedural",spec,Generated(wav.read_bytes(),".wav",{})))
    return {"artwork":art_id,"music_candidates":candidates}


def recipe(args, scene, project, demo=False):
    chosen = {}
    def select(role, asset_id):
        if asset_id:
            chosen[role] = asset_id
            return project.approved(asset_id,role)
        return None
    art_id, music_id = args.artwork, args.music
    if demo:
        defaults = stage_originals(project,scene)
        art_id, music_id = defaults["artwork"], defaults["music_candidates"][0]
    layers = []
    for role, depth in (("overlay",.7),("foreground",1.5)):
        path = select(role,getattr(args,role))
        if path:
            layers.append((path,scene.data.get("layer_depths",{}).get(role,depth)))
    mask = select("mask",args.mask)
    if demo:
        # Demo artifacts use only local originals and carry a pending manual review.
        items = {row["id"]:row for row in project.rows("asset")}
        originals = [items[asset_id] for asset_id in (art_id,music_id)]
        if any(item["verdict"]=="rejected" for item in originals):
            raise ValueError("The demo assets were rejected")
        art_path, music_path = [project.path(item) for item in originals]
        chosen.update(background=art_id,music=music_id)
    else:
        if not art_id or not music_id:
            raise ValueError("Specify approved --artwork and --music IDs, or use demo for an unapproved local sample")
        art_path, music_path = select("background",art_id),select("music",music_id)
    imports = {}
    for item in args.stem or []:
        name, asset_id = item.split("=",1)
        if name not in scene.data.get("environment",{}):
            raise ValueError(f"Declare environment stem {name!r} in the scene")
        imports[name] = select(name,asset_id)
    music_row = next(row for row in project.rows("asset") if row["id"]==music_id)
    return art_path, layers, mask, music_path, music_row, imports, chosen


def make_media(args, scene, project, demo):
    canvas, layers, mask, track, music_row, imports, chosen = recipe(args,scene,project,demo)
    recipe_key = fingerprint([scene.data,scene.duration,chosen,scene.fps])
    output = Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    is_preview = args.preview
    if not is_preview and not demo:
        reviewed = next((row for row in project.available("preview") if json.loads(row["spec"])["recipe"]==recipe_key),None)
        if reviewed is None:
            raise ValueError("Render a preview using the same recipe, then review and approve it before full render")
        project.path(reviewed)
    compositor = visuals.Compositor(scene,canvas,layers,mask)
    duration = scene.duration
    count = round(duration*audio.RATE)
    if music_row["provider"]=="procedural":
        spec = json.loads(music_row["spec"])
        if not demo and spec["target_duration"] != duration:
            raise ValueError("Approve a candidate for the target duration")
        music = audio.compose(duration,spec["brief"],spec["seed"],spec["variant"])
        harmony = audio.harmonic_similarity(music)
    else:
        source = audio.decode(track)
        if len(source) < count:
            raise ValueError("Approve a single full-length external composition or use local synthesis")
        harmony = audio.harmonic_similarity(source)
        music = audio.fit_music(source,count)
    stems = {"music":music}
    for i,(name,settings) in enumerate(scene.data.get("environment",{}).items()):
        if name in {"music","final_audio"} or not name.replace("_","").isalnum():
            raise ValueError(f"Invalid stem name {name!r}")
        stems[name] = audio.environment(name,settings,duration,scene.seed+i,imports.get(name))
    mixed = audio.mix(stems.values())
    video = output/("production_preview.mp4" if is_preview else "pilot_90s.mp4" if duration==90 else "pilot.mp4")
    if is_preview:
        span = min(4*scene.fps,scene.frames//2)
        indices = list(range(scene.frames-span,scene.frames))+list(range(span))
        limit = span*(audio.RATE//scene.fps)
        with TemporaryDirectory() as directory:
            wav = Path(directory)/"preview.wav"
            audio.write(wav,np.concatenate([mixed[-limit:],mixed[:limit]]))
            render.stream(scene,compositor,wav,video,indices)
        sample_cut = limit
        decoded = audio.decode(video)
        decoded = decoded[:2*sample_cut]
        decoded = np.concatenate([decoded[sample_cut:],decoded[:sample_cut]])
        previous = compositor.render(scene.frames-1)
        following = compositor.render(0)
        continuity = {"audio":qc.audio_metrics(decoded),
                      "source_frame_rgb_mad":float(np.mean(np.abs(previous.astype(np.int16)-following)))}
        preview_id = project.register("render",{"role":"preview","recipe":recipe_key,"assets":chosen,
                                                "continuity":continuity},
                                      Generated(video.read_bytes(),".mp4",{}))
        return {"video":str(video),"preview_id":preview_id,"loop_transition_seconds":span/scene.fps,
                "manual_review":"pending","measured_transition":continuity,"ending_chroma_similarity":harmony}
    for name,data in dict(stems,final_audio=mixed).items():
        audio.write(output/f"{name}.wav",data)
    render.stream(scene,compositor,output/"final_audio.wav",video)
    render.seam_preview(video,scene.frames,scene.fps,output/"seam_preview.mp4")
    report = qc.check(video,output,scene.frames,scene.fps,(scene.width,scene.height))
    report.update(asset_versions=chosen, demo_artwork=demo, music_ending_chroma_similarity=harmony)
    (output/"qc_report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


def ceiling_cents(value):
    amount = Decimal(str(value))*100
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise ValueError("Project budget must be a nonnegative USD amount with cent precision")
    return int(amount)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="atmosphere")
    parser.add_argument("--project",default="outputs/project")
    commands = parser.add_subparsers(dest="command",required=True)
    for command in ("demo","render","candidates","generate"):
        group = commands.add_parser(command)
        group.add_argument("--scene",default=DEFAULT_SCENE)
        group.add_argument("--duration",type=float)
        if command in {"demo","render"}:
            group.add_argument("--preview",action="store_true")
            group.add_argument("--output",default="outputs")
            for role in ("artwork","music","mask","overlay","foreground"):
                group.add_argument("--"+role)
            group.add_argument("--stem",action="append")
        if command=="generate":
            group.add_argument("provider",choices=PROVIDERS)
            group.add_argument("role")
            group.add_argument("--file")
            group.add_argument("--license")
            group.add_argument("--prompt")
            group.add_argument("--model")
            group.add_argument("--size",default="1536x1024")
            group.add_argument("--quality",choices=["low","medium","high","auto"])
            group.add_argument("--complexity",choices=["low","medium","high"])
            group.add_argument("--background",choices=["opaque","transparent"])
            group.add_argument("--dry-run",action="store_true")
            group.add_argument("--authorize-job")
            group.add_argument("--reserve-cents",type=int)
            group.add_argument("--regenerate")
    group=commands.add_parser("review")
    group.add_argument("id")
    group.add_argument("verdict",choices=["approved","rejected"])
    group.add_argument("--note",required=True)
    commands.add_parser("assets")
    commands.add_parser("costs")
    group=commands.add_parser("reconcile")
    group.add_argument("job")
    group.add_argument("actual_cents",type=int)
    group=commands.add_parser("qc")
    group.add_argument("--video",required=True)
    group.add_argument("--output",default="outputs")
    args = parser.parse_args(argv)
    try:
        if args.command=="qc":
            result = qc.check(args.video,args.output)
        else:
            project = Project(args.project)
            scene = load(args.scene,args.duration) if hasattr(args,"scene") else None
            if args.command in {"demo","render"}:
                if args.preview:
                    scene = replace(scene,width=1280,height=720)
                result = make_media(args,scene,project,args.command=="demo")
            elif args.command=="candidates":
                result = stage_originals(project,scene)
            elif args.command=="generate":
                spec = {"role":args.role}
                if args.provider=="local":
                    if not args.file or not args.license:
                        raise ValueError("Import requires --file and --license provenance")
                    spec.update(file=str(Path(args.file).resolve()),license=args.license)
                if args.provider=="openai":
                    if args.role not in {"background","foreground","overlay","mask"}:
                        raise ValueError("Image generation requires an image layer role")
                    spec.update(prompt=args.prompt or scene.data["image_prompt"].format(role=args.role),
                                size=args.size,license="OpenAI API output; review before publication")
                    spec.update({key:getattr(args,key) for key in ("quality","model","complexity","background")
                                 if getattr(args,key) is not None})
                if args.provider in {"stability","elevenlabs"}:
                    if args.role != "music":
                        raise ValueError("Music generation requires role music")
                    brief = dict(scene.data["music"], intended_duration=args.duration or 18)
                    spec.update(brief=brief,duration=args.duration or 18,
                                prompt=args.prompt or ", ".join(f"{key}: {value}" for key,value in brief.items()),
                                license="Provider output; verify account-specific rights before approval")
                result = project.request(args.provider,spec,ceiling_cents(scene.data.get("budget_usd",5)),args.dry_run,
                                         args.authorize_job,args.reserve_cents,args.regenerate)
            elif args.command=="review":
                project.review(args.id,args.verdict,args.note)
                result = {"id":args.id,"verdict":args.verdict}
            elif args.command=="assets":
                result = project.rows("asset")
            elif args.command=="reconcile":
                project.reconcile(args.job,args.actual_cents)
                result = project.rows("ledger")
            else:
                entries = project.rows("ledger")
                result = {"requests":entries,"estimated_cents":sum(row["estimate"] or 0 for row in entries),
                          "actual_confirmed_cents":sum(row["actual"] or 0 for row in entries),
                          "unconfirmed_requests":sum(row["actual"] is None for row in entries)}
        print(json.dumps(result,indent=2))
    except (ValueError,InvalidOperation,KeyError,OSError,RuntimeError,CalledProcessError) as error:
        parser.exit(1,f"{error}\n")
