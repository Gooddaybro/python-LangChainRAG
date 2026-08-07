ARG PYTHON_BASE_IMAGE=python:3.12-slim

FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ARG PIP_INDEX_URL=
ARG PIP_TRUSTED_HOST=

WORKDIR /app
COPY requirements.txt ./
RUN if [ -n "$PIP_INDEX_URL" ]; then \
      if [ -n "$PIP_TRUSTED_HOST" ]; then \
        pip install --no-cache-dir --index-url "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" -r requirements.txt; \
      else \
        pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.txt; \
      fi; \
    elif [ -n "$PIP_TRUSTED_HOST" ]; then \
      pip install --no-cache-dir --trusted-host "$PIP_TRUSTED_HOST" -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi
COPY clothing_assistant clothing_assistant
COPY langgraph.json ./
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "clothing_assistant.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
