# V2 Lite baseline audit

Baseline: main `2ae7ed3` (2026-10-19 review; all 17 tracked files read). Branch: `feature/mizan-canvas-bootstrap-v2`.

| Existing behavior | V2 Lite change |
| --- | --- |
| Four Skills; only image API and draft builder have execution scripts. Canvas operations are prose instructions. | Add a fifth independent non-generating Canvas bootstrap Skill and stdlib scripts. |
| No production/Canvas manifest; `host_anchor_id` / `scene_group` / `source_asset_id` / `pass` differ across handoffs. | Canonical stable shot/scene/character/asset IDs; evidence-aware migration instructions; no implicit QC approvals. |
| Resource upload can succeed while Canvas remains empty. | Require successful resource state plus a visible node containing that exact resource; roundtrip text verification. |
| No hash dedup, durable version selections or interrupted Canvas script state. | SHA256 dedup, preallocated identities, atomic journal, OS lock, local/remote reconcile. |
| GPT client records only after billable POST; optional record may be overwritten. | Durable pre-submit state, refuse repeated POST while status is uncertain, explicit record and paid-operation acknowledgement. |
| CapCut infers subtitle languages merely from populated caption keys. | Subtitles disabled by default, explicit language list only. Chinese review text never implicitly becomes subtitles. |
| CapCut `len(texts) != sum(...)` is always false; divergent draft JSON is overwritten without validation. | Check both JSON structures before edits, real timing/media/track checks, reject divergent originals. |
| CapCut starts HTTP service/creates draft before validating inputs and cannot prove embedded sound. | Probe all clips before mutation, preserve sound, check duration/aspect/order and no separate audio tracks. |
| Two Skills lack agents metadata; deployment says four Skills. | Add metadata and install the fifth Skill while retaining legacy standalone interfaces. |

No rewrite of the CapCut Mate server or Word templates. No paid generation during development. Actual capability/test results are recorded separately in `docs/V2_LITE_VALIDATION.md`.
