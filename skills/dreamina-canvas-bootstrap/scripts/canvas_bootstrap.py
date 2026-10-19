#!/usr/bin/env python3
"""MIZAN V2 Lite: non-generating, schema-checked Canvas synchronizer (stdlib only)."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
import xml.etree.ElementTree as ET

GROUPS = ["00｜项目总览与脚本", "01｜人物参考", "02｜门店场景素材", "03｜商品素材",
          "04｜场景锚点", "05｜分镜图片", "06｜西语音频", "07｜视频片段", "08｜历史版本"]
TYPES = {"character": (1, "人物参考"), "scene": (2, "场景参考"), "product": (3, "商品参考"),
         "scene_anchor": (4, "场景锚点"), "storyboard_image": (5, "分镜图片"),
         "first_frame": (5, "视频首帧"), "last_frame": (5, "视频尾帧"),
         "audio": (6, "西语音频"), "video": (7, "视频片段")}
QC = {"pending_check": "待核对", "pending_review": "待审核", "approved": "已批准",
      "redo": "需重做", "retired": "已停用"}
MEDIA = {".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
         ".mp3": "audio", ".wav": "audio", ".mp4": "video"}
SHOT_FIELDS = ("shot_id", "duration", "scene_id", "scene_anchor_id", "character_id", "product_refs",
               "voiceover_es", "translation_zh", "visual_description", "action", "motion_intention",
               "generation_strategy", "image_count", "audio_ref", "audio_role", "lip_sync_required")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "mizan-v2:" + ":".join(map(str, parts))))


def node_id(*parts):
    return "node_" + uuid.UUID(stable(*parts)).hex[:10]


def node_text(node):
    # CLI 1.0.3 serializes rich-text spaces/ampersands as HTML entities.
    # Decode exactly once; never trim or collapse source whitespace.
    return html.unescape(node.get("text", ""))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    """Atomic replacement; same-directory temp, fsync, private permissions where supported."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mizan-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def project_lock(path):
    """OS lock releases on process death, so resume never requires deleting a stale lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def safe_filename(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    if not text:
        raise ValueError("Empty filename")
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", text, re.I):
        text = "_" + text
    return text[:120].rstrip(" .")


def display_name(asset, version):
    prefix = asset.get("shot_id") or asset.get("sku_id") or asset.get("character_id") or asset["asset_id"]
    source = {"existing": "原有", "generated": "新生成"}[asset["source_type"]]
    return "｜".join((prefix, TYPES[asset["asset_type"]][1], asset["description"], source,
                     version["version"], QC[version["qc_status"]]))


def generated_filename(asset, version, suffix):
    return safe_filename("_".join(("MIZAN", asset.get("shot_id") or asset["asset_id"],
                                   TYPES[asset["asset_type"]][1], asset["description"], version))) + suffix


def validate_production(p):
    errors = []
    for key in ("schema_version", "project_id", "topic", "confirmed_by_owner", "script_version", "full_script", "shots", "assets"):
        if key not in p:
            errors.append("project." + key)
    if p.get("schema_version") != 2 or p.get("confirmed_by_owner") is not True:
        errors.append("schema_version must be 2 and confirmed_by_owner must be true")
    if not isinstance(p.get("full_script"), str) or not p.get("full_script"):
        errors.append("full_script must contain the locked original text")
    shots = p.get("shots", [])
    if not isinstance(shots, list) or not shots:
        errors.append("shots must be a nonempty ordered list")
        shots = []
    seen = set()
    for shot in shots:
        sid = shot.get("shot_id", "?")
        for field in SHOT_FIELDS:
            if field not in shot:
                errors.append(f"{sid}.{field}")
        if sid in seen:
            errors.append(f"duplicate shot_id: {sid}")
        seen.add(sid)
        if not isinstance(shot.get("duration"), (int, float)) or not math.isfinite(shot["duration"]) or shot["duration"] <= 0:
            errors.append(f"{sid}.duration must be positive finite seconds")
        if type(shot.get("image_count")) is not int or shot["image_count"] < 0:
            errors.append(f"{sid}.image_count must be an integer >=0")
        if shot.get("audio_role") not in ("dialogue", "narration", "none", None):
            errors.append(f"{sid}.audio_role")
        if not isinstance(shot.get("product_refs"), list):
            errors.append(f"{sid}.product_refs must be a list (empty when none)")
    ids = set()
    for a in p.get("assets", []):
        for key in ("asset_id", "asset_type", "local_path", "source_type", "description", "qc_status"):
            if key not in a:
                errors.append("asset." + key)
        if a.get("asset_id") in ids:
            errors.append("duplicate logical asset_id in production inputs: " + a["asset_id"])
        ids.add(a.get("asset_id"))
        if a.get("asset_type") not in TYPES or a.get("source_type") not in ("existing", "generated") or a.get("qc_status") not in QC:
            errors.append("invalid asset classification: " + str(a.get("asset_id")))
        if a.get("qc_status") == "approved" and not a.get("qc_evidence"):
            errors.append("approved asset requires qc_evidence: " + a.get("asset_id", "?"))
    subtitles = p.get("subtitles", {"enabled": False})
    if subtitles.get("enabled") and not subtitles.get("languages"):
        errors.append("explicit subtitle languages required")
    if errors:
        raise ValueError("Missing/invalid fields (no inferred script changes): " + "; ".join(errors))
    return p


def extract_docx(path):
    """Lossless paragraph/table text extraction in document order; no semantic guessing."""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:body//w:p", ns):
        parts = []
        for element in paragraph.iter():
            if element.tag == "{" + ns["w"] + "}t":
                parts.append(element.text or "")
            elif element.tag in ("{" + ns["w"] + "}br", "{" + ns["w"] + "}cr"):
                parts.append("\n")
            elif element.tag == "{" + ns["w"] + "}tab":
                parts.append("\t")
        paragraphs.append("".join(parts))
    text = "\n".join(paragraphs)
    # Only an explicitly supplied JSON production block is safe to interpret automatically.
    match = re.search(r"MIZAN_PRODUCTION_JSON_BEGIN\s*(.*?)\s*MIZAN_PRODUCTION_JSON_END", text, re.S)
    return {"source_file": str(Path(path).resolve()), "source_hash": file_hash(path), "full_text": text,
            "production": validate_production(json.loads(match.group(1))) if match else None,
            "requires_structured_mapping": not bool(match),
            "required_shot_fields": list(SHOT_FIELDS) if not match else []}


class CLIError(RuntimeError):
    def __init__(self, error):
        self.error = error
        super().__init__(json.dumps(error, ensure_ascii=False))


class CanvasCLI:
    """Public CLI only. This wrapper cannot run/quote/confirm any generation task."""
    def __init__(self, executable=None, skill_path=None, timeout=90):
        self.executable = executable or shutil.which("dreamina-canvas") or shutil.which("dreamina-canvas.exe")
        if not self.executable:
            candidate = Path.home() / "bin" / "dreamina-canvas.exe"
            if candidate.is_file():
                self.executable = str(candidate)
        if not self.executable:
            raise ValueError("dreamina-canvas CLI is not installed")
        self.timeout, self.requests, self.spec = timeout, [], None
        candidates = [Path(skill_path)] if skill_path else [Path.home() / ".agents/skills/dreamina-canvas-cli/SKILL.md",
                                                          Path.home() / ".codex/skills/dreamina-canvas-cli/SKILL.md"]
        self.skill = next((p for p in candidates if p.is_file()), None)
        if not self.skill:
            raise ValueError("Installed dreamina-canvas-cli SKILL.md not found; pass --canvas-skill")
        self.skill_hash = file_hash(self.skill)
        self.skill.read_text(encoding="utf-8-sig")

    def command(self, *parts):
        entry = self.spec
        for part in parts:
            entry = next((c for c in entry.get("subcommands", []) if c["name"] == part), None) if entry else None
        return entry

    def supports(self, parts, *flags):
        entry = self.command(*parts)
        return bool(entry) and set(flags) <= {f["name"] for f in entry.get("flags", [])}

    def call(self, parts, positional=(), **flags):
        if parts not in [("version",), ("schema",), ("auth", "status")] and not self.command(*parts):
            raise ValueError("Command absent from current CLI schema: " + " ".join(parts))
        if "--run" in positional or flags.get("run") or parts[:2] in (("node", "run"), ("node", "quote"), ("node", "confirm")):
            raise ValueError("Bootstrap does not permit paid-generation commands")
        if self.spec:
            supported = {f["name"] for f in self.command(*parts).get("flags", [])}
            if not set(flags) <= supported:
                raise ValueError("Flags absent from CLI schema: " + str(set(flags) - supported))
        args = [str(self.executable), *parts, *map(str, positional), "--format", "json", "--non-interactive"]
        for name, values in flags.items():
            for value in values if isinstance(values, list) else [values]:
                if value is None or value is False:
                    continue
                args.append("--" + name)
                if value is not True:
                    args.append(str(value))
        try:
            result = subprocess.run(args, capture_output=True, encoding="utf-8", timeout=self.timeout)
            # Public CLI writes structured failure envelopes to stderr, success to stdout.
            envelope = json.loads((result.stdout.strip() or result.stderr.strip()).lstrip("\ufeff"))
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as error:
            raise CLIError({"code": "transport_uncertain", "class": type(error).__name__, "requiredAction": "resume"}) from error
        request_id = envelope.get("meta", {}).get("requestId") or envelope.get("error", {}).get("requestId")
        self.requests.append({"command": " ".join(parts), "request_id": request_id, "at": now(), "ok": envelope.get("ok")})
        if not envelope.get("ok") or result.returncode:
            # Only stable error facts; provider payloads and authenticated URLs never enter our journal.
            error = envelope.get("error", {})
            raise CLIError({k: error[k] for k in ("code", "serviceCode", "class", "retryable", "requiredAction", "requestId") if k in error})
        return envelope["data"]

    def discover(self):
        version = self.call(("version",))
        self.spec = self.call(("schema",))
        auth = self.call(("auth", "status"))
        media = {kind: self.supports(("node", "create", kind), "resource-id", "import-kind", "node-id", "submit-id")
                 for kind in ("image", "audio", "video")}
        group_command = self.command("node", "create", "group")
        # No native group contract exists in CLI 1.0.3. Never synthesize a private API.
        return {"version": version.get("version"), "logged_in": auth.get("loggedIn") is True,
                "installed_skill_hash": self.skill_hash, "schema_hash": digest(self.spec),
                "text": self.supports(("node", "create", "text"), "text", "node-id"), "media_import": media,
                "resource_upload": self.supports(("resource", "upload"), "resource-id", "project-id", "file"),
                "native_group": bool(group_command), "native_group_adapter_verified": False,
                "layout": all(self.supports(("node", "create", k), "x", "y") for k in ("text", "image", "audio", "video")),
                "query": self.supports(("node", "find"), "project-id") and bool(self.command("node", "show")) and bool(self.command("resource", "get")),
                "canvas_creation_access": "not_yet_verified"}


class Bootstrap:
    def __init__(self, production_path, client=None, state_path=None):
        self.path = Path(production_path).resolve()
        self.production = validate_production(read_json(self.path))
        self.client = client
        self.state_path = Path(state_path) if state_path else self.path.with_name("canvas_manifest.json")
        self.state = read_json(self.state_path) if self.state_path.exists() else {
            "schema_version": 2, "project_id": self.production["project_id"], "created_at": now(),
            "canvas_project_id": self.production.get("canvas_project_id") or stable(self.production["project_id"], "canvas"),
            "sync_status": "planned", "nodes": {}, "assets": {}, "approved_versions": {}, "tasks": {}, "history": []}
        if self.state["project_id"] != self.production["project_id"]:
            raise ValueError("Production and Canvas project_id do not match")
        self.state.setdefault("node_owners", {})
        # Migrate earlier journals once, retaining earliest known content ownership.
        existing = [v for vs in self.state["assets"].values() for v in vs]
        for v in sorted(existing, key=lambda item: item.get("created_at", "")):
            self.state["node_owners"].setdefault(v["canvas_node_id"], {"asset_id": v["asset_id"], "version": v["version"]})
        self.remote = {}

    def save(self):
        self.state["updated_at"] = now()
        if self.client:
            self.state["requests"] = (self.state.get("requests", []) + self.client.requests)[-500:]
            self.client.requests.clear()
        write_json(self.state_path, self.state)

    def plan(self):
        assets, missing = [], []
        product_refs = {sku for s in self.production["shots"] for sku in s["product_refs"]}
        shots = {s["shot_id"] for s in self.production["shots"]}
        for asset in self.production["assets"]:
            if asset["asset_type"] == "product" and asset.get("sku_id") not in product_refs:
                continue
            if asset.get("shot_id") and asset["shot_id"] not in shots:
                continue
            path = (self.path.parent / asset["local_path"]).resolve()
            entry = dict(asset, local_path=str(path), media_type=MEDIA.get(path.suffix.lower()))
            expected_media = asset["asset_type"] if asset["asset_type"] in ("audio", "video") else "image"
            if not path.is_file():
                missing.append({"asset_id": asset["asset_id"], "reason": "missing_file", "local_path": str(path)})
            elif path.suffix.lower() not in MEDIA:
                missing.append({"asset_id": asset["asset_id"], "reason": "unsupported_extension", "local_path": str(path)})
            elif entry["media_type"] != expected_media:
                missing.append({"asset_id": asset["asset_id"], "reason": "asset_media_type_mismatch", "local_path": str(path)})
            else:
                entry["file_hash"] = file_hash(path)
                assets.append(entry)
        supplied = {a.get("sku_id") for a in assets if a["asset_type"] == "product"}
        missing += [{"sku_id": sku, "reason": "missing_product_reference"} for sku in sorted(product_refs - supplied)]
        return {"assets": assets, "missing": missing, "shot_order": [s["shot_id"] for s in self.production["shots"]],
                "script_nodes": 3 + len(self.production["shots"]), "sections": GROUPS,
                "writes_remote": False, "paid_operations": 0}

    def discover(self):
        caps = self.client.discover()
        self.state["capabilities"] = caps
        self.state["organization_mode"] = "spatial_sections" if caps["layout"] and caps["text"] else "name_prefixes"
        if caps["native_group"]:
            self.state["group_limitation"] = "Native group contract changed; adapter unverified; using documented fallback, not native groups."
        if not caps["logged_in"]:
            raise ValueError("Canvas authentication required")
        if not caps["query"]:
            raise ValueError("CLI cannot verify remote nodes/resources")
        self.save()
        return caps

    def remote_nodes(self):
        nodes, offset = {}, 0
        while True:
            data = self.client.call(("node", "find"), **{"project-id": self.state["canvas_project_id"], "limit": 50, "offset": offset})
            nodes.update({n["nodeId"]: n for n in data["items"]})
            if not data.get("hasMore"):
                break
            offset += len(data["items"])
            if offset > 1000 or not data["items"]:
                raise ValueError("Remote draft too large to reconcile safely")
        self.remote = nodes
        ids = list(nodes)
        for start in range(0, len(ids), 20):
            detail = self.client.call(("node", "show"), **{"project-id": self.state["canvas_project_id"], "node-id": ids[start:start + 20]})
            for item in detail.get("nodes", []):
                if item.get("result") == "FOUND" and item.get("node"):
                    node = item["node"]
                    self.remote[node["nodeId"]] = dict(node, _full=True)
        return self.remote

    def ensure_canvas(self, create=True):
        target = self.state["canvas_project_id"]
        cursor = None
        found = None
        while True:
            page = self.client.call(("canvas", "ls"), **({"cursor": cursor} if cursor else {}))
            found = next((c for c in page["items"] if c["projectId"] == target), None)
            if found or not page.get("hasMore"):
                break
            cursor = page["nextCursor"]
        if not found:
            if not create:
                raise ValueError("Canvas not found; reconcile is read-only and will not create one")
            if self.production.get("canvas_project_id") or self.state.get("sync_status") == "synced":
                raise ValueError("Existing configured Canvas is inaccessible; do not replace it")
            name = self.state.get("canvas_project_name") or "｜".join(("MIZAN", self.production["topic"], self.state["created_at"][:10], "v01"))
            self.state.update(canvas_project_name=name, sync_status="creating")
            self.save()  # target UUID is durable before create
            found = self.client.call(("canvas", "create"), (name,), **{"project-id": target})["project"]
        self.state.update(canvas_project_name=found["name"], canvas_url=found.get("webUrl"), sync_status="bootstrapped")
        self.state["capabilities"]["canvas_creation_access"] = "reused" if self.production.get("canvas_project_id") else "verified"
        self.save()
        self.remote_nodes()

    def show(self, nid):
        if self.remote.get(nid, {}).get("_full"):
            return self.remote[nid]
        data = self.client.call(("node", "show"), **{"project-id": self.state["canvas_project_id"], "node-id": [nid]})
        node = next((item["node"] for item in data.get("nodes", []) if item.get("node", {}).get("nodeId") == nid), None)
        if node:
            self.remote[nid] = dict(node, _full=True)
        return node

    def position(self, group, index):
        # Use measured card bounds, not assumed text heights. Keep each category in its own column.
        records = [r for r in self.state["nodes"].values() if r.get("group_index") == group]
        records += [v for vs in self.state["assets"].values() for v in vs if v.get("group_name") == GROUPS[group]]
        bottom = max((r["layout"]["y"] + r["layout"]["height"] for r in records
                      if r.get("layout") and abs(r["layout"]["x"] - group * 2600) < 1), default=0)
        return {"x": group * 2600, "y": bottom + 160}

    def sync_text(self, key, title, text, group=0, index=0):
        record = self.state["nodes"].setdefault(key, {"node_id": node_id(self.production["project_id"], key), "history": []})
        nid, content_hash = record["node_id"], digest({"title": title, "text": text})
        remote = self.show(nid) if nid in self.remote else None
        if remote and node_text(remote) == text and remote.get("title") == title:
            record.update(content_hash=content_hash, text=text, title=title, group_index=group,
                          script_version=self.production["script_version"], layout=remote.get("layout"),
                          sync_status="synced", verified_at=now())
            self.save()
            return
        if record.get("text") and record.get("content_hash") != content_hash:
            if (key == "full_script" or key.startswith("shot:")) and record.get("script_version") == self.production["script_version"]:
                raise ValueError("Locked script changed without incrementing script_version: " + key)
            record["history"].append({k: record[k] for k in ("content_hash", "text", "title") if k in record})
        record.update(content_hash=content_hash, text=text, title=title, sync_status="pending", group_index=group,
                      update_id=stable(nid, content_hash), script_version=self.production["script_version"])
        self.save()
        action = "edit" if remote else "create"
        flags = {"project-id": self.state["canvas_project_id"], "node-id": nid, "update-id": record["update_id"], "title": title, "text": text}
        if self.state["organization_mode"] == "spatial_sections" and not remote:
            flags.update({"x": group * 2600, "y": 0} if key.startswith("section:") else self.position(group, index))
        self.client.call(("node", action, "text"), **flags)
        self.remote[nid] = {"nodeId": nid, "type": "text"}
        actual = self.show(nid)
        if not actual or node_text(actual) != text or actual.get("title") != title:
            raise ValueError("Text roundtrip mismatch for " + key)
        record.update(sync_status="synced", verified_at=now(), layout=actual.get("layout"))
        self.save()

    def structure(self):
        if not self.state["capabilities"]["text"]:
            self.state["text_sync_status"] = "unsupported"
            self.save()
            return
        for index, title in enumerate(GROUPS):
            placeholder = "制作区域；首次初始化仅预留位置。实际素材及批准状态见各节点和清单。" if 4 <= index <= 7 else "按清单同步；资源状态以逐项记录为准。"
            self.sync_text("section:" + str(index), title, title + "\n" + placeholder, index, 0)

    def script(self):
        if not self.state["capabilities"]["text"]:
            raise ValueError("CLI cannot create text nodes; script sync remains unsupported")
        p = self.production
        overview = {k: p[k] for k in ("project_id", "topic", "script_version", "format", "subtitles") if k in p}
        self.sync_text("overview", "项目总览｜" + p["topic"], json.dumps(overview, ensure_ascii=False, indent=2), index=2)
        self.sync_text("full_script", "完整视频脚本｜" + p["script_version"], p["full_script"], index=3)
        self.sync_text("rules", "制作规则｜确认版", json.dumps(p.get("production_rules", []), ensure_ascii=False, indent=2), index=4)
        for index, shot in enumerate(p["shots"], 5):
            self.sync_text("shot:" + shot["shot_id"], shot["shot_id"] + "｜镜头脚本｜" + shot.get("title", shot["scene_id"]),
                           json.dumps(shot, ensure_ascii=False, indent=2), index=index)

    def register(self, asset):
        if asset.get("qc_status") not in QC:
            raise ValueError("Invalid QC status")
        if asset.get("qc_status") == "approved" and not asset.get("qc_evidence"):
            raise ValueError("Registering an approved input requires qc_evidence")
        aid = asset["asset_id"]
        versions = self.state["assets"].setdefault(aid, [])
        existing = next((v for v in versions if v["file_hash"] == asset["file_hash"]), None)
        if existing:
            return existing
        if versions and asset["qc_status"] == "approved":
            # An old input declaration/evidence cannot approve newly changed bytes.
            asset = dict(asset, qc_status="pending_review", requested_qc_status="approved",
                         qc_note="new_content_requires_review_after_sync")
        number = max((int(v["version"][1:]) for v in versions), default=0) + 1
        version = dict(asset, version=f"v{number:02}", canvas_resource_id=stable(self.state["canvas_project_id"], asset["file_hash"], "resource"),
                       canvas_node_id=node_id(self.state["canvas_project_id"], asset["file_hash"], "media"),
                       submit_id=stable(self.state["canvas_project_id"], asset["file_hash"], "import"), sync_status="pending",
                       group_name=GROUPS[TYPES[asset["asset_type"]][0]], created_at=now())
        version["update_id"] = stable(version["canvas_node_id"], "create")
        if asset["source_type"] == "generated":
            original = Path(asset["local_path"])
            destination = self.state_path.parent / "generated" / safe_filename(aid) / generated_filename(asset, version["version"], original.suffix.lower())
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and file_hash(destination) != asset["file_hash"]:
                raise ValueError("Refuse to overwrite existing generated version: " + str(destination))
            if not destination.exists():
                shutil.copy2(original, destination)
            version.update(source_local_path=str(original), local_path=str(destination))
        versions.append(version)
        self.state["node_owners"].setdefault(version["canvas_node_id"], {"asset_id": aid, "version": version["version"]})
        if asset["qc_status"] == "approved":
            version["approval_pending_selection"] = True
        self.save()
        return version

    def sync_asset(self, version, index):
        kind, nid, rid = version["media_type"], version["canvas_node_id"], version["canvas_resource_id"]
        caps = self.state["capabilities"]
        if not caps["resource_upload"] or not caps["media_import"].get(kind):
            version.update(sync_status="unsupported", unsupported_reason="current_schema_has_no_media_import")
            self.save()
            return
        # Probe preallocated resource even after an uncertain upload response; never allocate a new ID.
        try:
            resource = self.client.call(("resource", "get"), (rid,), **{"project-id": self.state["canvas_project_id"]})
        except CLIError as error:
            if error.error.get("code") != "service.6":  # 1.0.3 verified resource-not-found classification
                raise
            resource = None
        title = display_name(version, version)
        if not resource:
            version["sync_status"] = "uploading"
            self.save()
            self.client.call(("resource", "upload"), **{"project-id": self.state["canvas_project_id"], "resource-id": rid,
                "file": version["local_path"], "name": title, "type": kind,
                "import-kind": "external_generated" if version["source_type"] == "generated" else "local_upload"})
            resource = self.client.call(("resource", "get"), (rid,), **{"project-id": self.state["canvas_project_id"]})
        if resource.get("status") != "success" or resource.get("type") != kind:
            raise ValueError("Uploaded resource is not terminal success with matching media type")
        actual = self.show(nid) if nid in self.remote else None
        if not actual:
            version["sync_status"] = "importing"
            self.save()
            flags = {"project-id": self.state["canvas_project_id"], "node-id": nid, "update-id": version["update_id"],
                     "submit-id": version["submit_id"], "title": title, "resource-id": [rid],
                     "import-kind": "external_generated" if version["source_type"] == "generated" else "local_upload"}
            if self.state["organization_mode"] == "spatial_sections":
                flags.update(self.position(GROUPS.index(version["group_name"]), index + 1))
            self.client.call(("node", "create", kind), **flags)
            self.remote[nid] = {"nodeId": nid, "type": kind}
            actual = self.show(nid)
        if not actual or not any(r.get("resourceId") == rid and r.get("status") == "success" for r in actual.get("resources", [])):
            raise ValueError("Resource exists but is not visible through the expected Canvas node")
        version.update(sync_status="synced", verified_at=now())
        version["layout"] = actual.get("layout")
        version.setdefault("layout_group", version["group_name"])
        if version.pop("approval_pending_selection", False):
            self.state["approved_versions"][version["asset_id"]] = version["version"]
        # Repair a review/name edit lost after the local manifest was durably saved.
        owner = self.node_owner(nid)
        if owner is version and (actual.get("title") != title or version.get("metadata_sync_status") == "pending"):
            self.update_title(version, history=version["group_name"] == GROUPS[8])
        self.save()

    def sync(self):
        self.script()
        plan = self.plan()
        self.state["missing"] = plan["missing"]
        self.save()
        for asset in plan["assets"]:
            self.register(asset)
        # Also recover registered outputs that are absent from the original production input list.
        for versions in self.state["assets"].values():
            for version in versions:
                if not Path(version["local_path"]).is_file():
                    version["sync_status"] = "missing_file"
                    self.save()
                    continue
                if file_hash(version["local_path"]) != version["file_hash"]:
                    version["sync_status"] = "local_content_changed"
                    self.save()
                    continue
                try:
                    self.sync_asset(version, 0)
                except CLIError as error:
                    version.update(sync_status="interrupted", last_error=error.error)
                    self.save()
                    raise
        self.state["sync_status"] = "synced" if not plan["missing"] and all(v["sync_status"] == "synced" for vs in self.state["assets"].values() for v in vs) else "partial"
        self.save()

    def reconcile(self):
        self.remote_nodes()
        for record in self.state["nodes"].values():
            actual = self.show(record["node_id"]) if record["node_id"] in self.remote else None
            record["sync_status"] = "synced" if actual and node_text(actual) == record.get("text") and actual.get("title") == record.get("title") else "drifted"
        for versions in self.state["assets"].values():
            for v in versions:
                actual = self.show(v["canvas_node_id"]) if v["canvas_node_id"] in self.remote else None
                v["sync_status"] = "synced" if actual and any(r.get("resourceId") == v["canvas_resource_id"] and r.get("status") == "success" for r in actual.get("resources", [])) else "drifted"
                if v["sync_status"] == "synced":
                    resource = self.client.call(("resource", "get"), (v["canvas_resource_id"],), **{"project-id": self.state["canvas_project_id"]})
                    if resource.get("status") != "success":
                        v["sync_status"] = "drifted"
        # Generation recovery is read-only, including absent/unknown submissions.
        for task in self.state["tasks"].values():
            if task.get("submit_id"):
                status = self.client.call(("operation", "status"), (task["submit_id"],), **{"project-id": self.state["canvas_project_id"]})
                task["remote_state"] = status.get("state")
                task["resources"] = [{"resource_id": r.get("resourceId"), "state": r.get("state")} for r in status.get("resources", [])]
                task["recovery_action"] = "inspect_same_submission_no_resubmit"
        records = list(self.state["nodes"].values()) + [v for vs in self.state["assets"].values() for v in vs]
        self.state["sync_status"] = "synced" if records and all(r["sync_status"] == "synced" for r in records) else "partial"
        self.save()

    def review(self, asset_id, version, status, evidence):
        if status == "approved" and not evidence:
            raise ValueError("Approval requires reviewer evidence")
        v = next(v for v in self.state["assets"][asset_id] if v["version"] == version)
        if v["sync_status"] != "synced" and status == "approved":
            raise ValueError("Cannot approve an unverified Canvas import")
        old = self.state["approved_versions"].get(asset_id)
        v.update(qc_status=status, qc_evidence=evidence)
        previous = None

        def place(item, group):
            if item["group_name"] != group:
                item.pop("metadata_position", None)
            item.update(group_name=group, metadata_sync_status="pending")

        if status == "approved":
            self.state["approved_versions"][asset_id] = version
            place(v, GROUPS[TYPES[v["asset_type"]][0]])
            if old and old != version:
                previous = next(x for x in self.state["assets"][asset_id] if x["version"] == old)
                place(previous, GROUPS[8])
        elif old == version:
            self.state["approved_versions"].pop(asset_id, None)
        if status == "retired":
            place(v, GROUPS[8])
        v["metadata_sync_status"] = "pending"
        self.state["history"].append({"asset_id": asset_id, "version": version, "qc_status": status, "evidence": evidence, "at": now()})
        self.save()  # both new selection and old archival intent survive the first failed edit
        self.update_title(v)
        if previous:
            self.update_title(previous, history=True)
        self.save()

    def node_owner(self, nid):
        owner = self.state["node_owners"][nid]
        return next(v for v in self.state["assets"][owner["asset_id"]] if v["version"] == owner["version"])

    def update_title(self, v, history=False):
        owner = self.node_owner(v["canvas_node_id"])
        if owner is not v:
            v["metadata_sync_status"] = "shared_owner_controls_title"
            self.save()
            return
        title = display_name(v, v)
        flags = {"project-id": self.state["canvas_project_id"], "node-id": v["canvas_node_id"],
                 "update-id": stable(v["canvas_node_id"], title, v["group_name"]), "title": title}
        if self.state["organization_mode"] == "spatial_sections" and v.get("layout_group") != v["group_name"]:
            v.setdefault("metadata_position", self.position(GROUPS.index(v["group_name"]), len(self.state["history"])))
            flags.update(v["metadata_position"])
            flags["update-id"] = stable(v["canvas_node_id"], title, v["group_name"], digest(v["metadata_position"]))
        v.update(title_update_id=flags["update-id"], metadata_sync_status="pending")
        self.save()
        self.client.call(("node", "edit", v["media_type"]), **flags)
        self.remote.pop(v["canvas_node_id"], None)
        actual = self.show(v["canvas_node_id"])
        if not actual or actual.get("title") != title:
            raise ValueError("Updated media title did not roundtrip")
        v.update(metadata_sync_status="synced", layout=actual.get("layout"), layout_group=v["group_name"])
        self.save()

    def status(self):
        versions = [v for vs in self.state["assets"].values() for v in vs]
        blockers = []
        for shot in self.production["shots"]:
            if shot.get("audio_role") != "none" and not shot.get("audio_ref"):
                blockers.append({"shot_id": shot["shot_id"], "reason": "missing_prepared_audio"})
            if shot.get("approved_asset_id") not in self.state["approved_versions"]:
                blockers.append({"shot_id": shot["shot_id"], "reason": "missing_approved_execution_image"})
        return {"project_id": self.production["project_id"], "canvas_project_id": self.state["canvas_project_id"],
                "canvas_url": self.state.get("canvas_url"), "sync_status": self.state["sync_status"],
                "organization_mode": self.state.get("organization_mode", "not_discovered"),
                "asset_versions": len(versions), "synced_asset_versions": sum(v["sync_status"] == "synced" for v in versions),
                "script_nodes": len(self.state["nodes"]), "missing": self.plan()["missing"], "video_blockers": blockers,
                "next_action": "review_materials_then_generate_approved_shots", "paid_operations": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["dry-run", "bootstrap", "sync", "reconcile", "resume", "status", "register", "review", "extract-docx"])
    parser.add_argument("--production", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--cli")
    parser.add_argument("--canvas-skill")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--asset-id")
    parser.add_argument("--source-type", choices=["existing", "generated"], default="generated")
    parser.add_argument("--version")
    parser.add_argument("--qc-status", choices=list(QC), default="pending_review")
    parser.add_argument("--evidence")
    args = parser.parse_args(argv)
    if args.mode == "extract-docx":
        if not args.file or not args.output:
            parser.error("extract-docx requires --file and --output")
        result = extract_docx(args.file)
        write_json(args.output, result)
        print(json.dumps({"output": str(args.output), "requires_structured_mapping": result["requires_structured_mapping"]}, ensure_ascii=False))
        return 2 if result["requires_structured_mapping"] else 0
    if not args.production:
        parser.error("--production is required")
    job = Bootstrap(args.production, state_path=args.state)
    if args.mode == "dry-run":
        print(json.dumps(job.plan(), ensure_ascii=False, indent=2))
        return 2 if job.plan()["missing"] else 0
    if args.mode == "status":
        print(json.dumps(job.status(), ensure_ascii=False, indent=2))
        return 0
    with project_lock(job.state_path.with_suffix(".lock")):
        # Reload after acquiring the lock to avoid lost updates between concurrent invocations.
        job = Bootstrap(args.production, state_path=args.state)
        job.client = CanvasCLI(args.cli, args.canvas_skill)
        try:
            job.discover()
            job.ensure_canvas(create=args.mode != "reconcile")
            if args.mode == "reconcile":
                job.reconcile()
            elif args.mode == "review":
                job.review(args.asset_id, args.version, args.qc_status, args.evidence)
            else:
                if args.mode == "resume":
                    job.reconcile()
                job.structure()
                if args.mode == "register":
                    if not args.file or not args.asset_id:
                        parser.error("register requires --file and --asset-id")
                    template = next((a for a in job.production["assets"] + job.production.get("outputs", []) if a["asset_id"] == args.asset_id), None)
                    if not template:
                        raise ValueError("Declare the logical output asset in production.assets before registering")
                    path = args.file.resolve()
                    if path.suffix.lower() not in MEDIA:
                        raise ValueError("Unsupported extension")
                    job.register(dict(template, local_path=str(path), file_hash=file_hash(path), media_type=MEDIA[path.suffix.lower()],
                                      source_type=args.source_type, qc_status=args.qc_status, qc_evidence=args.evidence))
                if args.mode in ("sync", "resume", "register"):
                    job.sync()
            print(json.dumps(job.status(), ensure_ascii=False, indent=2))
            return 0 if job.state["sync_status"] != "partial" else 2
        except (CLIError, ValueError) as error:
            job.state.update(sync_status="interrupted", last_error=error.error if isinstance(error, CLIError) else str(error))
            job.save()
            raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, CLIError, OSError, KeyError, StopIteration) as error:
        print(json.dumps({"ok": False, "error": str(error), "next_action": "inspect_status_then_resume"}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
