#!/usr/bin/env python3
"""Materialize labeled synthetic import fixtures locally; no model/service calls."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import uuid
import wave
import zlib


def png(path, rgb, width=180, height=320):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def create(output, ffmpeg=None):
    output = Path(output)
    production = output / "production_manifest.json"
    if production.exists():
        raise FileExistsError("Example already exists; use sync/resume rather than recreating it")
    p = json.loads(Path(__file__).with_name("production_manifest.json").read_text(encoding="utf-8"))
    p["project_id"] = str(uuid.uuid4())
    for index, name in enumerate(("人物", "门店", "商品")):
        png(output / "素材" / (name + ".png"), ((index * 70 + 20) % 255, 90, 220 - index * 50))
    with wave.open(str(output / "素材/测试音频.wav"), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\x00\x00" * 16000 * 4)
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if ffmpeg:
        video = output / "素材/模拟片段.mp4"
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=180x320:r=30:d=4",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", str(video)], check=True)
        p["assets"].append({"asset_id": "VIDEO_FIXTURE", "asset_type": "video", "description": "本地合成测试片段非AI产物",
                            "local_path": "素材/模拟片段.mp4", "source_type": "existing", "qc_status": "pending_check"})
    production.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return production


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ffmpeg")
    args = parser.parse_args()
    print(create(args.out, args.ffmpeg))
