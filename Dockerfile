ARG PYTHON_BASE_IMAGE=python:3.12-slim

FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY clothing_assistant clothing_assistant
COPY langgraph.json ./
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "clothing_assistant.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
