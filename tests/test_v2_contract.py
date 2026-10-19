"""Review regressions: synthetic files only, no network or billable operation."""
import copy
import json
from pathlib import Path
import unittest
import zipfile
from xml.sax.saxutils import escape

import test_canvas_bootstrap as fixtures
from canvas_bootstrap import extract_docx, generated_filename, validate_production, write_json, file_hash
from canvas_preview import preview_status, require_preview
from pipeline_handoff import build_plan
from production_contract import normalize_production, image_contract_errors


class ContractTests(unittest.TestCase):
    setUp = fixtures.BootstrapTests.setUp
    job = fixtures.BootstrapTests.job
    sync = fixtures.BootstrapTests.sync

    def preview(self, job):
        job.approve_preview("synthetic owner", "offline test, not creative approval", owner_confirmed=True)

    def inputs(self, job):
        for aid in list(job.state["assets"]): job.review(aid, "v01", "approved", "synthetic input QC")

    def output(self, job, aid, kind="storyboard_image"):
        path = self.root / (aid + ".png")
        path.write_bytes(aid.encode())
        v = job.register(dict(asset_id=aid, asset_type=kind, description=aid, local_path=str(path),
                              file_hash=file_hash(path), source_type="generated", qc_status="pending_review", media_type="image"))
        job.sync_asset(v, 0)
        job.review(aid, "v01", "approved", "synthetic output QC")
        return v

    def test_owner_alias_is_lossless_and_conflicts_stop(self):
        p = copy.deepcopy(self.p)
        p["owner_confirmed"] = p.pop("confirmed_by_owner")
        self.assertTrue(validate_production(p)["confirmed_by_owner"])
        self.assertIn("owner_confirmed", p)
        p["confirmed_by_owner"] = False
        with self.assertRaisesRegex(ValueError, "Conflicting aliases"): normalize_production(p)

    def test_missing_stages_and_untyped_reference_lists_rejected(self):
        s = copy.deepcopy(self.p["shots"][0])
        del s["image_generation"]
        self.assertTrue(image_contract_errors(s))
        s = copy.deepcopy(self.p["shots"][0])
        s["image_generation"]["anchor"]["reference_asset_ids"] = "SCENE_STORE"
        self.assertTrue(image_contract_errors(s))

    def test_all_production_plans_require_project_preview(self):
        job = self.sync()
        for stage in ("image-anchor", "image-incremental", "video", "capcut"):
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, "PREVIEW_APPROVAL_REQUIRED"):
                build_plan(job.production, job.state, stage)

    def test_owner_confirmation_not_inferred_from_sync(self):
        job = self.sync()
        self.assertEqual(preview_status(self.p, job.state)["status"], "CANVAS_PREVIEW_PENDING")
        with self.assertRaises(ValueError): job.approve_preview("test", "test")
        self.preview(job)
        self.assertEqual(preview_status(self.p, job.state)["status"], "CANVAS_PREVIEW_APPROVED")
        self.assertTrue(job.state["canvas_preview"]["material_manifest_version"].startswith("sha256:"))

    def test_changed_input_invalidates_preview_not_immutable_history(self):
        job = self.sync()
        self.inputs(job)
        self.preview(job)
        old = Path(job.state["assets"]["CHAR01"][0]["local_path"])
        (self.root / self.p["assets"][0]["local_path"]).write_bytes(b"new original")
        self.assertEqual(old.read_bytes(), b"fixture-0")
        with self.assertRaisesRegex(ValueError, "PREVIEW_REVIEW_REQUIRED"): require_preview(self.p, job.state)

    def test_affected_shots_can_be_reviewed_without_blocking_others(self):
        job = self.sync()
        self.preview(job)
        (self.root / self.p["assets"][2]["local_path"]).write_bytes(b"new SKU")
        result = require_preview(self.p, job.state, ["P01"])
        self.assertEqual(result["affected_shot_ids"], ["P02", "P03"])
        with self.assertRaises(ValueError): require_preview(self.p, job.state, ["P02"])

    def test_script_and_prompt_changes_invalidate_preview(self):
        job = self.sync()
        self.preview(job)
        p = copy.deepcopy(self.p)
        p["shots"][0]["image_generation"]["anchor"]["prompt"] += "new"
        with self.assertRaisesRegex(ValueError, "PREVIEW_REVIEW_REQUIRED"): require_preview(p, job.state)

    def test_shot_order_alone_invalidates_preview(self):
        self.p["assets"] = []
        for shot in self.p["shots"]: shot["product_refs"] = []
        write_json(self.path, self.p)
        job = self.sync()
        self.preview(job)
        p = copy.deepcopy(self.p)
        p["shots"].reverse()
        with self.assertRaisesRegex(ValueError, "shot_order"): require_preview(p, job.state)
        p = copy.deepcopy(self.p)
        p["script_version"] = "v02"
        with self.assertRaisesRegex(ValueError, "PREVIEW_REVIEW_REQUIRED"): require_preview(p, job.state)

    def test_new_output_approval_does_not_reset_input_preview(self):
        job = self.sync()
        self.preview(job)
        self.output(job, "ANCHOR_STORE", "scene_anchor")
        self.assertEqual(require_preview(self.p, job.state)["status"], "CANVAS_PREVIEW_APPROVED")

    def test_anchor_queue_deduplicates_and_keeps_prompt_bytes(self):
        text = "  ¿Tienda? ñ\n保持原文，禁止重写。  "
        for s in self.p["shots"][:2]: s["image_generation"]["anchor"]["prompt"] = text
        write_json(self.path, self.p)
        job = self.sync()
        self.inputs(job)
        self.preview(job)
        plan = build_plan(self.p, job.state, "image-anchor")
        self.assertEqual(len(plan["tasks"]), 2)
        self.assertEqual(plan["tasks"][0]["shot_ids"], ["P01", "P02"])
        self.assertEqual(plan["tasks"][0]["prompt"], text)
        self.assertEqual(plan["tasks"][0]["negative_prompt"], self.p["shots"][0]["image_generation"]["anchor"]["negative_prompt"])

    def test_incremental_requires_approved_anchor_and_real_sku(self):
        job = self.sync()
        self.inputs(job)
        self.preview(job)
        with self.assertRaisesRegex(ValueError, "ANCHOR_STORE"): build_plan(self.p, job.state, "image-incremental", ["P02"])
        self.output(job, "ANCHOR_STORE", "scene_anchor")
        task = build_plan(self.p, job.state, "image-incremental", ["P02"])["tasks"][0]
        self.assertEqual(task["reference_asset_ids"], ["ANCHOR_STORE", "CHAR01", "PRODUCT_DEMO"])
        self.assertEqual(task["keep_fixed"], self.p["shots"][1]["image_generation"]["incremental"]["keep_fixed"])
        self.assertTrue(all(Path(p).is_file() for p in task["reference_files"]))

    def test_start_end_two_independent_approvals_and_frame_order(self):
        s = self.p["shots"][0]
        s.update(generation_strategy="START_END_FRAME", image_count=2, image_asset_ids=["FIRST", "LAST"],
                 start_frame_asset_id="FIRST", end_frame_asset_id="LAST", audio_role="none", lip_sync_required=False)
        recipe = s["image_generation"].pop("incremental")
        s["image_generation"]["start"] = dict(recipe, output_asset_ids=["FIRST"], prompt="首帧原文")
        s["image_generation"]["end"] = dict(recipe, output_asset_ids=["LAST"], prompt="尾帧原文")
        write_json(self.path, self.p)
        self.assertFalse(image_contract_errors(s))
        job = self.sync()
        self.inputs(job)
        self.preview(job)
        self.output(job, "ANCHOR_STORE", "scene_anchor")
        self.output(job, "FIRST", "first_frame")
        with self.assertRaisesRegex(ValueError, "LAST"): build_plan(self.p, job.state, "video", ["P01"])
        self.output(job, "LAST", "last_frame")
        record = build_plan(self.p, job.state, "video", ["P01"])["shots"][0]
        self.assertEqual(record["source_image_ids"], ["FIRST", "LAST"])
        self.assertEqual(record["frame_roles"], ["first", "last"])
        self.assertEqual(record["mode"], "first_last_frame")
        s.update(audio_role="dialogue", audio_ref="AUDIO", lip_sync_required=True)
        job.production["shots"][0].update(audio_role="dialogue", audio_ref="AUDIO", lip_sync_required=True)
        self.p["script_version"] = job.production["script_version"] = "v02"
        job.script()
        self.preview(job)
        with self.assertRaisesRegex(ValueError, "prepared audio is blocked"): build_plan(self.p, job.state, "video", ["P01"])
        s["image_asset_ids"].reverse()
        self.assertTrue(image_contract_errors(s))

    def test_start_end_same_content_cannot_collapse_two_frame_slots(self):
        s = self.p["shots"][0]
        s.update(generation_strategy="START_END_FRAME", image_count=2, image_asset_ids=["FIRST", "LAST"],
                 start_frame_asset_id="FIRST", end_frame_asset_id="LAST", audio_role="none", lip_sync_required=False)
        recipe = s["image_generation"].pop("incremental")
        s["image_generation"]["start"] = dict(recipe, output_asset_ids=["FIRST"])
        s["image_generation"]["end"] = dict(recipe, output_asset_ids=["LAST"])
        write_json(self.path, self.p)
        job = self.sync()
        self.inputs(job)
        self.preview(job)
        self.output(job, "ANCHOR_STORE", "scene_anchor")
        first = self.output(job, "FIRST", "first_frame")
        v = job.register(dict(first, asset_id="LAST", asset_type="last_frame", qc_status="pending_review"))
        job.sync_asset(v, 0)
        job.review("LAST", "v01", "approved", "synthetic QC")
        with self.assertRaisesRegex(ValueError, "distinct physical frame"): build_plan(self.p, job.state, "video", ["P01"])

    def test_multi_image_execution_preserves_declared_order(self):
        s = self.p["shots"][0]
        s.update(generation_strategy="MULTI_REFERENCE", image_count=3, image_asset_ids=["X", "Y", "Z"], audio_role="none", lip_sync_required=False)
        s["image_generation"] = {"direct": dict(s["image_generation"]["incremental"], output_asset_ids=["X", "Y", "Z"])}
        write_json(self.path, self.p)
        job = self.sync()
        self.inputs(job)
        self.preview(job)
        self.output(job, "ANCHOR_STORE", "scene_anchor")
        for aid in s["image_asset_ids"]: self.output(job, aid)
        self.assertEqual(build_plan(self.p, job.state, "video", ["P01"])["shots"][0]["source_image_ids"], ["X", "Y", "Z"])

    def test_ensure_canvas_preserves_synced_status(self):
        job = self.sync()
        job.ensure_canvas()
        self.assertEqual(job.state["sync_status"], "synced")

    def test_media_title_and_location_drift_detected_then_repaired(self):
        job = self.sync()
        v = job.state["assets"]["CHAR01"][0]
        nid = v["canvas_node_id"]
        expected = copy.deepcopy(self.cli.nodes[nid])
        self.cli.nodes[nid]["title"] = "wrong v99"
        self.cli.nodes[nid]["layout"]["x"] += 900
        job.reconcile()
        self.assertIn("position", v["drift_issues"])
        self.assertIn("display_name_or_version_status", v["drift_issues"])
        self.sync(job)
        self.assertEqual(self.cli.nodes[nid]["title"], expected["title"])
        self.assertEqual(self.cli.nodes[nid]["layout"]["x"], expected["layout"]["x"])

    def test_drift_blocks_preview_approved_production(self):
        job = self.sync()
        self.preview(job)
        self.cli.nodes[job.state["nodes"]["full_script"]["node_id"]]["text"] = "drift"
        job.reconcile()
        with self.assertRaisesRegex(ValueError, "CANVAS_SYNC_REQUIRED"): require_preview(self.p, job.state)

    def test_missing_original_recovers_from_verified_snapshot(self):
        job = self.sync()
        (self.root / self.p["assets"][0]["local_path"]).unlink()
        plan = job.plan()
        self.assertFalse(plan["missing"])
        self.assertTrue(plan["assets"][0]["source_missing_using_snapshot"])
        self.sync(job)
        self.assertEqual(len(job.state["assets"]["CHAR01"]), 1)

    def test_filename_truncates_description_not_identity_version(self):
        a = dict(self.p["assets"][0], asset_id="ID_" + "A" * 135, description="超长描述" * 200)
        name = generated_filename(a, "v123", ".png")
        self.assertIn(a["asset_id"], name)
        self.assertTrue(name.endswith("_v123.png"))
        self.assertLessEqual(len(name.encode("utf-16-le")) // 2, 240)

    def test_docx_explicit_cells_map_complete_manifest_with_provenance(self):
        def table(pairs):
            return "<w:tbl>" + "".join("<w:tr>" + "".join("<w:tc><w:p><w:r><w:t xml:space='preserve'>" + escape(v) + "</w:t></w:r></w:p></w:tc>" for v in pair) + "</w:tr>" for pair in pairs) + "</w:tbl>"
        def literal(v): return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        p = copy.deepcopy(self.p)
        p["owner_confirmed"] = p.pop("confirmed_by_owner")
        body = table([(k, literal(v)) for k, v in p.items() if k != "shots"])
        for s in p["shots"]: body += table([(k, literal(v)) for k, v in s.items()])
        path = self.root / "模板2.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')
        data = extract_docx(path)
        self.assertFalse(data["requires_structured_mapping"], data)
        self.assertEqual(data["production"]["shots"][0]["image_generation"], p["shots"][0]["image_generation"])
        self.assertTrue(data["production"]["source_provenance"])


if __name__ == "__main__": unittest.main()
