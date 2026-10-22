FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PREDICTOR_LOG_PATH=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY researcher researcher
COPY ranker ranker
COPY training training
COPY serving serving
COPY utils utils

RUN useradd --create-home app \
    && mkdir /mlflow /data \
    && chown app /mlflow /data


USER app