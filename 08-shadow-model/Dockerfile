FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PREDICTOR_LOG_PATH=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY researcher researcher
COPY ranker ranker
COPY training training
COPY serving serving
COPY utils utils
COPY gates gates

RUN useradd --create-home app \
    && mkdir /mlflow /data /shadow \
    && chown -R app /app /mlflow /data /shadow

USER app


FROM base AS scheduler

ARG SUPERCRONIC_VERSION=0.2.49
ARG SUPERCRONIC_SHA1SUM=e63c11a9726b775a6a11801e81af4f3fb926aa68

USER root
ADD https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN echo "${SUPERCRONIC_SHA1SUM}  /usr/local/bin/supercronic" | sha1sum -c - \
    && chmod +x /usr/local/bin/supercronic
COPY scheduler scheduler
USER app

CMD ["supercronic", "/app/scheduler/crontab"]


FROM base AS app
