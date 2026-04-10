"""Centralized environment configuration."""

import os


API_BASE_URL = os.getenv("API_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
