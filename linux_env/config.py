"""Centralized environment configuration."""

import os


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost")
MODEL_NAME = os.getenv("MODEL_NAME", "dummy")
HF_TOKEN = os.getenv("HF_TOKEN", "dummy")
