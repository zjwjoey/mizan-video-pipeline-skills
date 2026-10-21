#!/usr/bin/env python3
"""Small GPT-Image-2.5-Ext client for safe single-submit image tasks."""
import argparse, hashlib, json, mimetypes, os, sys, tempfile, uuid
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
    if not args.record or not args.allow_paid:
        raise ValueError("generate requires --record and --allow-paid after explicit task authorization")
    record = Path(args.record)
    if record.exists():
        raise ValueError("Record already exists. Query the recorded task ID; uncertain submissions must not be repeated.")
    payload = {"model":"gpt-image-2.5-ext", "version":args.version, "prompt":args.prompt,
               "size":args.size, "resolution":args.resolution, "n":args.n}
    if args.image_url:
        payload["image_urls"] = args.image_url
    journal = {"request": {k:v for k,v in payload.items() if k != "image_urls"},
               "reference_hashes": [hashlib.sha256(u.encode("utf-8")).hexdigest() for u in args.image_url or []],
               "state": "submission_uncertain", "qc_status": "pending_review"}
    record.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents two processes from submitting the same task record.
    with record.open("x", encoding="utf-8") as stream:
        json.dump(journal, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    result = call(f"{BASE}/images/generations", "POST", json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
    task_id = result.get("id") or result.get("data", {}).get("id")
    journal.update(task_id=task_id, state="submitted" if task_id else "submission_uncertain")
    fd, temporary = tempfile.mkstemp(prefix=".gpt-record-", dir=record.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(journal, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, record)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps(result, ensure_ascii=False, indent=2))

def status(task_id):
    print(json.dumps(call(f"{BASE}/tasks/{quote(task_id)}?model=gpt-image-2.5-ext"), ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("upload"); p.add_argument("files", nargs="+")
    p = sub.add_parser("generate"); p.add_argument("--prompt", required=True); p.add_argument("--image-url", action="append"); p.add_argument("--version", default="flare", choices=["flare","sunburst"]); p.add_argument("--size", default="9:16"); p.add_argument("--resolution", default="1K", choices=["1K","2K","4K"]); p.add_argument("--n", type=int, default=1, choices=range(1,5)); p.add_argument("--record", required=True); p.add_argument("--allow-paid", action="store_true")
    p = sub.add_parser("status"); p.add_argument("task_id")
    args = parser.parse_args()
    if args.cmd == "upload": upload(args.files)
    elif args.cmd == "generate": generate(args)
    else: status(args.task_id)


if __name__ == "__main__":
    main()
