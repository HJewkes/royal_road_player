# Parked code (not wired into the pipeline)

This tree holds work that landed on `origin/main` (PRs #1–#3, AI-authored)
**after** the backend was restructured locally (`3201c5a`, "replace legacy
architecture with simplified module structure"). Those PRs targeted the old
layered architecture (`controllers/`, `services/`, `data/`, `text_processing/`,
`web/app.py`, `tts/engine.py`), which no longer exists in the live tree.

Rather than merge it against a layout it was never written for, the *value* is
preserved here, **deliberately disconnected from the live pipeline**. Nothing
under `backend/src/` imports anything in here, and it sits outside the
`backend/` import and test-collection roots, so it cannot affect scraping,
chunking, TTS, or validation. Revive a piece by porting it into the current
structure — don't add `parked/` to `PYTHONPATH`.

## Layout

### `backend/` — Python from PRs #1 and #2
- `src/text_processing/dialogue/` — LLM-based dialogue / speaker-detection
  module (models, prompts, validator, service). **Needs** `src/llm/ollama_client`
  (also parked here) and an Ollama runtime. Original paths under `src.*`.
- `src/llm/` — Ollama client the dialogue module depends on; removed from the
  live tree in the restructure.
- `src/monitoring/` — AWS CloudWatch / metrics / secrets / SNS / tracing.
- `src/storage/` — S3 / SQS / file storage backends.
- `src/services/audio_formatter.py`, `src/tts/model_registry.py` — standalone
  helpers (no internal imports).
- `tests/text_processing/` — the dialogue module's test suite.
- `docs/DIALOGUE_TESTING.md` — testing guide for the dialogue module.

Extra runtime deps these expect (NOT added to live `backend/requirements.txt`):
`boto3`, plus the Ollama client/runtime for the dialogue module.

### `infra/` — IaC / config from PR #1
Docker (`Dockerfile`, `docker-compose*.yml`), Kubernetes (`k8s/`), Helm
(`helm/`), Terraform (`terraform/`), observability stacks (`monitoring/` —
Grafana / Loki / Prometheus / Promtail / Tempo), CI/CD (`.github/workflows/`),
and deploy scripts. This is cloud-scale scaffolding (Postgres, S3, SQS, k8s)
that does not match the current single-user, filesystem-only design — kept for
reference, not active. The CI workflows are under `infra/.github/` (not the repo
root `.github/`), so they do **not** run.

## Kept live instead of parked
The research/analysis docs from these PRs were promoted to the live `docs/`
(`SPEAKER_DETECTION_RESEARCH.md`, `EBOOK2AUDIOBOOK_ANALYSIS.md`,
`EBOOK2AUDIOBOOK_OPPORTUNITIES.md`). The TTS "s"-cutoff fix (PR #3) was ported
into `backend/src/tts/xtts.py`.
