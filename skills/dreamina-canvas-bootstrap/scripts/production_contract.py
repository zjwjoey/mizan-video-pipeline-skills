"""Explicit template-2 aliases and lossless image-stage contract. No creative inference."""
import copy

PROJECT_ALIASES = {"owner_confirmed": "confirmed_by_owner", "项目ID": "project_id", "主题": "topic",
                   "脚本版本": "script_version", "完整脚本": "full_script", "镜头": "shots", "素材": "assets"}
SHOT_ALIASES = {"duration_target": "duration", "duration_s": "duration", "scene_group": "scene_id",
                "host_anchor_id": "character_id", "products": "product_refs", "西班牙语口播": "voiceover_es",
                "中文对照": "translation_zh", "画面内容": "visual_description", "人物动作": "action",
                "motion intention": "motion_intention", "start_asset_id": "start_frame_asset_id",
                "end_asset_id": "end_frame_asset_id"}
LEGACY_STRATEGIES = {"scene_anchor_then_incremental_composite": "ANCHOR_CHARACTER_PRODUCT",
                     "reuse_approved_anchor": "ANCHOR_CHARACTER_PRODUCT"}
STRATEGIES = {"ANCHOR_ONLY", "ANCHOR_CHARACTER", "ANCHOR_PRODUCT", "ANCHOR_CHARACTER_PRODUCT",
              "START_END_FRAME", "DIRECT_PRODUCT", "MULTI_REFERENCE"}
STAGE_FIELDS = ("prompt", "negative_prompt", "reference_asset_ids", "keep_fixed", "add_elements", "output_asset_ids")


def canonical_strategy(value):
    return LEGACY_STRATEGIES.get(value, value)


def map_aliases(data, aliases, scope, provenance):
    for source, target in aliases.items():
        if source not in data:
            continue
        if target in data and data[target] != data[source]:
            raise ValueError(f"Conflicting aliases at {scope}: {source} != {target}")
        if target not in data:
            data[target] = copy.deepcopy(data[source])
            provenance.append({"source_field": scope + "." + source, "target_field": scope + "." + target,
                               "operation": "exact_alias_copy"})
        del data[source]


def normalize_production(value):
    """Return a copy. Only documented keys change; original string/list values do not."""
    p = copy.deepcopy(value)
    provenance = p.setdefault("field_mappings", [])
    for key in ("owner_confirmed", "confirmed_by_owner"):
        if isinstance(p.get(key), str) and p[key].lower() in ("true", "yes", "false", "no"):
            raw = p[key]
            p[key] = raw.lower() in ("true", "yes")
            provenance.append({"source_field": key, "raw_value": raw, "operation": "explicit_boolean_literal"})
    map_aliases(p, PROJECT_ALIASES, "project", provenance)
    for index, shot in enumerate(p.get("shots", [])):
        map_aliases(shot, SHOT_ALIASES, f"shots[{index}]", provenance)
        for key in list(shot):
            for stage in ("anchor", "incremental", "start", "end", "direct"):
                prefix = stage + "_"
                if key.startswith(prefix) and key[len(prefix):] in STAGE_FIELDS + ("base_asset_id", "reuse_asset_id"):
                    field = key[len(prefix):]
                    target = shot.setdefault("image_generation", {}).setdefault(stage, {})
                    if field in target and target[field] != shot[key]:
                        raise ValueError("Conflicting staged prompt field: " + key)
                    target[field] = shot.pop(key)
                    provenance.append({"source_field": f"shots[{index}].{key}", "operation": "exact_stage_field_copy"})
    return p


def image_contract_errors(shot):
    sid = shot.get("shot_id", "?")
    strategy = canonical_strategy(shot.get("generation_strategy"))
    if strategy not in STRATEGIES:
        return [f"{sid}.generation_strategy: unsupported explicit strategy"]
    errors = []
    images = shot.get("image_asset_ids")
    if not isinstance(images, list) or not all(isinstance(i, str) and i for i in images) or len(images) != shot.get("image_count") or len(set(images)) != len(images):
        errors.append(f"{sid}.image_asset_ids: ordered unique IDs must match image_count")
        images = []
    if shot.get("image_count", 0) == 0:
        return errors
    stages = shot.get("image_generation")
    if not isinstance(stages, dict):
        return errors + [f"{sid}.image_generation: explicit per-stage prompt records required"]
    required = ["direct"] if strategy in ("DIRECT_PRODUCT", "MULTI_REFERENCE") else ["anchor"]
    if strategy == "START_END_FRAME":
        required += ["start", "end"]
        start, end = shot.get("start_frame_asset_id"), shot.get("end_frame_asset_id")
        if not start or not end or start == end or images != [start, end]:
            errors.append(f"{sid}: START_END_FRAME requires two distinct ordered start/end image_asset_ids")
    elif strategy != "ANCHOR_ONLY" and strategy not in ("DIRECT_PRODUCT", "MULTI_REFERENCE"):
        required += ["incremental"]
    outputs = []
    for name in required:
        stage = stages.get(name)
        if not isinstance(stage, dict):
            errors.append(f"{sid}.image_generation.{name}")
            continue
        if name == "anchor" and stage.get("reuse_asset_id"):
            if stage["reuse_asset_id"] != shot.get("scene_anchor_id"):
                errors.append(f"{sid}.anchor.reuse_asset_id must match scene_anchor_id")
            if strategy == "ANCHOR_ONLY": outputs.append(stage["reuse_asset_id"])
            continue
        for field in STAGE_FIELDS:
            if field not in stage:
                errors.append(f"{sid}.image_generation.{name}.{field}")
        if not isinstance(stage.get("prompt"), str) or not stage["prompt"]:
            errors.append(f"{sid}.{name}.prompt: exact approved text required")
        if not isinstance(stage.get("negative_prompt"), str):
            errors.append(f"{sid}.{name}.negative_prompt: explicit string, empty if intentionally none")
        for field in ("reference_asset_ids", "keep_fixed", "add_elements", "output_asset_ids"):
            if not isinstance(stage.get(field), list):
                errors.append(f"{sid}.{name}.{field}: explicit ordered list required")
        if name in ("incremental", "start", "end") and stage.get("base_asset_id") != shot.get("scene_anchor_id"):
            errors.append(f"{sid}.{name}.base_asset_id must explicitly bind scene_anchor_id")
        if name == "anchor" and stage.get("output_asset_ids") != [shot.get("scene_anchor_id")]:
            errors.append(f"{sid}.anchor.output_asset_ids must name scene_anchor_id")
        if name != "anchor" or strategy == "ANCHOR_ONLY":
            outputs.extend(stage.get("output_asset_ids", []) if isinstance(stage.get("output_asset_ids"), list) else [])
    if outputs != images:
        errors.append(f"{sid}: stage output_asset_ids must exactly preserve ordered image_asset_ids")
    return errors
