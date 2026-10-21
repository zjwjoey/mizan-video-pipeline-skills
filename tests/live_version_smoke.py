#!/usr/bin/env python3
"""Opt-in version/approval/rollback smoke on synthetic media, no generation service."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/dreamina-canvas-bootstrap/scripts"))
from canvas_bootstrap import Bootstrap, CanvasCLI, GROUPS, file_hash, now, project_lock, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", required=True, type=Path)
    parser.add_argument("--cli")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    job = Bootstrap(args.production, CanvasCLI(args.cli))
    if not job.production.get("simulation_only"):
        raise ValueError("This smoke requires simulation_only=true")
    with project_lock(job.state_path.with_suffix(".lock")):
        job.discover()
        job.ensure_canvas()
        first = job.state["assets"]["CHAR01"][0]
        job.review("CHAR01", "v01", "approved", "Synthetic fixture approval for code validation, not production creative QC")
        spec = importlib.util.spec_from_file_location("example_generator", ROOT / "examples/mizan-family-party/create_example.py")
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        candidate = job.path.parent / "fixture-character-v02.png"
        fixture.png(candidate, (200, 60, 150))
        v2 = job.register(dict(first, local_path=str(candidate), file_hash=file_hash(candidate), source_type="generated", qc_status="pending_review"))
        if job.state["approved_versions"]["CHAR01"] != "v01":
            raise AssertionError("Pending version displaced approved v01")
        job.sync_asset(v2, 0)
        if job.register(dict(v2))["version"] != v2["version"]:
            raise AssertionError("Same content increased version")
        job.review("CHAR01", v2["version"], "approved", "Synthetic v02 approval for code validation")
        if job.state["approved_versions"]["CHAR01"] != v2["version"] or first["group_name"] != GROUPS[8]:
            raise AssertionError("New approval did not select/archive")
        job.review("CHAR01", "v01", "approved", "Synthetic rollback verification")
        if first["group_name"] != GROUPS[1] or v2["group_name"] != GROUPS[8]:
            raise AssertionError("Rollback did not restore active region")
        job.reconcile()
        if job.state["sync_status"] != "synced":
            raise AssertionError("Version smoke left remote drift")
        report = {"verified_at": now(), "test_kind": "real_public_cli_nonpaid_synthetic_qc", "canvas_url": job.state["canvas_url"],
                  "pending_preserves_v01": True, "v02_approval_switches_pointer": True,
                  "rollback_restores_active_region": True, "old_nodes_preserved": True,
                  "same_hash_no_new_version": True, "reconcile": "passed", "paid_operations": 0}
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
