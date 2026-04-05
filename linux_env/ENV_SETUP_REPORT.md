# Environment Setup Report

Date: 2026-04-05
Scope: Hugging Face Spaces (Docker) compatibility for environment variables and OpenAI client setup.

## Centralized Configuration

Added `config.py` with safe defaults:

- `API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost")`
- `MODEL_NAME = os.getenv("MODEL_NAME", "dummy")`
- `HF_TOKEN = os.getenv("HF_TOKEN", "dummy")`

This allows local and container runs even when variables are unset.

## Where Env Vars Are Used

### `inference.py`

- Imports env constants from `config.py`.
- Keeps OpenAI usage and initializes client as:

```python
from openai import OpenAI
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "dummy"
)
```

- Inference output format remains unchanged (`[START]`, `[STEP]`, `Output:`, `[END]`).

### `api/server.py`

- Imports env constants from `config.py` (with package-safe fallback import path).
- Stores them in `app.state`:
  - `app.state.api_base_url`
  - `app.state.model_name`
  - `app.state.hf_token`

No API endpoint behavior was changed.

## Fallback Behavior

If environment variables are missing:

- `API_BASE_URL` defaults to `http://localhost`
- `MODEL_NAME` defaults to `dummy`
- `HF_TOKEN` defaults to `dummy`

Result:
- App does not crash from missing env configuration.
- Inference and API imports/run paths remain functional.

## Hugging Face Spaces Notes

In HF Spaces (Docker), secrets/variables can be set in Space settings:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

If these are provided by Spaces, runtime uses them automatically.
If not provided, safe defaults keep the app bootable for smoke tests.

## Validation Summary

- Static checks: no diagnostics in `config.py`, `inference.py`, `api/server.py`.
- Runtime check: defaults load correctly without env vars.
- Runtime check: `inference.py` executes and preserves required output format.
