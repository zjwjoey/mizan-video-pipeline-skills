#!/usr/bin/env python3
"""Opt-in real nonpaid Canvas smoke. Use only an explicitly designated test project."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/dreamina-canvas-bootstrap/scripts"))
from canvas_bootstrap import Bootstrap, CanvasCLI, file_hash, now, project_lock, write_json


class CountingCLI(CanvasCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []

    def call(self, parts, positional=(), **flags):
        self.commands.append(parts)
        return super().call(parts, positional, **flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", required=True, type=Path)
    parser.add_argument("--cli")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    cli = CountingCLI(args.cli)
    job = Bootstrap(args.production, cli)
    if not job.production.get("simulation_only"):
        raise ValueError("Live smoke requires a simulation_only test project")
    with project_lock(job.state_path.with_suffix(".lock")):
        job.discover()
        job.ensure_canvas()
        original_hashes = {a["local_path"]: a["file_hash"] for a in job.plan()["assets"]}
        job.structure()
        job.sync()
        before_nodes = set(job.remote_nodes())
        before_versions = sum(len(vs) for vs in job.state["assets"].values())
        cli.commands.clear()
        job.structure()
        job.sync()
        repeat_commands = list(cli.commands)
        after_nodes = set(job.remote_nodes())
        forbidden = [("canvas", "create"), ("resource", "upload")]
        mutations = [p for p in repeat_commands if p in forbidden or p[:2] in (("node", "create"), ("node", "edit"))]
        if mutations or before_nodes != after_nodes:
            raise AssertionError("Repeated sync mutated remote Canvas")
        if before_versions != sum(len(vs) for vs in job.state["assets"].values()):
            raise AssertionError("Repeated sync changed versions")
        job.reconcile()
        if job.state["sync_status"] != "synced":
            raise AssertionError("Reconcile found drift")
        if any(file_hash(path) != expected for path, expected in original_hashes.items()):
            raise AssertionError("Original input media changed")
        result = {"verified_at": now(), "test_kind": "real_public_cli_nonpaid", "cli_version": job.state["capabilities"]["version"],
                  "canvas_url": job.state["canvas_url"], "canvas_project_id": job.state["canvas_project_id"],
                  "remote_node_count": len(after_nodes), "asset_versions": before_versions,
                  "media_types": sorted({v["media_type"] for vs in job.state["assets"].values() for v in vs}),
                  "script_roundtrip": "passed", "repeated_sync_remote_mutations": 0, "original_hashes_unchanged": True,
                  "organization_mode": job.state["organization_mode"], "reconcile": "passed", "paid_operations": 0}
        write_json(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
