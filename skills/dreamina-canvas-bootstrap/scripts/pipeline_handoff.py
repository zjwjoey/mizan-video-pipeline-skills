#!/usr/bin/env python3
"""Build approved-only stage plans; journal paid submissions BEFORE an external authorized CLI run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from canvas_bootstrap import (Bootstrap, CLIError, file_hash, generated_filename, now, project_lock,
                              read_json, write_json)
from canvas_preview import require_preview
from production_contract import canonical_strategy


def approved(state, asset_id, expected_type=None):
    selected = state["approved_versions"].get(asset_id)
    v = next((v for v in state["assets"].get(asset_id, []) if v["version"] == selected), None)
    if not v or v["qc_status"] != "approved" or not v.get("qc_evidence") or v["sync_status"] != "synced":
        raise ValueError("No approved, synchronized version: " + str(asset_id))
    if expected_type and v["asset_type"] not in expected_type:
        raise ValueError("Wrong asset type: " + asset_id)
    path = Path(v["local_path"])
    if not path.is_file() or file_hash(path) != v["file_hash"]:
        raise ValueError("Approved source is missing or changed: " + str(path))
    if not v.get("canvas_node_id") or not v.get("canvas_resource_id"):
        raise ValueError("Approved source has no Canvas mapping: " + asset_id)
    return v


def build_image_tasks(production, state, stage, shot_ids=None):
    require_preview(production, state, shot_ids)
    tasks = {}
    for shot in production["shots"]:
        if shot_ids and shot["shot_id"] not in shot_ids: continue
        strategy = canonical_strategy(shot["generation_strategy"])
        names = ["anchor"] if stage == "image-anchor" else (["start", "end"] if strategy == "START_END_FRAME" else ["direct"] if strategy in ("DIRECT_PRODUCT", "MULTI_REFERENCE") else ["incremental"] if strategy != "ANCHOR_ONLY" else [])
        for name in names:
            spec = shot["image_generation"].get(name)
            if spec is None: continue
            if spec.get("reuse_asset_id"):
                approved(state, spec["reuse_asset_id"], {"scene_anchor"})
                continue
            for output_id in spec["output_asset_ids"]:
                if output_id in state["approved_versions"]:
                    approved(state, output_id)
                    continue
                refs = list(spec["reference_asset_ids"])
                if spec.get("base_asset_id"):
                    refs.insert(0, spec["base_asset_id"])
                refs = list(dict.fromkeys(refs))
                sources = [approved(state, aid, {"character", "scene", "product", "scene_anchor", "storyboard_image", "first_frame", "last_frame"}) for aid in refs]
                if name != "anchor":
                    for sku in shot["product_refs"]:
                        if not any(v.get("sku_id") == sku for v in sources):
                            raise ValueError(shot["shot_id"] + ": explicit stage reference missing real SKU " + sku)
                    if "CHARACTER" in strategy and shot["character_id"] not in refs:
                        raise ValueError("Incremental reference must include the declared character")
                task = {"stage": name, "output_asset_id": output_id, "prompt": spec.get("output_prompts", {}).get(output_id, spec["prompt"]),
                        "negative_prompt": spec["negative_prompt"], "keep_fixed": spec["keep_fixed"], "add_elements": spec["add_elements"],
                        "reference_asset_ids": refs, "refs": ["node:" + v["canvas_node_id"] for v in sources],
                        "reference_files": [v["local_path"] for v in sources], "base_asset_id": spec.get("base_asset_id"),
                        "canvas_project_id": state["canvas_project_id"]}
                if output_id in tasks and any(tasks[output_id][k] != v for k, v in task.items()):
                    raise ValueError("Conflicting recipes for shared output: " + output_id)
                task["shot_ids"] = list(dict.fromkeys(tasks.get(output_id, {}).get("shot_ids", []) + [shot["shot_id"]]))
                tasks[output_id] = task
    return {"schema_version": 2, "stage": stage, "project_id": production["project_id"],
            "canvas_project_id": state["canvas_project_id"], "tasks": list(tasks.values()), "paid_operations": 0}


def build_plan(production, state, stage, shot_ids=None):
    if production["project_id"] != state["project_id"]:
        raise ValueError("Project IDs differ")
    require_preview(production, state, shot_ids)
    if stage in ("image-anchor", "image-incremental"):
        return build_image_tasks(production, state, stage, shot_ids)
    records, timeline = [], 0.0
    for shot in production["shots"]:
        if shot_ids and shot["shot_id"] not in shot_ids: continue
        record = {"shot_id": shot["shot_id"], "canvas_project_id": state["canvas_project_id"],
                  "generation_strategy": shot["generation_strategy"], "duration": shot["duration"]}
        if stage == "video":
            strategy = canonical_strategy(shot["generation_strategy"])
            images = shot["image_asset_ids"]
            if strategy == "START_END_FRAME":
                if images != [shot.get("start_frame_asset_id"), shot.get("end_frame_asset_id")] or len(set(images)) != 2:
                    raise ValueError("START_END_FRAME needs distinct ordered approved start/end IDs")
            if len(images) != shot["image_count"] or not images:
                raise ValueError("Execution-image count/mapping mismatch: " + shot["shot_id"])
            visuals = [approved(state, aid, {"storyboard_image", "first_frame", "last_frame", "scene_anchor"}) for aid in images]
            if strategy == "START_END_FRAME" and (visuals[0]["file_hash"] == visuals[1]["file_hash"] or visuals[0]["canvas_node_id"] == visuals[1]["canvas_node_id"]):
                raise ValueError("START_END_FRAME needs distinct physical frame contents/nodes; deduplicated identical frames are not two references")
            refs = [v["canvas_node_id"] for v in visuals]
            context = []
            for identifier, kinds in ((shot.get("character_id"), {"character"}), (shot.get("scene_anchor_id"), {"scene_anchor"})):
                if identifier:
                    context.append(approved(state, identifier, kinds)["canvas_node_id"])
            for sku in shot["product_refs"]:
                candidates = [aid for aid, vs in state["assets"].items() if any(v.get("sku_id") == sku for v in vs)]
                if len(candidates) != 1:
                    raise ValueError("Missing or ambiguous real SKU reference: " + sku)
                context.append(approved(state, candidates[0], {"product"})["canvas_node_id"])
            if strategy != "START_END_FRAME": refs += context
            role = shot["audio_role"]
            if role not in ("dialogue", "narration", "none"):
                raise ValueError(shot["shot_id"] + ": explicitly select dialogue, narration or none")
            if role == "dialogue" and shot["lip_sync_required"] is not True:
                raise ValueError("Visible dialogue requires explicit lip sync")
            if role == "narration" and shot["lip_sync_required"] is not False:
                raise ValueError("Narration requires lip_sync_required=false")
            if role == "none":
                if shot["audio_ref"] is not None or shot["lip_sync_required"] is not False:
                    raise ValueError("No-audio mode requires audio_ref=null and lip_sync_required=false")
                record["requires_live_model_validation"] = "explicit_silent_mode_support"
            else:
                if strategy == "START_END_FRAME":
                    raise ValueError("START_END_FRAME with prepared audio is blocked: current public first_last_frame permits only the two image references; a verified audio-capable adapter is required")
                audio = approved(state, shot["audio_ref"], {"audio"})
                refs.append(audio["canvas_node_id"])
                record["canvas_audio_node_id"] = audio["canvas_node_id"]
                record["audio_file"] = audio["local_path"]
                record["requires_live_model_validation"] = "audio_reference_type_count_duration_and_mode"
            record.update(source_image_id=visuals[0]["asset_id"], source_image_ids=images,
                          image_versions={v["asset_id"]: v["version"] for v in visuals}, version=visuals[0]["version"],
                          mode="first_last_frame" if strategy == "START_END_FRAME" else "m2v",
                          frame_refs=["node:" + v["canvas_node_id"] for v in visuals],
                          context_refs=["node:" + r for r in dict.fromkeys(context)],
                          frame_roles=["first", "last"] if strategy == "START_END_FRAME" else ["reference"] * len(visuals),
                          audio_role=role, lip_sync_required=shot["lip_sync_required"],
                          voiceover_es=shot["voiceover_es"], motion_intention=shot["motion_intention"],
                          refs=["node:" + r for r in dict.fromkeys(refs)])
        elif stage == "capcut":
            video = approved(state, shot.get("video_asset_id"), {"video"})
            record.update(id=shot["shot_id"], video=video["local_path"], start_s=timeline,
                          end_s=timeline + shot["duration"], audio_role=shot["audio_role"],
                          version=video["version"], canvas_node_id=video["canvas_node_id"])
            if production.get("subtitles", {}).get("enabled"):
                record["captions"] = {}
                for language in production["subtitles"]["languages"]:
                    text = shot.get("subtitle_" + language)
                    if not isinstance(text, str) or not text:
                        raise ValueError("Explicit subtitle text missing: " + shot["shot_id"] + "." + language)
                    record["captions"][language] = text
            timeline += shot["duration"]
        else:
            raise ValueError("Unknown handoff stage")
        records.append(record)
    return {"schema_version": 2, "project_id": production["project_id"], "canvas_project_id": state["canvas_project_id"],
            "stage": stage, "shots": records, "subtitles_enabled": production.get("subtitles", {}).get("enabled", False),
            "subtitle_tracks": production.get("subtitles", {}).get("languages", []) if production.get("subtitles", {}).get("enabled") else [],
            **production.get("format", {}), "paid_operations": 0}


def record_task(job, key, node_id, model, parameters):
    """Preparation only. Never submit automatically, including during resume."""
    require_preview(job.production, job.state)
    allowed = {"mode", "prompt", "ratio", "resolution", "duration", "refs", "audio_role", "lip_sync_required", "count", "shot_id", "version"}
    if not set(parameters) <= allowed:
        raise ValueError("Only public generation parameters may be journaled; no tokens/provider payloads")
    if any(not ref.startswith(("node:", "res:")) for ref in parameters.get("refs", [])):
        raise ValueError("Journal references must use public node/resource IDs, not signed URLs")
    tasks = job.state["tasks"]
    if key in tasks:
        task = tasks[key]
        if task["canvas_node_id"] != node_id or task["model"] != model or task["parameters"] != parameters:
            raise ValueError("Task key already bound to different inputs; new intentional revision needs a new key")
        return task
    task = {"task_key": key, "canvas_node_id": node_id, "submit_id": str(uuid.uuid4()), "model": model,
            "parameters": parameters, "state": "prepared_not_submitted", "created_at": now(),
            "recovery_action": "query_same_submit_id_only"}
    tasks[key] = task
    job.save()
    return task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["image-anchor", "image-incremental", "video", "capcut", "record-task"])
    parser.add_argument("--production", required=True, type=Path)
    parser.add_argument("--canvas", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--task-key")
    parser.add_argument("--node-id")
    parser.add_argument("--model")
    parser.add_argument("--parameters", type=Path)
    parser.add_argument("--shot-id", action="append")
    args = parser.parse_args()
    with project_lock((args.canvas or args.production.with_name("canvas_manifest.json")).with_suffix(".lock")):
        job = Bootstrap(args.production, state_path=args.canvas)
        if args.mode == "record-task":
            if not all((args.task_key, args.node_id, args.model, args.parameters)):
                parser.error("record-task needs --task-key --node-id --model --parameters")
            result = record_task(job, args.task_key, args.node_id, args.model, read_json(args.parameters))
        else:
            result = build_plan(job.production, job.state, args.mode, args.shot_id)
        write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "paid_operations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, CLIError, KeyError, OSError) as error:
        raise SystemExit(str(error))
