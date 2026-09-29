# API contract

- Endpoint: `POST https://api.ai.hzagent.cn/v1/images/generations`
- Model: `gpt-image-2.5-ext`
- Authentication: `GPT_IMAGE_API_KEY` environment variable, sent as a bearer token. The bundled client also accepts the legacy `NANOBANANA2_API_KEY` name.
- Reference images: upload local files to `/v1/uploads/images`, then send returned URLs in `image_urls`.
- Poll the returned ID through `GET /v1/tasks/{id}?model=gpt-image-2.5-ext`; do not submit again while it is pending.
