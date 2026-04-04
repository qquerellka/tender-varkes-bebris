# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

WORKDIR /app

ARG INSTALL_SEMANTIC=false

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=120

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --upgrade pip && \
    if [ "$INSTALL_SEMANTIC" = "true" ]; then \
        pip install --retries 10 --timeout 120 -e ".[semantic]"; \
    else \
        pip install --retries 10 --timeout 120 -e "."; \
    fi

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
