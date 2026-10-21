import argparse
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


capcut = module("capcut_builder", ROOT / "skills/capcut-mate-video-pipeline/scripts/build_capcut_draft.py")
gpt = module("gpt_client", ROOT / "skills/gpt-image-ext-material-generation/scripts/gpt_image_ext.py")


class DownstreamTests(unittest.TestCase):
    def test_relative_media_root_is_canonicalized_without_weakening_boundary(self):
        from urllib.parse import unquote
        root = self.root / "资料"
        root.mkdir()
        video = root / "片段.mp4"
        video.write_bytes(b"fixture")
        alias = root / ".." / "资料"
        config = copy.deepcopy(self.config)
        config["shots"][0]["video"] = video.name
        with patch.object(capcut, "probe_media", return_value=self.probe):
            self.assertEqual(len(capcut.preflight(config, alias, "ffprobe")), 1)
        self.assertTrue(unquote(capcut.encoded_url(alias, video.resolve(), 9000)).endswith("/片段.mp4"))
        config["shots"][0]["video"] = "../镜头1.mp4"
        with self.assertRaises(ValueError): capcut.preflight(config, alias, "ffprobe")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="MIZAN_剪映_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / "镜头1.mp4"
        self.video.write_bytes(b"fixture only")
        self.config = {"width": 1080, "height": 1920, "shots": [{"id": "P01", "video": self.video.name, "start_s": 0, "end_s": 4,
                                                                 "captions": {"es": "Hola", "zh": "你好"}}]}
        self.probe = {"streams": [{"codec_type": "video", "width": 720, "height": 1280}, {"codec_type": "audio"}],
                      "format": {"duration": "4"}}

    def test_implicit_captions_stay_disabled(self):
        with patch.object(capcut, "probe_media", return_value=self.probe):
            shots = capcut.preflight(self.config, self.root, "ffprobe")
        self.assertEqual(len(shots), 1)
        self.assertEqual(self.config.get("subtitle_tracks", []), [])

    def test_explicit_subtitle_requires_all_text(self):
        self.config["subtitle_tracks"] = ["es", "zh"]
        del self.config["shots"][0]["captions"]["zh"]
        with patch.object(capcut, "probe_media", return_value=self.probe), self.assertRaises(ValueError):
            capcut.preflight(self.config, self.root, "ffprobe")

    def test_no_embedded_audio_is_rejected(self):
        self.probe["streams"].pop()
        with patch.object(capcut, "probe_media", return_value=self.probe), self.assertRaisesRegex(ValueError, "embedded audio"):
            capcut.preflight(self.config, self.root, "ffprobe")

    def test_explicit_none_audio_allowed(self):
        self.probe["streams"].pop()
        self.config["shots"][0]["audio_role"] = "none"
        with patch.object(capcut, "probe_media", return_value=self.probe):
            capcut.preflight(self.config, self.root, "ffprobe")

    def test_short_or_wrong_ratio_media_rejected(self):
        for mode in ("duration", "ratio"):
            probe = copy.deepcopy(self.probe)
            if mode == "duration": probe["format"]["duration"] = "2"
            else: probe["streams"][0].update(width=1280, height=720)
            with patch.object(capcut, "probe_media", return_value=probe), self.assertRaises(ValueError):
                capcut.preflight(self.config, self.root, "ffprobe")

    def test_timeline_gaps_and_duplicates_rejected(self):
        self.config["shots"].append(dict(self.config["shots"][0]))
        with patch.object(capcut, "probe_media", return_value=self.probe), self.assertRaises(ValueError):
            capcut.preflight(self.config, self.root, "ffprobe")

    def draft(self):
        draft_dir, source = self.root / "draft", self.root / "server-draft"
        media = draft_dir / "assets/videos/1.mp4"
        media.parent.mkdir(parents=True)
        media.write_bytes(self.video.read_bytes())
        data = {"canvas_config": {"width": 1080, "height": 1920}, "fps": 30, "duration": 4000000,
                "materials": {"videos": [{"id": "v1", "path": str(source / "assets/videos/1.mp4")}], "texts": []},
                "tracks": [{"type": "video", "segments": [{"material_id": "v1", "target_timerange": {"start": 0, "duration": 4000000}}]}]}
        for name in ("draft_info.json", "draft_content.json"):
            (draft_dir / name).write_text(json.dumps(data), encoding="utf-8")
        return draft_dir, source, data

    def test_draft_timeline_audio_and_portable_paths(self):
        draft, source, _ = self.draft()
        with patch.object(capcut, "probe_media", return_value=self.probe):
            shots = capcut.preflight(self.config, self.root, "ffprobe")
        result = capcut.rewrite_and_validate(draft, source, 1080, 1920, 30, [], {}, "Georgia", 8, shots)
        self.assertTrue(Path(result["materials"]["videos"][0]["path"]).is_file())
        self.assertEqual((draft / "draft_info.json").read_bytes(), (draft / "draft_content.json").read_bytes())

    def test_divergent_json_not_silently_overwritten(self):
        draft, source, data = self.draft()
        data["duration"] = 1
        (draft / "draft_content.json").write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "differ"):
            capcut.rewrite_and_validate(draft, source, 1080, 1920, 30, [], {}, "Georgia", 8)

    def test_extra_audio_track_rejected(self):
        draft, source, data = self.draft()
        data["tracks"].append({"type": "audio", "segments": [{}]})
        for name in ("draft_info.json", "draft_content.json"):
            (draft / name).write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "separate audio"):
            capcut.rewrite_and_validate(draft, source, 1080, 1920, 30, [], {}, "Georgia", 8)

    def caption_draft(self):
        draft, source, data = self.draft()
        data["materials"]["texts"] = [{"id": "t1", "font_size": 8, "fonts": [{"title": "Fallback", "path": "D:", "resource_id": ""}],
                                           "content": json.dumps({"text": "Hola", "styles": [{"size": 8, "bold": True, "italic": True, "font": {"path": "D:"}}]})}]
        data["tracks"].append({"type": "text", "segments": [{"material_id": "t1", "clip": {"transform": {"y": -700/1920}}}]})
        for name in ("draft_info.json", "draft_content.json"):
            (draft / name).write_text(json.dumps(data), encoding="utf-8")
        return draft, source, data

    def test_caption_fallback_font_is_not_relabelled_as_success(self):
        draft, source, _ = self.caption_draft()
        with self.assertRaisesRegex(RuntimeError, "fell back"):
            capcut.rewrite_and_validate(draft, source, 1080, 1920, 30, ["es"], {"es": -700}, "Georgia", 8)

    def test_explicit_local_font_copied_and_referenced(self):
        draft, source, _ = self.caption_draft()
        font = self.root / "fixture.ttf"
        font.write_bytes(b"offline font-copy fixture, not rendering evidence")
        data = capcut.rewrite_and_validate(draft, source, 1080, 1920, 30, ["es"], {"es": -700}, "Georgia", 8,
                                          font_path=font, bold=True, italic=True)
        text = data["materials"]["texts"][0]
        copied = Path(text["fonts"][0]["path"])
        self.assertEqual(copied.read_bytes(), font.read_bytes())
        self.assertEqual(json.loads(text["content"])["styles"][0]["font"]["path"], str(copied))

    def gpt_args(self):
        return argparse.Namespace(record=str(self.root / "image-task.json"), allow_paid=True, version="flare", prompt="exact approved ñ 中文",
                                  image_url=["https://example.com/ref?signature=PRIVATE"], size="9:16", resolution="1K", n=1)

    def test_paid_post_has_durable_record_and_cannot_repeat(self):
        args = self.gpt_args()
        def check_journal(*unused):
            self.assertEqual(json.loads(Path(args.record).read_text(encoding="utf-8"))["state"], "submission_uncertain")
            return {"id": "fixture-task"}
        with patch.object(gpt, "call", side_effect=check_journal) as call, redirect_stdout(io.StringIO()):
            gpt.generate(args)
            with self.assertRaises(ValueError): gpt.generate(args)
        self.assertEqual(call.call_count, 1)
        text = Path(args.record).read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE", text)
        self.assertIn("fixture-task", text)

    def test_paid_response_loss_stays_uncertain(self):
        args = self.gpt_args()
        with patch.object(gpt, "call", side_effect=TimeoutError), self.assertRaises(TimeoutError):
            gpt.generate(args)
        self.assertEqual(json.loads(Path(args.record).read_text(encoding="utf-8"))["state"], "submission_uncertain")
        with self.assertRaises(ValueError): gpt.generate(args)


if __name__ == "__main__":
    unittest.main()
