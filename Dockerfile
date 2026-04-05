FROM python:3.10-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn openai

EXPOSE 7860
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "7860"]

