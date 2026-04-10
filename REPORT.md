# REPORT

## What was changed
- Standardized shared config in `config.py` to only use:
  - `API_BASE_URL = os.environ.get("API_BASE_URL")`
  - `API_KEY = os.environ.get("API_KEY")`
  - `MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")`
- Updated `inference.py` to import `API_BASE_URL`, `API_KEY`, and `MODEL_NAME` from `config.py`.
- Added required guard in `inference.py`:
  - `if not API_BASE_URL or not API_KEY: raise ValueError("Missing API_BASE_URL or API_KEY")`
- Ensured OpenAI client in `inference.py` is initialized only with:
  - `OpenAI(base_url=API_BASE_URL, api_key=API_KEY)`
- Updated `api/server.py` to remove legacy token variable usage and use `API_KEY` consistently.
- Updated `README.md` to remove legacy token variable references and document `API_KEY`.

## Why this is required for evaluation
- The evaluator tracks LLM traffic through the provided OpenAI-compatible proxy and key.
- Consistent use of `API_BASE_URL` and `API_KEY` ensures calls are observable by the validator.
- Removing legacy/fallback key names prevents accidental bypass of the evaluator’s proxy path.
