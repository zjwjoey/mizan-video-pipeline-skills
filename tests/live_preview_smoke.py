"""Opt-in nonpaid gate test, only on a dedicated simulation project, never creative approval."""
import argparse
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/dreamina-canvas-bootstrap/scripts"))
from canvas_bootstrap import Bootstrap, CanvasCLI, file_hash, now, project_lock, write_json
from canvas_preview import require_preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    job = Bootstrap(args.production, CanvasCLI())
    if job.production.get("simulation_only") is not True:
        raise ValueError("Only simulation_only fixtures may receive automated test approvals")
    with project_lock(job.state_path.with_suffix(".lock")):
        job.discover()
        job.ensure_canvas(create=False)
        job.reconcile()
        job.approve_preview("AUTOMATED SYNTHETIC FIXTURE TEST", "No real creative project approved; nonpaid regression only", owner_confirmed=True)
        require_preview(job.production, job.state)
        changed = copy.deepcopy(job.production)
        changed["shots"].reverse()
        try:
            require_preview(changed, job.state)
        except ValueError:
            order_blocked = True
        else:
            raise AssertionError("Shot reorder failed to invalidate the gate")
        versions = [v for vs in job.state["assets"].values() for v in vs]
        if any(not Path(v["local_path"]).is_file() or file_hash(v["local_path"]) != v["file_hash"] for v in versions):
            raise AssertionError("Immutable input/output snapshot missing or corrupted")
        write_json(args.report, {"verified_at": now(), "test_kind": "real_nonpaid_sync_plus_synthetic_approval_gate",
                   "canvas_project_id": job.state["canvas_project_id"], "version_snapshots_verified": len(versions),
                   "preview_gate_passed": True, "shot_reorder_blocked": order_blocked, "paid_operations": 0,
                   "real_owner_creative_approval": False})
        print("Nonpaid synthetic preview gate and immutable snapshots verified; no production owner approval.")


if __name__ == "__main__": main()
