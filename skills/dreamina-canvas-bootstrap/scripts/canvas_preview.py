"""Project-level owner preview gate, bound to exact script and selected input bytes."""
import hashlib
import json
from pathlib import Path


def signature(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def preview_snapshot(production, state):
    shots = production["shots"]
    sku_ids = {sku for s in shots for sku in s["product_refs"]}
    inputs = {}
    for a in production["assets"]:
        if a["asset_type"] == "product" and a.get("sku_id") not in sku_ids: continue
        consumers = [s["shot_id"] for s in shots if s["shot_id"] == a.get("shot_id") or s["shot_id"] in a.get("shot_ids", [])
                     or a.get("sku_id") in s["product_refs"] or a["asset_id"] in (s.get("scene_id"), s.get("character_id"), s.get("audio_ref"))]
        if a.get("shot_id") and not consumers: continue
        versions = state.get("assets", {}).get(a["asset_id"], [])
        chosen = next((v for v in versions if v["version"] == state.get("approved_versions", {}).get(a["asset_id"])), None)
        chosen = chosen or (versions[-1] if versions else {})
        source = Path(state.get("production_root", ".")) / a["local_path"]
        inputs[a["asset_id"]] = {"declared_hash": hash_file(source) if source.is_file() else chosen.get("file_hash", "missing"),
                                "selected_hash": chosen.get("file_hash", "not_registered"), "selected_version": chosen.get("version"),
                                "description": a["description"], "type": a["asset_type"], "consumers": consumers or [s["shot_id"] for s in shots]}
    project = {k: production.get(k) for k in ("project_id", "topic", "script_version", "full_script", "format", "subtitles", "production_rules")}
    return {"project": signature(project), "script_version": production["script_version"], "shot_order": [s["shot_id"] for s in shots],
            "shots": {s["shot_id"]: signature(s) for s in shots}, "inputs": inputs,
            "material_manifest_version": "sha256:" + signature(inputs)}


def preview_changes(previous, current):
    affected, changed = set(), []
    if not previous or previous.get("project") != current["project"]:
        affected.update(current["shots"])
        changed.append("project_script_or_rules")
    if (previous or {}).get("shot_order") != current["shot_order"]:
        affected.update(current["shots"])
        changed.append("shot_order")
    for sid in set((previous or {}).get("shots", {})) | set(current["shots"]):
        if (previous or {}).get("shots", {}).get(sid) != current["shots"].get(sid):
            affected.add(sid)
            changed.append("shot:" + sid)
    old = (previous or {}).get("inputs", {})
    for aid in set(old) | set(current["inputs"]):
        if old.get(aid) != current["inputs"].get(aid):
            affected.update(old.get(aid, {}).get("consumers", []))
            affected.update(current["inputs"].get(aid, {}).get("consumers", []))
            changed.append("asset:" + aid)
    return {"changed_components": sorted(changed), "affected_shot_ids": sorted(affected)}


def preview_status(production, state):
    current = preview_snapshot(production, state)
    approval = state.get("canvas_preview", {})
    changes = preview_changes(approval.get("approved_snapshot"), current)
    status = "CANVAS_PREVIEW_PENDING"
    if approval.get("approved_snapshot"):
        status = "CANVAS_PREVIEW_APPROVED" if not changes["changed_components"] else "CANVAS_PREVIEW_REVIEW_REQUIRED"
    return {"status": status, "current_snapshot": current, **changes}


def require_preview(production, state, shot_ids=None):
    preview = preview_status(production, state)
    approval = state.get("canvas_preview", {})
    if not approval.get("approved_snapshot") or not approval.get("reviewer") or not approval.get("evidence") or not approval.get("approved_at"):
        raise ValueError("CANVAS_PREVIEW_APPROVAL_REQUIRED: owner must preview the synchronized script/material set")
    if state.get("sync_status") != "synced":
        raise ValueError("CANVAS_SYNC_REQUIRED: reconcile/repair Canvas drift before production")
    requested = set(shot_ids or [s["shot_id"] for s in production["shots"]])
    if preview["status"] != "CANVAS_PREVIEW_APPROVED" and requested.intersection(preview["affected_shot_ids"]):
        raise ValueError("CANVAS_PREVIEW_REVIEW_REQUIRED: " + ", ".join(preview["changed_components"]))
    return preview
