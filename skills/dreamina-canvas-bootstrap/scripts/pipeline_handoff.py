#!/usr/bin/env python3
"""Build approved-only stage plans; journal paid submissions BEFORE an external authorized CLI run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from canvas_bootstrap import (Bootstrap, CLIError, file_hash, generated_filename, now, project_lock,
                              read_json, write_json)


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


def build_plan(production, state, stage):
    if production["project_id"] != state["project_id"]:
        raise ValueError("Project IDs differ")
    records, timeline = [], 0.0
    for shot in production["shots"]:
        record = {"shot_id": shot["shot_id"], "canvas_project_id": state["canvas_project_id"],
                  "generation_strategy": shot["generation_strategy"], "duration": shot["duration"]}
        if stage == "video":
            image = approved(state, shot.get("approved_asset_id"), {"storyboard_image", "first_frame", "scene_anchor"})
            refs = [image["canvas_node_id"]]
            for identifier, kinds in ((shot.get("character_id"), {"character"}), (shot.get("scene_anchor_id"), {"scene_anchor"})):
                if identifier:
                    refs.append(approved(state, identifier, kinds)["canvas_node_id"])
            for sku in shot["product_refs"]:
                candidates = [aid for aid, vs in state["assets"].items() if any(v.get("sku_id") == sku for v in vs)]
                if len(candidates) != 1:
                    raise ValueError("Missing or ambiguous real SKU reference: " + sku)
                refs.append(approved(state, candidates[0], {"product"})["canvas_node_id"])
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
                audio = approved(state, shot["audio_ref"], {"audio"})
                refs.append(audio["canvas_node_id"])
                record["canvas_audio_node_id"] = audio["canvas_node_id"]
                record["audio_file"] = audio["local_path"]
                record["requires_live_model_validation"] = "audio_reference_type_count_duration_and_mode"
            record.update(source_image_id=image["asset_id"], version=image["version"],
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
    parser.add_argument("mode", choices=["video", "capcut", "record-task"])
    parser.add_argument("--production", required=True, type=Path)
    parser.add_argument("--canvas", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--task-key")
    parser.add_argument("--node-id")
    parser.add_argument("--model")
    parser.add_argument("--parameters", type=Path)
    args = parser.parse_args()
    with project_lock((args.canvas or args.production.with_name("canvas_manifest.json")).with_suffix(".lock")):
        job = Bootstrap(args.production, state_path=args.canvas)
        if args.mode == "record-task":
            if not all((args.task_key, args.node_id, args.model, args.parameters)):
                parser.error("record-task needs --task-key --node-id --model --parameters")
            result = record_task(job, args.task_key, args.node_id, args.model, read_json(args.parameters))
        else:
            result = build_plan(job.production, job.state, args.mode)
        write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "paid_operations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, CLIError, KeyError, OSError) as error:
        raise SystemExit(str(error))
