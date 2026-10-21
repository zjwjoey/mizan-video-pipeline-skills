"""Conservative DOCX mapping: explicit tables/JSON, source coordinates, no prose guessing."""
import json
import re
import zipfile
import xml.etree.ElementTree as ET

from production_contract import PROJECT_ALIASES, SHOT_ALIASES

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"
PROJECT_KEYS = {"schema_version", "project_id", "topic", "confirmed_by_owner", "script_version", "full_script",
                "format", "subtitles", "production_rules", "assets", "outputs", "canvas_project_id", *PROJECT_ALIASES}
SHOT_KEYS = {"shot_id", "title", "duration", "scene_id", "scene_anchor_id", "character_id", "outfit_id", "product_refs",
             "voiceover_es", "translation_zh", "visual_description", "action", "motion_intention", "generation_strategy",
             "image_count", "audio_ref", "audio_role", "lip_sync_required", "approved_asset_id", "video_asset_id",
             "image_asset_ids", "start_frame_asset_id", "end_frame_asset_id", "image_generation", *SHOT_ALIASES}
JSON_KEYS = {"format", "subtitles", "production_rules", "assets", "outputs", "product_refs", "image_asset_ids",
             "image_generation", "reference_asset_ids", "keep_fixed", "add_elements", "output_asset_ids"}
STAGE_ALIASES = {"ANCHOR PROMPT": "prompt", "ANCHOR_PROMPT": "prompt", "FINAL PROMPT": "prompt",
                 "INCREMENTAL PROMPT": "prompt", "INCREMENTAL_PROMPT": "prompt", "START PROMPT": "prompt",
                 "END PROMPT": "prompt", "NEGATIVE / 禁止项": "negative_prompt", "NEGATIVE PROMPT": "negative_prompt",
                 "NEGATIVE_PROMPT": "negative_prompt", "参考素材": "reference_asset_ids", "REFERENCE ASSET IDS": "reference_asset_ids"}
STAGE_KEYS = {"prompt", "negative_prompt", "reference_asset_ids", "keep_fixed", "add_elements", "output_asset_ids",
              "base_asset_id", "reuse_asset_id"}


def paragraph_text(element):
    parts = []
    for item in element.iter():
        if item.tag == W + "t": parts.append(item.text or "")
        elif item.tag in (W + "br", W + "cr"): parts.append("\n")
        elif item.tag == W + "tab": parts.append("\t")
    return "".join(parts)


def docx_blocks(path):
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    blocks, table_index, paragraph_index = [], 0, 0
    for element in root.find("w:body", NS):
        if element.tag == W + "p":
            blocks.append({"kind": "paragraph", "source": f"paragraph[{paragraph_index}]", "text": paragraph_text(element)})
            paragraph_index += 1
        elif element.tag == W + "tbl":
            rows = []
            for ri, row in enumerate(element.findall("w:tr", NS)):
                cells = []
                for ci, cell in enumerate(row.findall("w:tc", NS)):
                    cells.append({"text": "\n".join(paragraph_text(p) for p in cell.findall(".//w:p", NS)),
                                  "source": f"table[{table_index}].row[{ri}].cell[{ci}]"})
                rows.append(cells)
            blocks.append({"kind": "table", "source": f"table[{table_index}]", "rows": rows})
            table_index += 1
    return blocks


def value_for(key, value):
    if not value.strip() or any(marker in value for marker in ("【", "填写 / 输入", "P__", "__ 秒")):
        raise ValueError("blank_or_template_placeholder")
    canonical = PROJECT_ALIASES.get(key, SHOT_ALIASES.get(key, key))
    if canonical in JSON_KEYS:
        return json.loads(value)  # do not guess reference IDs from filenames or freeform delimiters
    if canonical in ("confirmed_by_owner", "lip_sync_required"):
        if value.strip() in ("true", "yes", "是", "已确认"): return True
        if value.strip() in ("false", "no", "否", "未确认"): return False
        if canonical == "lip_sync_required" and value.strip() == "null": return None
        raise ValueError("explicit_boolean_required")
    if canonical in ("duration", "image_count", "schema_version"):
        parsed = json.loads(value)
        if not isinstance(parsed, (int, float)) or isinstance(parsed, bool): raise ValueError("explicit_number_required")
        return parsed
    if value.strip() == "null" and canonical in ("audio_ref", "audio_role", "character_id", "scene_anchor_id", "scene_id"):
        return None
    return value  # prompt, Spanish and Chinese cells retain every character, including whitespace


