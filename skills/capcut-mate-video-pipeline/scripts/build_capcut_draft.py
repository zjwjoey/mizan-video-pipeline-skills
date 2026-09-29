#!/usr/bin/env python3
"""Build a local CapCut Mate/Jianying draft from a shot config.

Example config:
{
  "draft_name": "MIZAN_P01-P02_Bilingual",
  "width": 1080,
  "height": 1920,
  "fps": 30,
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
import json
import os
import shutil
import subprocess
import sys
import time
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
    relative = file_path.relative_to(media_root).as_posix()
    encoded = "/".join(quote(part) for part in relative.split("/"))
    return f"http://127.0.0.1:{port}/{encoded}"


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
) -> dict:
    info_path = draft_dir / "draft_info.json"
    content_path = draft_dir / "draft_content.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    if info.get("canvas_config", {}).get("width") != width or info.get("canvas_config", {}).get("height") != height:
        raise RuntimeError("Draft canvas does not match the requested dimensions")
    if int(info.get("fps", 0)) != int(fps):
        raise RuntimeError("Draft fps does not match the requested fps")

    old_json_root = str(old_root).replace("\\", "\\\\")
    new_json_root = str(draft_dir).replace("\\", "\\\\")
    raw_objects = []
    for path in (info_path, content_path):
        raw = path.read_text(encoding="utf-8")
        if old_json_root in raw:
            raw = raw.replace(old_json_root, new_json_root)
        raw_objects.append(json.loads(raw))

    patched = raw_objects[0]
    texts = patched.get("materials", {}).get("texts", [])
    if len(texts) != sum(1 for _ in texts):
        raise RuntimeError("Malformed text materials")
    for material in texts:
        material["font_name"] = font_name
        material["font_title"] = font_name
        for font in material.get("fonts", []):
            font["title"] = font_name
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

    # Rewrite both files from the same object so they remain identical.
    serialized = json.dumps(patched, ensure_ascii=False, indent=2) + "\n"
    info_path.write_text(serialized, encoding="utf-8")
    content_path.write_text(serialized, encoding="utf-8")
    for video in patched.get("materials", {}).get("videos", []):
        if not Path(video.get("path", "")).exists():
            raise RuntimeError(f"Missing copied media: {video.get('path')}")
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path, help="capcut-mate repository root")
    parser.add_argument("--media-dir", required=True, type=Path)
    parser.add_argument("--draft-root", type=Path, default=None)
    parser.add_argument("--api-base", default="http://127.0.0.1:30000/openapi/capcut-mate/v1")
    parser.add_argument("--http-port", type=int, default=8765)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    width = int(config.get("width", 1080))
    height = int(config.get("height", 1920))
    fps = int(config.get("fps", 30))
    if fps != 30:
        raise SystemExit("The current CapCut Mate create_draft API emits 30fps drafts; use fps=30.")
    media_root = args.media_dir.resolve()
    shots = config.get("shots", [])
    if not shots:
        raise SystemExit("config.shots is empty")
    style = config.get("caption_style", {})
    font_name = str(style.get("font", "Georgia"))
    font_size = float(style.get("font_size", 8))
    language_positions = {
        "es": float(style.get("es_transform_y", -700)),
        "zh": float(style.get("zh_transform_y", -500)),
    }
    caption_languages = [lang for lang in ("es", "zh") if any(lang in shot.get("captions", {}) for shot in shots)]

    http_process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(args.http_port), "--bind", "127.0.0.1"],
        cwd=str(media_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.6)
        created = api_call(args.api_base, "create_draft", {"width": width, "height": height})
        draft_url = created["draft_url"]
        video_infos = []
        for shot in shots:
            file_path = (media_root / shot["video"]).resolve()
            if not file_path.exists():
                raise FileNotFoundError(file_path)
            start_us, end_us = micros(shot["start_s"]), micros(shot["end_s"])
            video_infos.append({
                "video_url": encoded_url(media_root, file_path, args.http_port),
                "width": int(shot.get("width", 720)),
                "height": int(shot.get("height", 1280)),
                "start": start_us,
                "end": end_us,
                "duration": int(shot.get("duration_us", end_us - start_us)),
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
        http_process.terminate()
        try:
            http_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            http_process.kill()

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
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source_dir, destination)
    rewrite_and_validate(destination, source_dir, width, height, fps, caption_languages, language_positions, font_name, font_size)
    print(json.dumps({"draft_url": draft_url, "draft_id": draft_id, "draft_path": str(destination), "caption_languages": caption_languages}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
