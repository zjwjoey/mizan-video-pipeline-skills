import copy
from contextlib import redirect_stdout
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/dreamina-canvas-bootstrap/scripts"
sys.path.insert(0, str(SCRIPTS))
from canvas_bootstrap import (Bootstrap, CanvasCLI, CLIError, GROUPS, display_name, extract_docx, node_text,
                              file_hash, generated_filename, main, safe_filename, write_json)
from pipeline_handoff import approved, build_plan, record_task


class FakeCLI:
    """Public 1.0.3 response shapes, including node show's `nodes` (not `items`)."""
    def __init__(self, layout=True):
        self.nodes, self.resources, self.canvases, self.requests, self.calls = {}, {}, {}, [], []
        self.layout, self.fail_after, self.fail_before = layout, None, None

    def discover(self):
        return dict(version="fixture-1.0.3", logged_in=True, text=True, media_import=dict(image=True, audio=True, video=True),
                    resource_upload=True, native_group=False, layout=self.layout, query=True)

    def call(self, parts, positional=(), **flags):
        assert not flags.get("run") and parts not in (("node", "run"), ("node", "quote"), ("node", "confirm"))
        self.calls.append((parts, copy.deepcopy(flags)))
        if self.fail_before == parts:
            self.fail_before = None
            raise CLIError({"code": "transport_uncertain"})
        if parts == ("canvas", "ls"):
            result = {"items": list(self.canvases.values()), "hasMore": False}
        elif parts == ("canvas", "create"):
            pid = flags["project-id"]
            self.canvases[pid] = dict(projectId=pid, name=positional[0], webUrl="https://jimeng.jianying.com/ai-tool/ai-canvas/" + pid)
            result = {"project": self.canvases[pid]}
        elif parts == ("node", "find"):
            result = {"items": list(self.nodes.values()), "hasMore": False, "total": len(self.nodes)}
        elif parts == ("node", "show"):
            result = {"nodes": [{"result": "FOUND", "node": self.nodes[nid]} for nid in flags["node-id"] if nid in self.nodes]}
        elif parts == ("resource", "get"):
            if positional[0] not in self.resources:
                raise CLIError({"code": "service.6"})
            result = self.resources[positional[0]]
        elif parts == ("resource", "upload"):
            rid = flags["resource-id"]
            self.resources[rid] = dict(resourceId=rid, status="success", type=flags["type"])
            result = dict(resourceId=rid, mediaType=flags["type"])
        elif parts[:2] in (("node", "create"), ("node", "edit")):
            nid = flags["node-id"]
            if parts[1] == "create" and nid in self.nodes:
                raise AssertionError("duplicate create for existing node")
            node = self.nodes.setdefault(nid, {"nodeId": nid, "resources": [], "type": parts[2]})
            node.update(title=flags["title"], status="success")
            if "text" in flags:
                node["text"] = flags["text"]
            if "resource-id" in flags:
                node["resources"] = [self.resources[r] for r in flags["resource-id"]]
            node["layout"] = dict(x=flags.get("x", 0), y=flags.get("y", 0), width=600,
                                  height=200 + len(flags.get("text", "")) * 0.5)
            result = {"node": node}
        elif parts == ("operation", "status"):
            result = {"state": "unknown", "resources": []}
        else:
            raise AssertionError(parts)
        if self.fail_after == parts:
            self.fail_after = None
            raise CLIError({"code": "transport_uncertain"})
        return copy.deepcopy(result)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="MIZAN_中文_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.p = json.loads((ROOT / "examples/mizan-family-party/production_manifest.json").read_text(encoding="utf-8"))
        self.p["assets"] = self.p["assets"][:3]
        for i, asset in enumerate(self.p["assets"]):
            path = self.root / asset["local_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture-" + str(i).encode())
        self.path = self.root / "production_manifest.json"
        write_json(self.path, self.p)
        self.cli = FakeCLI()

    def job(self):
        return Bootstrap(self.path, self.cli)

    def sync(self, job=None):
        job = job or self.job()
        job.discover()
        job.ensure_canvas()
        job.structure()
        job.sync()
        return job

    def test_initial_canvas_and_visible_nodes(self):
        job = self.sync()
        self.assertEqual(job.state["sync_status"], "synced")
        self.assertEqual(len(self.cli.canvases), 1)
        self.assertEqual(len(self.cli.nodes), 18)  # 9 headings + 3 common + 3 shots + 3 media
        self.assertEqual(job.state["organization_mode"], "spatial_sections")
        self.assertEqual(next(v for v in self.cli.nodes.values() if v["title"].startswith("完整视频脚本"))["text"], self.p["full_script"])

    def test_repeat_has_no_remote_mutations(self):
        self.sync()
        self.cli.calls.clear()
        self.sync()
        self.assertFalse(any(parts in (("canvas", "create"), ("resource", "upload")) or parts[:2] in (("node", "create"), ("node", "edit")) for parts, _ in self.cli.calls))

    def test_upload_response_loss_recovers_original_id(self):
        self.cli.fail_after = ("resource", "upload")
        with self.assertRaises(CLIError):
            self.sync()
        self.sync()
        self.assertEqual(len(self.cli.resources), 3)
        self.assertEqual(sum(parts == ("resource", "upload") for parts, _ in self.cli.calls), 3)

    def test_failure_before_upload_can_resume(self):
        self.cli.fail_before = ("resource", "upload")
        with self.assertRaises(CLIError):
            self.sync()
        self.assertEqual(len(self.sync().state["assets"]), 3)

    def test_canvas_created_but_response_lost(self):
        self.cli.fail_after = ("canvas", "create")
        with self.assertRaises(CLIError):
            self.sync()
        self.sync()
        self.assertEqual(sum(p == ("canvas", "create") for p, _ in self.cli.calls), 1)

    def test_node_created_but_response_lost(self):
        self.cli.fail_after = ("node", "create", "text")
        with self.assertRaises(CLIError):
            self.sync()
        self.assertEqual(self.sync().state["nodes"]["section:0"]["sync_status"], "synced")

    def test_hash_dedup_across_logical_ids(self):
        a = dict(self.p["assets"][0], asset_id="ALIAS")
        self.p["assets"].append(a)
        write_json(self.path, self.p)
        job = self.sync()
        self.assertEqual(len(self.cli.resources), 3)
        self.assertEqual(len(self.cli.nodes), 18)
        self.assertEqual(job.state["assets"]["CHAR01"][0]["canvas_node_id"], job.state["assets"]["ALIAS"][0]["canvas_node_id"])

    def test_local_originals_unchanged(self):
        hashes = {a["local_path"]: file_hash(self.root / a["local_path"]) for a in self.p["assets"]}
        self.sync()
        self.assertEqual(hashes, {p: file_hash(self.root / p) for p in hashes})

    def test_missing_file_report_and_product_filter(self):
        (self.root / self.p["assets"][0]["local_path"]).unlink()
        self.p["assets"].append(dict(self.p["assets"][2], asset_id="unused", sku_id="UNUSED", local_path="does-not-exist.png"))
        write_json(self.path, self.p)
        plan = self.job().plan()
        self.assertEqual(len(plan["missing"]), 1)
        self.assertEqual(plan["missing"][0]["reason"], "missing_file")

    def test_dry_run_no_client_or_state_writes(self):
        with patch("canvas_bootstrap.CanvasCLI", side_effect=AssertionError("No CLI in dry-run")), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["dry-run", "--production", str(self.path)]), 0)
        self.assertFalse(self.path.with_name("canvas_manifest.json").exists())

    def test_fallback_without_coordinates(self):
        self.cli.layout = False
        self.assertEqual(self.sync().state["organization_mode"], "name_prefixes")
        self.assertFalse(any("x" in flags for _, flags in self.cli.calls))

    def test_version_retains_old_approval_until_new_approved(self):
        job = self.sync()
        first = job.state["assets"]["CHAR01"][0]
        job.review("CHAR01", "v01", "approved", "fixture reviewer")
        other = self.root / "新生成.png"
        other.write_bytes(b"new version")
        v2 = job.register(dict(first, local_path=str(other), source_type="generated", file_hash=file_hash(other), qc_status="pending_review"))
        self.assertEqual(v2["version"], "v02")
        self.assertEqual(job.state["approved_versions"]["CHAR01"], "v01")
        job.sync_asset(v2, 1)
        job.review("CHAR01", "v02", "approved", "fixture approved v2")
        self.assertEqual(job.state["approved_versions"]["CHAR01"], "v02")
        self.assertIn(first["canvas_node_id"], self.cli.nodes)
        self.assertEqual(first["group_name"], GROUPS[8])
        self.assertEqual(job.register(dict(v2))["version"], "v02")
        self.assertIn("MIZAN_", Path(v2["local_path"]).name)

    def test_script_change_edits_existing_and_requires_version(self):
        self.sync()
        self.p["full_script"] += "\n确认增补"
        write_json(self.path, self.p)
        with self.assertRaisesRegex(ValueError, "script_version"):
            self.sync()
        self.p["script_version"] = "v02"
        write_json(self.path, self.p)
        job = self.sync()
        self.assertEqual(len(self.cli.nodes), 18)
        self.assertTrue(job.state["nodes"]["full_script"]["history"])

    def test_text_drift_detected_without_mutation(self):
        job = self.sync()
        nid = job.state["nodes"]["full_script"]["node_id"]
        self.cli.nodes[nid]["text"] = "external edit"
        self.cli.calls.clear()
        job.reconcile()
        self.assertEqual(job.state["nodes"]["full_script"]["sync_status"], "drifted")
        self.assertFalse(any(parts[:2] == ("node", "edit") for parts, _ in self.cli.calls))

    def test_paid_task_record_and_recovery_only_queries(self):
        job = self.sync()
        task = record_task(job, "P01-video-v01", "node_test", "live-model", {"duration": 4})
        self.assertEqual(task, record_task(job, "P01-video-v01", "node_test", "live-model", {"duration": 4}))
        self.cli.calls.clear()
        job.reconcile()
        self.assertEqual(job.state["tasks"]["P01-video-v01"]["remote_state"], "unknown")
        self.assertIn(("operation", "status"), [p for p, _ in self.cli.calls])
        self.assertNotIn(("node", "run"), [p for p, _ in self.cli.calls])
        with self.assertRaises(ValueError):
            record_task(job, "bad", "node_test", "live", {"access_token": "DO_NOT_SAVE"})
        self.assertNotIn("DO_NOT_SAVE", job.state_path.read_text(encoding="utf-8"))

    def test_downstream_rejects_unapproved_and_missing_audio(self):
        job = self.sync()
        with self.assertRaises(ValueError):
            build_plan(self.p, job.state, "video")
        with self.assertRaises(ValueError):
            build_plan(self.p, job.state, "capcut")

    def test_declared_approved_inputs_need_evidence(self):
        self.p["assets"][0]["qc_status"] = "approved"
        write_json(self.path, self.p)
        with self.assertRaisesRegex(ValueError, "qc_evidence"):
            self.job()

    def test_changed_original_invalidates_approved_handoff(self):
        job = self.sync()
        job.review("CHAR01", "v01", "approved", "fixture")
        (self.root / self.p["assets"][0]["local_path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            approved(job.state, "CHAR01")

    def test_windows_naming(self):
        self.assertEqual(safe_filename('门店:灯/串?<>"|*'), "门店_灯_串______")
        self.assertEqual(safe_filename("CON"), "_CON")
        a = self.p["assets"][0]
        name = display_name(a, {"version": "v01", "qc_status": "pending_check"})
        self.assertEqual(name, "角色01｜人物参考｜模拟人物参考｜原有｜v01｜待核对")
        self.assertNotIn("待核对", generated_filename(a, "v02", ".png"))

    def test_docx_text_not_guessed(self):
        path = self.root / "脚本.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>原文西语 ñ ¿</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>中文对照</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        data = extract_docx(path)
        self.assertEqual(data["full_text"], "原文西语 ñ ¿\n中文对照")
        self.assertTrue(data["requires_structured_mapping"])

    def test_live_cli_rich_text_entity_roundtrip(self):
        self.assertEqual(node_text({"text": '  西语 &amp; 中文\n&#32;&#32;"shot_id": "P01"'}), '  西语 & 中文\n  "shot_id": "P01"')

    def test_schema_checked_flags_and_paid_rejection(self):
        cli = object.__new__(CanvasCLI)
        cli.spec = {"subcommands": [{"name": "node", "subcommands": [{"name": "run", "flags": []}]}]}
        with self.assertRaises(ValueError):
            cli.call(("node", "run"))
        with self.assertRaises(ValueError):
            cli.call(("private", "upload"))

    def test_live_cli_structured_errors_on_stderr(self):
        cli = object.__new__(CanvasCLI)
        cli.spec = None
        cli.executable, cli.timeout, cli.requests = "fixture", 1, []
        result = SimpleNamespace(stdout="", stderr=json.dumps({"ok": False, "error": {"code": "service.6", "class": "invalid_input"}}), returncode=1)
        with patch("canvas_bootstrap.subprocess.run", return_value=result), self.assertRaises(CLIError) as caught:
            cli.call(("version",))
        self.assertEqual(caught.exception.error["code"], "service.6")

    def new_character_version(self, job):
        other = self.root / "新版本.png"
        other.write_bytes(b"new character fixture")
        first = job.state["assets"]["CHAR01"][0]
        v = job.register(dict(first, local_path=str(other), file_hash=file_hash(other), source_type="generated", qc_status="pending_review"))
        job.sync_asset(v, 1)
        return v

    def test_register_cannot_approve_without_evidence(self):
        job = self.sync()
        asset = dict(job.state["assets"]["CHAR01"][0], file_hash="changed", qc_status="approved", qc_evidence=None)
        with self.assertRaisesRegex(ValueError, "qc_evidence"):
            job.register(asset)
        self.assertFalse(job.state["approved_versions"])

    def test_review_rollback_restores_active_region(self):
        job = self.sync()
        job.review("CHAR01", "v01", "approved", "fixture")
        self.new_character_version(job)
        job.review("CHAR01", "v02", "approved", "fixture")
        job.review("CHAR01", "v01", "approved", "rollback fixture")
        self.assertEqual(job.state["assets"]["CHAR01"][0]["group_name"], GROUPS[1])
        self.assertEqual(job.state["assets"]["CHAR01"][1]["group_name"], GROUPS[8])

    def test_review_response_loss_recovers_old_archival_intent(self):
        job = self.sync()
        job.review("CHAR01", "v01", "approved", "fixture")
        self.new_character_version(job)
        self.cli.fail_after = ("node", "edit", "image")
        with self.assertRaises(CLIError):
            job.review("CHAR01", "v02", "approved", "fixture")
        job = self.sync()
        old = job.state["assets"]["CHAR01"][0]
        self.assertEqual(old["group_name"], GROUPS[8])
        self.assertEqual(old["metadata_sync_status"], "synced")
        self.assertEqual(self.cli.nodes[old["canvas_node_id"]]["layout"]["x"], 8 * 2600)

    def test_alias_review_does_not_rename_owner_node(self):
        alias = dict(self.p["assets"][0], asset_id="ALIAS", description="另一中文描述")
        self.p["assets"].append(alias)
        write_json(self.path, self.p)
        job = self.sync()
        owner = job.state["assets"]["CHAR01"][0]
        expected = self.cli.nodes[owner["canvas_node_id"]]["title"]
        job.review("ALIAS", "v01", "approved", "fixture alias approval")
        self.assertEqual(self.cli.nodes[owner["canvas_node_id"]]["title"], expected)

    def test_later_version_sharing_an_existing_hash_keeps_original_owner(self):
        job = self.sync()
        scene = job.state["assets"]["SCENE_STORE"][0]
        character = job.state["assets"]["CHAR01"][0]
        v2 = job.register(dict(character, local_path=scene["local_path"], file_hash=scene["file_hash"], qc_status="pending_review"))
        job.sync_asset(v2, 0)
        expected = self.cli.nodes[scene["canvas_node_id"]]["title"]
        job.review("CHAR01", "v02", "approved", "fixture approval")
        self.assertEqual(self.cli.nodes[scene["canvas_node_id"]]["title"], expected)
        self.assertEqual(job.node_owner(v2["canvas_node_id"])["asset_id"], "SCENE_STORE")

    def test_positive_downstream_approved_refs_and_no_subtitles(self):
        job = self.sync()
        # Isolated fixture approval, never a real user's creative QC.
        for aid in list(job.state["assets"]):
            job.review(aid, "v01", "approved", "offline fixture approval")
        for asset in self.p["outputs"]:
            path = self.root / (asset["asset_id"] + (".mp4" if asset["asset_type"] == "video" else ".png"))
            path.write_bytes(asset["asset_id"].encode())
            v = job.register(dict(asset, local_path=str(path), file_hash=file_hash(path), source_type="generated", qc_status="pending_review",
                                  media_type="video" if asset["asset_type"] == "video" else "image"))
            job.sync_asset(v, 0)
            job.review(asset["asset_id"], "v01", "approved", "offline fixture approval")
        for shot in self.p["shots"]:
            shot.update(audio_role="none", audio_ref=None, lip_sync_required=False)
        video_plan = build_plan(self.p, job.state, "video")
        self.assertEqual(video_plan["canvas_project_id"], job.state["canvas_project_id"])
        self.assertTrue(all(r.startswith("node:") for s in video_plan["shots"] for r in s["refs"]))
        capcut_plan = build_plan(self.p, job.state, "capcut")
        self.assertEqual([s["shot_id"] for s in capcut_plan["shots"]], ["P01", "P02", "P03"])
        self.assertEqual(capcut_plan["subtitle_tracks"], [])
        self.assertEqual(capcut_plan["shots"][-1]["end_s"], 12)


if __name__ == "__main__":
    unittest.main()
