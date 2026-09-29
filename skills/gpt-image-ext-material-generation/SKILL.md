---
name: gpt-image-ext-material-generation
description: Generate storyboard stills with GPT-Image-2.5-Ext when reference-led image generation and strict prompt preservation are needed before video assembly.
---

# GPT-Image-2.5-Ext material generation

Use this skill after a shot has an approved image prompt and before its video task is submitted.

- Submit user-provided per-shot prompts verbatim. Use ordered image references for character and scene continuity; never append unapproved creative changes to the prompt.
- Before each billable POST, confirm the model, version, ratio, resolution, quantity, and selected references. Each POST creates a new paid task; poll only its returned task ID.
- For this project, retain the approved host image as reference 1 and the selected real-store scene image as reference 2. Do not reuse an AI frame with unwanted text as the scene anchor.
- Default to `flare`, `1K`, `9:16`, and `n=1` unless the user specifies otherwise. Keep task records and mark results `not_started`, `pass`, or `revise` after visual QC.
- QC rejects generated signage, price labels, unreadable pseudo-text, identity/outfit drift, store-geometry drift, or a frame that cannot connect naturally to the neighbouring shot.

## Structured storyboard execution

- Read the owner-confirmed shot record and honor `image_count` exactly for each shot; do not infer a fixed total image count.
- Resolve `host_anchor_id`, `scene_anchor_id`, and each `product_refs` ID to approved local reference files before a paid submission. Missing references stop the submission until supplied or explicitly waived by the owner.
- Keep `material_mode`, `image_priority`, `additional_refs`, `must_keep`, and `must_avoid` in the task record. Submit the approved per-shot image prompt verbatim.
- Generate anchor images first and wait for human approval before using them for child shots. Generated images remain `not_started` until QC; only `pass` images can move to video generation.
- Set `GPT_IMAGE_API_KEY` in the process environment. For compatibility with existing installations, `NANOBANANA2_API_KEY` is also accepted by the bundled client.

Use [scripts/gpt_image_ext.py](scripts/gpt_image_ext.py) for upload, submission, and task status. Read [references/api-contract.md](references/api-contract.md) when the response shape differs from the standard async format.
