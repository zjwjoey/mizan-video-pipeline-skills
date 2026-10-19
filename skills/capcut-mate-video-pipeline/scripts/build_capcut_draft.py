#!/usr/bin/env python3
"""Build a local CapCut Mate/Jianying draft from a shot config.

Example config:
{
  "draft_name": "MIZAN_P01-P02_Bilingual",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "subtitle_tracks": ["es", "zh"],
  "shots": [
    {"id": "P01", "video": "镜头1.mp4", "start_s": 0, "end_s": 5,
     "width": 720, "height": 1280,
     "captions": {"es": "Spanish text", "zh": "中文字幕"}},
    {"id": "P02", "video": "镜头2.mp4", "start_s": 5, "end_s": 11,
     "width": 720, "height": 1280,
     "captions": {"es": "More Spanish", "zh": "更多中文字幕"}}
  ],
  "caption_style": {
    "font": "Georgia", "font_size": 8, "bold": true, "italic": true,
    "es_transform_y": -700, "zh_transform_y": -500
  }
}

The script intentionally uses only the Python standard library. It starts a
temporary HTTP server because CapCut Mate rejects local file:// URLs.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen


def api_call(base: str, endpoint: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"{base.rstrip('/')}/{endpoint.lstrip('/')}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") not in (0, None):
        raise RuntimeError(f"{endpoint} failed: {result}")
    return result


def micros(seconds: float) -> int:
    return int(round(float(seconds) * 1_000_000))


def encoded_url(media_root: Path, file_path: Path, port: int) -> str:
    relative = file_path.resolve().relative_to(media_root.resolve()).as_posix()
    encoded = "/".join(quote(part) for part in relative.split("/"))
    return f"http://127.0.0.1:{port}/{encoded}"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe_media(path: Path, ffprobe: str) -> dict:
    result = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                            check=True, capture_output=True, encoding="utf-8",
                            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
    return json.loads(result.stdout)


def preflight(config: dict, media_root: Path, ffprobe: str) -> list[dict]:
    # Resolve both sides: Windows TEMP may contain an 8.3 alias such as RUNNER~1.
    # Keep the containment check; normalizing only the file causes false escapes.
    media_root = media_root.resolve()
    shots, ids, previous = config.get("shots", []), set(), 0
    if not shots:
        raise ValueError("config.shots is empty")
    languages = config.get("subtitle_tracks", [])
    if not isinstance(languages, list) or len(languages) != len(set(languages)) or any(l not in ("es", "zh") for l in languages):
        raise ValueError("subtitle_tracks must explicitly list supported es/zh languages")
    for shot in shots:
        sid = shot.get("shot_id", shot.get("id"))
        if not sid or sid in ids:
            raise ValueError("Missing or duplicate shot ID")
        ids.add(sid)
        shot["id"] = sid
        start, end = float(shot["start_s"]), float(shot["end_s"])
        if not math.isfinite(start + end) or end <= start or micros(start) != previous:
            raise ValueError("Shot timing has a gap, overlap or invalid duration: " + sid)
        previous = micros(end)
        file_path = (media_root / shot["video"]).resolve()
        file_path.relative_to(media_root)  # do not expose files outside the explicitly served directory
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        facts = probe_media(file_path, ffprobe)
        video = next((s for s in facts.get("streams", []) if s.get("codec_type") == "video"), None)
        audio = [s for s in facts.get("streams", []) if s.get("codec_type") == "audio"]
        if not video or not video.get("width") or not video.get("height"):
            raise ValueError("No valid video stream: " + sid)
        source_duration = float(facts.get("format", {}).get("duration", video.get("duration", 0)))
        if source_duration + 0.05 < end - start:
            raise ValueError("Video is shorter than its timeline placement: " + sid)
        expected_ratio = float(config.get("width", 1080)) / float(config.get("height", 1920))
        if abs(video["width"] / video["height"] - expected_ratio) > 0.02:
            raise ValueError("Video aspect ratio differs from requested canvas: " + sid)
        if shot.get("audio_role", "dialogue") != "none" and not audio:
            raise ValueError("Generated video has no embedded audio: " + sid)
        if len(audio) > 1:
            raise ValueError("Multiple embedded audio streams require explicit review: " + sid)
        for language in languages:
            if not isinstance(shot.get("captions", {}).get(language), str) or not shot["captions"][language]:
                raise ValueError("Missing explicitly requested subtitle: " + sid + "." + language)
        shot.update(width=video["width"], height=video["height"], source_sha256=sha256(file_path),
                    source_duration_s=source_duration, embedded_audio_streams=len(audio))
    return shots


def resolve_font_file(name: str, bold: bool, italic: bool, supplied=None):
    if supplied:
        path = Path(supplied).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    if os.name == "nt" and name.casefold() == "georgia":
        filename = "georgiaz.ttf" if bold and italic else "georgiab.ttf" if bold else "georgiai.ttf" if italic else "georgia.ttf"
        path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if path.is_file():
            return path
    return None


def rewrite_and_validate(
    draft_dir: Path,
    old_root: Path,
    width: int,
    height: int,
    fps: int,
    caption_languages: list[str],
    caption_positions: dict[str, float],
    font_name: str,
    font_size: float,
    shots: list[dict] | None = None,
    font_path: Path | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> dict:
    info_path = draft_dir / "draft_info.json"
    content_path = draft_dir / "draft_content.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    if info.get("canvas_config", {}).get("width") != width or info.get("canvas_config", {}).get("height") != height:
        raise RuntimeError("Draft canvas does not match the requested dimensions")
    if int(info.get("fps", 0)) != int(fps):
        raise RuntimeError("Draft fps does not match the requested fps")

    content = json.loads(content_path.read_text(encoding="utf-8"))
    if info != content:
        raise RuntimeError("Draft JSON files differ before editing; refusing to hide divergence")

    def rewrite(value):
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, str):
            for old, new in ((str(old_root), str(draft_dir)), (old_root.as_posix(), draft_dir.as_posix())):
                if value.startswith(old + os.sep) or value.startswith(old + "/"):
                    return new + value[len(old):]
        return value

    patched = rewrite(info)
    texts = patched.get("materials", {}).get("texts", [])
    if not isinstance(texts, list):
        raise RuntimeError("Malformed text materials")
    copied_font = None
    if texts and font_path:
        copied_font = draft_dir / "assets/fonts" / font_path.name
        copied_font.parent.mkdir(parents=True, exist_ok=True)
        if copied_font.exists() and sha256(copied_font) != sha256(font_path):
            raise RuntimeError("Refuse to overwrite an existing different font file")
        if not copied_font.exists():
            shutil.copy2(font_path, copied_font)
    for material in texts:
        declared_names = {material.get("font_name"), material.get("font_title"), *(f.get("title") for f in material.get("fonts", []))}
        if not copied_font and font_name not in declared_names:
            raise RuntimeError("Requested caption font fell back to a different font")
        content = json.loads(material["content"])
        for style in content.get("styles", []):
            if float(style.get("size", 0)) != float(font_size):
                raise RuntimeError("Actual caption style size mismatch")
            for field, expected in (("bold", bold), ("italic", italic)):
                if expected is not None and bool(style.get(field, False)) != expected:
                    raise RuntimeError("Actual caption style mismatch: " + field)
            if copied_font:
                style["font"] = {"id": "", "path": str(copied_font)}
        if copied_font:
            material["font_name"] = material["font_title"] = font_name
        for font in material.get("fonts", []):
            if copied_font:
                font.update(title=font_name, path=str(copied_font), resource_id="")
            elif not font.get("resource_id") and not Path(font.get("path", "")).is_file():
                raise RuntimeError("Caption font has no usable file/resource; supply caption_style.font_path")
        material["content"] = json.dumps(content, ensure_ascii=False)
        if float(material.get("font_size", font_size)) != float(font_size):
            raise RuntimeError("Caption font size mismatch")

    text_tracks = [track for track in patched.get("tracks", []) if track.get("type") == "text"]
    if len(text_tracks) != len(caption_languages):
        raise RuntimeError(f"Expected {len(caption_languages)} caption tracks, found {len(text_tracks)}")
    for index, language in enumerate(caption_languages):
        expected_y = float(caption_positions[language]) / float(height)
        ys = {round(float(segment.get("clip", {}).get("transform", {}).get("y", 0)), 9) for segment in text_tracks[index].get("segments", [])}
        if not ys or any(abs(y - expected_y) > 1e-6 for y in ys):
            raise RuntimeError(f"Caption track {language} has unexpected Y positions: {sorted(ys)}")

    if any(t.get("type") == "audio" and t.get("segments") for t in patched.get("tracks", [])):
        raise RuntimeError("Unexpected separate audio track")
    videos = {v["id"]: v for v in patched.get("materials", {}).get("videos", [])}
    for video in videos.values():
        path = Path(video.get("path", "")).resolve()
        if not path.is_file() or not path.is_relative_to((draft_dir / "assets/videos").resolve()):
            raise RuntimeError(f"Missing or nonportable copied media: {path}")
    if shots:
        segments = [s for t in patched.get("tracks", []) if t.get("type") == "video" for s in t.get("segments", [])]
        segments.sort(key=lambda s: s["target_timerange"]["start"])
        if len(segments) != len(shots) or patched.get("duration") != micros(shots[-1]["end_s"]):
            raise RuntimeError("Draft clip count or duration mismatch")
        for segment, shot in zip(segments, shots):
            expected = {"start": micros(shot["start_s"]), "duration": micros(shot["end_s"] - shot["start_s"])}
            if segment.get("target_timerange") != expected:
                raise RuntimeError("Draft shot timing/order mismatch: " + shot["id"])
            video = videos.get(segment.get("material_id"))
            if not video or sha256(video["path"]) != shot["source_sha256"]:
                raise RuntimeError("Draft uses wrong media/order: " + shot["id"])
            if shot.get("audio_role", "dialogue") != "none" and segment.get("volume", 1) <= 0:
                raise RuntimeError("Approved generated audio was muted")
        materials = {t["id"]: t for t in texts}
        if len(texts) != len(shots) * len(caption_languages):
            raise RuntimeError("Unexpected caption material count")
        for index, language in enumerate(caption_languages):
            caption_segments = text_tracks[index].get("segments", [])
            if len(caption_segments) != len(shots):
                raise RuntimeError("Caption segment count mismatch")
            for segment, shot in zip(caption_segments, shots):
                material = materials[segment["material_id"]]
                caption = json.loads(material["content"])
                if caption.get("text") != shot["captions"][language] or segment["target_timerange"] != {
                    "start": micros(shot["start_s"]), "duration": micros(shot["end_s"] - shot["start_s"])}:
                    raise RuntimeError("Caption text or timing mismatch")

    # Rewrite both files from the same object so they remain identical.
    serialized = json.dumps(patched, ensure_ascii=False, indent=2) + "\n"
    info_path.write_text(serialized, encoding="utf-8")
    content_path.write_text(serialized, encoding="utf-8")
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path, help="capcut-mate repository root")
    parser.add_argument("--media-dir", required=True, type=Path)
    parser.add_argument("--draft-root", type=Path, default=None)
    parser.add_argument("--api-base", default="http://127.0.0.1:30000/openapi/capcut-mate/v1")
    parser.add_argument("--http-port", type=int, default=8765)
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe"))
    parser.add_argument("--dry-run", action="store_true", help="Probe inputs only; no API/draft writes")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    width = int(config.get("width", 1080))
    height = int(config.get("height", 1920))
    fps = int(config.get("fps", 30))
    if fps != 30:
        raise SystemExit("The current CapCut Mate create_draft API emits 30fps drafts; use fps=30.")
    media_root = args.media_dir.resolve()
    if not args.ffprobe:
        raise SystemExit("ffprobe is required for media validation; pass --ffprobe or add it to PATH")
    shots = preflight(config, media_root, args.ffprobe)
    style = config.get("caption_style", {})
    font_name = str(style.get("font", "Georgia"))
    font_size = float(style.get("font_size", 8))
    bold, italic = bool(style.get("bold", True)), bool(style.get("italic", True))
    font_path = resolve_font_file(font_name, bold, italic, style.get("font_path")) if config.get("subtitle_tracks") else None
    language_positions = {
        "es": float(style.get("es_transform_y", -700)),
        "zh": float(style.get("zh_transform_y", -500)),
    }
    caption_languages = config.get("subtitle_tracks", [])
    if args.dry_run:
        print(json.dumps({"shots": shots, "caption_languages": caption_languages, "api_writes": 0}, ensure_ascii=False, indent=2))
        return 0

    http_server = ThreadingHTTPServer(("127.0.0.1", args.http_port), partial(SimpleHTTPRequestHandler, directory=str(media_root)))
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    try:
        created = api_call(args.api_base, "create_draft", {"width": width, "height": height})
        draft_url = created["draft_url"]
        video_infos = []
        for shot in shots:
            file_path = (media_root / shot["video"]).resolve()
            if not file_path.exists():
                raise FileNotFoundError(file_path)
            start_us, end_us = micros(shot["start_s"]), micros(shot["end_s"])
            video_infos.append({
                "video_url": encoded_url(media_root, file_path, http_server.server_port),
                "width": int(shot.get("width", 720)),
                "height": int(shot.get("height", 1280)),
                "start": start_us,
                "end": end_us,
                "duration": end_us - start_us,
            })
        api_call(args.api_base, "add_videos", {"draft_url": draft_url, "video_infos": json.dumps(video_infos, ensure_ascii=False, separators=(",", ":"))})

        for language in caption_languages:
            captions = []
            for shot in shots:
                text = shot.get("captions", {}).get(language)
                if text is None:
                    raise RuntimeError(f"Missing {language} caption for shot {shot.get('id')}")
                captions.append({"start": micros(shot["start_s"]), "end": micros(shot["end_s"]), "text": text})
            api_call(args.api_base, "add_captions", {
                "draft_url": draft_url,
                "captions": json.dumps(captions, ensure_ascii=False, separators=(",", ":")),
                "text_color": style.get("text_color", "#FFFFFF"),
                "border_color": style.get("border_color", "#000000"),
                "alignment": 1,
                "font": font_name,
                "font_size": font_size,
                "line_max_width": float(style.get("line_max_width", 0.82)),
                "transform_x": 0,
                "transform_y": language_positions[language],
                "bold": bool(style.get("bold", True)),
                "italic": bool(style.get("italic", True)),
            })
        api_call(args.api_base, "save_draft", {"draft_url": draft_url})
    finally:
        http_server.shutdown()
        http_server.server_close()
        http_thread.join(timeout=3)

    query = parse_qs(urlparse(draft_url).query)
    draft_id = query.get("draft_id", [""])[0]
    if not draft_id:
        raise RuntimeError(f"Cannot parse draft_id from {draft_url}")
    source_dir = args.repo.resolve() / "output" / "draft" / draft_id
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    if args.draft_root:
        draft_root = args.draft_root.resolve()
    elif os.environ.get("DRAFT_SAVE_PATH"):
        draft_root = Path(os.environ["DRAFT_SAVE_PATH"]).resolve()
    else:
        draft_root = (Path(os.environ.get("LOCALAPPDATA", ".")) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft").resolve()
    destination = draft_root / str(config.get("draft_name", f"capcut-draft-{draft_id}"))
    if not destination.resolve().is_relative_to(draft_root) or destination.resolve() == draft_root:
        raise ValueError("Draft name escapes the requested draft root")
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source_dir, destination)
    rewrite_and_validate(destination, source_dir, width, height, fps, caption_languages, language_positions, font_name, font_size, shots, font_path, bold, italic)
    print(json.dumps({"draft_url": draft_url, "draft_id": draft_id, "draft_path": str(destination), "caption_languages": caption_languages,
                      "structural_qc": "passed", "jianying_gui_open": "requires_manual_verification"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
