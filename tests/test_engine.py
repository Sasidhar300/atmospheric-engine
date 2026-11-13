import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from atmosphere import audio, qc, render, visuals
from atmosphere.cli import main
from atmosphere.config import load
from atmosphere.project import Project
from atmosphere.providers import Generated, PROVIDERS


class EngineTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.scene_file = self.root/"scene.yaml"
        original = Path("scenes/rainy_apartment.yaml").read_text()
        self.scene_file.write_text(original.replace("[1920, 1080]", "[320, 180]"))

    def test_configuration_and_periodic_frames(self):
        scene = load(self.scene_file, 2)
        with self.assertRaises(ValueError):
            load(self.scene_file, 1.021)
        artwork = self.root/"art.png"
        visuals.illustration((320,180)).save(artwork)
        compositor = visuals.Compositor(scene,artwork)
        initial = compositor.render(0)
        np.testing.assert_array_equal(initial, compositor.render(scene.frames))
        np.testing.assert_array_equal(compositor.render(-1), compositor.render(scene.frames-1))
        self.assertGreater(np.count_nonzero(initial != compositor.render(10)), 0)

    def test_deterministic_audio_and_click_detector(self):
        scene = load(self.scene_file)
        track = audio.compose(6,scene.data["music"],scene.seed)
        np.testing.assert_array_equal(track,audio.compose(6,scene.data["music"],scene.seed))
        self.assertEqual(track.shape,(288000,2))
        baseline = qc.audio_metrics(track)
        self.assertLess(baseline["seam_sample_step"], .01)
        track[-1] = .95
        self.assertGreater(qc.audio_metrics(track)["seam_sample_step"], .8)

    def test_paid_request_gate_and_cache(self):
        project = Project(self.root/"project")
        spec = {"role":"music","duration":18,"prompt":"soft ambient synth"}
        adapter = PROVIDERS["stability"]
        with patch.object(adapter,"generate",return_value=Generated(b"fixture",".wav",{})) as generate:
            plan = project.request("stability",spec,500,True)
            with self.assertRaises(ValueError):
                project.request("stability",spec,500)
            with self.assertRaises(ValueError):
                project.request("stability",spec,7,ticket=plan["job"],authorize=8)
            generate.assert_not_called()
            version = project.request("stability",spec,500,ticket=plan["job"],authorize=8)
            self.assertEqual(project.request("stability",spec,500),version)
            generate.assert_called_once()
            self.assertIsNone(project.rows("ledger")[0]["actual"])
            project.reconcile(plan["job"],8)
            self.assertEqual(project.rows("ledger")[0]["actual"],8)
            project.review(version,"rejected","Candidate has an audible artifact")
            with self.assertRaises(ValueError):
                project.request("stability",spec,500)

    def test_failed_paid_request_stays_reserved(self):
        project = Project(self.root/"project")
        spec = {"role":"music"}
        with patch.object(PROVIDERS["elevenlabs"],"generate",side_effect=TimeoutError) as generate:
            job = project.request("elevenlabs",spec,500,True)["job"]
            with self.assertRaises(TimeoutError):
                project.request("elevenlabs",spec,500,ticket=job,authorize=500)
            with self.assertRaises(ValueError):
                project.request("elevenlabs",spec,500,ticket=job,authorize=500)
            generate.assert_called_once()
            self.assertEqual(project.rows("ledger")[0]["status"],"unconfirmed")

    def test_provider_wire_formats(self):
        with patch("atmosphere.providers.send_json", return_value=(
            200, {"x-request-id":"request"}, json.dumps({
                "data":[{"b64_json":base64.b64encode(b"image").decode()}],
                "usage":{"output_tokens":100},
            }).encode()
        )) as send_json:
            generated = PROVIDERS["openai"].generate({"prompt":"An apartment","model":"gpt-image-2.6-sunburst"})
            self.assertEqual(generated.content,b"image")
            self.assertEqual(send_json.call_args.args[2]["model"],"gpt-image-2.6-sunburst")
            self.assertEqual(generated.usage["tokens"]["output_tokens"],100)
        with patch("atmosphere.providers.send",side_effect=[
            (202,{},b'{"id":"generation"}'), (202,{},b""), (200,{},b"audio"),
        ]) as send, patch("atmosphere.providers.time.sleep"):
            generated = PROVIDERS["stability"].generate({"prompt":"Soft ambient","duration":18})
            self.assertEqual(generated.content,b"audio")
            self.assertIn(b"stable-audio-3",send.call_args_list[0].args[2])
            self.assertEqual(send.call_args_list[1].args[:2],
                             ("https://api.stability.ai/v2beta/audio/results/generation","STABILITY_API_KEY"))
            self.assertEqual(len(send.call_args_list[2].args),2)
        with patch("atmosphere.providers.send_json",return_value=(200,{"song-id":"song"},b"audio")) as send_json:
            generated = PROVIDERS["elevenlabs"].generate({"prompt":"Soft ambient","duration":18})
            self.assertEqual(generated.usage["song_id"],"song")
            payload = send_json.call_args.args[2]
            self.assertEqual(payload["music_length_ms"],18000)
            self.assertEqual(payload["model_id"],"music_v2_5")
            self.assertTrue(payload["force_instrumental"])

    def test_offline_video_round_trip(self):
        output = self.root/"media"
        main(["--project",str(self.root/"project"),"demo","--scene",str(self.scene_file),
              "--duration","2","--output",str(output)])
        report = json.loads((output/"qc_report.json").read_text())
        self.assertTrue(report["checks"]["timing"])
        self.assertEqual(report["frames"],60)
        self.assertEqual(report["video_codec"],"h264")
        self.assertEqual(len(audio.decode(output/"music.wav")),96000)
        seam = render.probe(output/"seam_preview.mp4")
        self.assertAlmostEqual(float(seam["format"]["duration"]),4,places=2)

    def test_production_approval_gate(self):
        from atmosphere.cli import stage_originals
        project = Project(self.root/"project")
        scene = load(self.scene_file,2)
        staged = stage_originals(project,scene)
        artwork, music = staged["artwork"], staged["music_candidates"][0]
        command = ["--project",str(project.root),"render","--scene",str(self.scene_file),
                   "--duration","2","--output",str(self.root/"media"),
                   "--artwork",artwork,"--music",music]
        with self.assertRaises(SystemExit):
            main(command)
        project.review(artwork,"approved","Artwork inspected")
        project.review(music,"approved","Candidate reviewed")
        with self.assertRaises(SystemExit):
            main(command)
        main(command+["--preview"])
        preview = project.rows("asset")[-1]["id"]
        project.review(preview,"approved","Test fixture approval")
        main(command)


if __name__ == "__main__":
    unittest.main()
