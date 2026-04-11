import os

API_BASE_URL = os.getenv('API_BASE_URL')
API_KEY = os.getenv('API_KEY') or os.getenv('HF_TOKEN')
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')
LOCAL_MODE = not (API_BASE_URL and API_KEY)

# Backward compatibility for existing imports.
HF_TOKEN = API_KEY