def map_blocks(blocks):
    """Map fully labeled key/value cards or wide shot tables; return unresolved facts, never fill prose."""
    p = {"shots": []}
    provenance, unresolved, conflicts = [], [], []
    current, stage_name, section = None, None, "project"
    shots = {}

    def put(target, key, raw, source):
        try:
            value = value_for(key, raw)
        except (ValueError, TypeError) as error:
            unresolved.append({"source": source, "field": key, "reason": str(error), "raw_value": raw})
            return
        if key in target and target[key] != value:
            conflicts.append({"source": source, "field": key, "reason": "conflicting_repeated_field"})
            return
        target[key] = value
        provenance.append({"source": source, "field": key, "raw_value": raw, "operation": "typed_exact_cell"})

    for block in blocks:
        if block["kind"] == "paragraph":
            heading = block["text"].strip()
            match = re.fullmatch(r"(?:SHOT\s+)?(P\d+(?:-[A-Z0-9]+)?)(?:\s*[｜|].*)?", heading)
            if match:
                sid = match.group(1)
                current = shots.setdefault(sid, {"shot_id": sid})
                stage_name, section = None, "shot"
            elif re.match(r"^(?:\d+(?:\.\d+)?\s*)?Stage\s+A\b", heading, re.I): stage_name = "anchor"
            elif re.match(r"^(?:\d+(?:\.\d+)?\s*)?Stage\s+B\b", heading, re.I): stage_name = "incremental"
            elif heading.upper() in ("START FRAME", "START", "首帧提示词"): stage_name = "start"
            elif heading.upper() in ("END FRAME", "END", "尾帧提示词"): stage_name = "end"
            elif heading.upper() in ("DIRECT", "DIRECT PRODUCT"): stage_name = "direct"
            elif heading.upper() in ("PROJECT SUMMARY", "项目总览", "项目配置"): current, stage_name, section = None, None, "project"
            continue
        rows = block["rows"]
        if rows and len(rows[0]) > 2 and any(c["text"].strip() == "shot_id" for c in rows[0]):
            headers = [c["text"].strip() for c in rows[0]]
            for row in rows[1:]:
                if len(row) != len(headers):
                    unresolved.append({"source": block["source"], "reason": "nonrectangular_shot_table"})
                    continue
                values = dict(zip(headers, row))
                sid = values["shot_id"]["text"]
                if not re.fullmatch(r"P\d+(?:-[A-Z0-9]+)?", sid):
                    unresolved.append({"source": values["shot_id"]["source"], "reason": "invalid_or_placeholder_shot_id"})
                    continue
                target = shots.setdefault(sid, {})
                for key, cell in values.items():
                    if key in SHOT_KEYS: put(target, key, cell["text"], cell["source"])
            continue
        for row in rows:
            if len(row) != 2:
                continue
            key, cell = row[0]["text"].strip(), row[1]
            if key == "shot_id":
                sid = cell["text"].strip()
                if re.fullmatch(r"P\d+(?:-[A-Z0-9]+)?", sid):
                    current = shots.setdefault(sid, {"shot_id": sid})
                    stage_name, section = None, "shot"
                else:
                    unresolved.append({"source": cell["source"], "field": key, "reason": "invalid_or_placeholder_shot_id"})
                continue
            field = STAGE_ALIASES.get(key.upper(), STAGE_ALIASES.get(key, key))
            if current is not None and stage_name and field in STAGE_KEYS:
                target = current.setdefault("image_generation", {}).setdefault(stage_name, {})
                put(target, field, cell["text"], cell["source"])
            elif current is not None and key in SHOT_KEYS:
                put(current, key, cell["text"], cell["source"])
            elif section == "project" and key in PROJECT_KEYS:
                put(p, key, cell["text"], cell["source"])
    p["shots"] = list(shots.values())
    p["source_provenance"] = provenance
    return p, unresolved, conflicts
