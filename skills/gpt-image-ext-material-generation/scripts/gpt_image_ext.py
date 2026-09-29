#!/usr/bin/env python3
"""Small GPT-Image-2.5-Ext client for safe single-submit image tasks."""
import argparse, json, mimetypes, os, sys, uuid
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://api.ai.hzagent.cn/v1"

def token():
    value = os.environ.get("GPT_IMAGE_API_KEY") or os.environ.get("NANOBANANA2_API_KEY")
    if not value:
        raise SystemExit("Set GPT_IMAGE_API_KEY (or legacy NANOBANANA2_API_KEY) in this process.")
    return value

def call(url, method="GET", data=None, content_type=None):
    headers = {"Authorization": f"Bearer {token()}"}
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))

def upload(files):
    boundary = "----gptimage" + uuid.uuid4().hex
    body = bytearray()
    for filename in files:
        path = Path(filename)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="images"; filename="{path.name}"\r\n'.encode())
        body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    print(json.dumps(call(f"{BASE}/uploads/images", "POST", bytes(body), f"multipart/form-data; boundary={boundary}"), ensure_ascii=False, indent=2))

def generate(args):
    payload = {"model":"gpt-image-2.5-ext", "version":args.version, "prompt":args.prompt,
               "size":args.size, "resolution":args.resolution, "n":args.n}
    if args.image_url:
        payload["image_urls"] = args.image_url
    result = call(f"{BASE}/images/generations", "POST", json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
    if args.record:
        Path(args.record).write_text(json.dumps({"request":payload, "response":result, "qc_status":"not_started"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

def status(task_id):
    print(json.dumps(call(f"{BASE}/tasks/{quote(task_id)}?model=gpt-image-2.5-ext"), ensure_ascii=False, indent=2))

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("upload"); p.add_argument("files", nargs="+")
p = sub.add_parser("generate"); p.add_argument("--prompt", required=True); p.add_argument("--image-url", action="append"); p.add_argument("--version", default="flare", choices=["flare","sunburst"]); p.add_argument("--size", default="9:16"); p.add_argument("--resolution", default="1K", choices=["1K","2K","4K"]); p.add_argument("--n", type=int, default=1, choices=range(1,5)); p.add_argument("--record")
p = sub.add_parser("status"); p.add_argument("task_id")
args = parser.parse_args()
if args.cmd == "upload": upload(args.files)
elif args.cmd == "generate": generate(args)
else: status(args.task_id)
