# BL Ranker — MLOps Home Assignment

This repo turns the researcher's BL payout model (CatBoost + TabPFN) into a production system:

- a **training pipeline** with test and production modes, tracked in MLflow
- a **model registry** with versioning and a `champion` alias
- a **FastAPI serving endpoint** that takes one user and returns ranked brands
- a **load test** (k6) that reports median and tail latency
- a **weekly retrain** (Sunday 05:00, Asia/Jerusalem), with Docker and Databricks options

The repo is built in stages. Each numbered folder is a self-contained snapshot that adds one step to the previous one. **[08-final/](08-final/) is the deliverable.** The earlier folders show how the design developed.

| Folder | What it adds |
|---|---|
| [00-run-locally/](00-run-locally/) | The researcher's original code, running as delivered |
| [01-productize-mlflow/](01-productize-mlflow/) | A training pipeline that logs runs to MLflow |
| [02-mlflow-prod-mode/](02-mlflow-prod-mode/) | Test and production modes, a registered pyfunc model, the `champion` alias, a dataset digest |
| [03-serving/](03-serving/) | A FastAPI `/predict` endpoint. The model loads once at startup instead of on every request |
| [04-dockerize/](04-dockerize/) | A Docker Compose stack: MLflow server, trainer, API |
| [05-load-tests/](05-load-tests/) | A k6 load test, plus a fix for sparse survey input found by the load test |
| [06-scheduler/](06-scheduler/) | A weekly retrain inside Docker (supercronic) |
| [07-databricks/](07-databricks/) | Training and the Unity Catalog registry on Databricks (Asset Bundle) |
| [08-final/](08-final/) | The final version: 07 plus the finishing fixes + rollback script |

All commands below run from inside `08-final/`.

---

## Layout of `08-final/`

```
researcher/     original researcher code, logic unchanged (only file paths come from env vars)
ranker/         BLRankerModel (MLflow pyfunc wrapper) + registry config
training/       train_pipeline.py: runs the researcher training, logs to MLflow, registers the model
serving/        FastAPI app (/predict, /health) + Pydantic input schema
scheduler/      crontab for the Docker weekly retrain
tests/load/     k6 load test, user sampler, runner script
databricks.yml  Databricks Asset Bundle (experiment, registered model, scheduled job)
databricks_job.py  adapter: Databricks job parameters → the same training pipeline
pyproject.toml  packages the code as a wheel for the Databricks job
rollback.py     moves the @champion alias to an earlier model version
Dockerfile, docker-compose.yml, requirements.txt, .env.example
```

## Prerequisites

- Python 3.13
- Docker with Compose v2
- A TabPFN API token from [Prior Labs](https://priorlabs.ai)
- The dataset `bl_full_data.csv`. It holds personal data, so it is **not in git**. Put it in `08-final/`.
- Optional: [k6](https://k6.io) to run the load test without Docker. Optional: the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/) for the Databricks part.

## Configuration

```bash
cp .env.example .env
```

| Variable | Meaning |
|---|---|
| `TABPFN_TOKEN` | Prior Labs API key |
| `INPUT_PATH` / `INPUT_FILE` | Folder (with a trailing `/`) and file name of the dataset |
| `MLFLOW_TRACKING_URI` | MLflow server, e.g. `http://127.0.0.1:5000` |
| `MLFLOW_EXPERIMENT_NAME` | Experiment name, e.g. `bl_payout_ranking` |
| `REGISTERED_MODEL_NAME` | Optional. Default is `bl_ranker`. On Unity Catalog use `catalog.schema.name` |

---

## Run with Docker (recommended)

```bash
docker compose build
docker compose up -d mlflow                 # MLflow UI at http://localhost:5000
docker compose run --rm trainer             # production training → registers a new version with alias @champion
docker compose up -d api                    # API at http://localhost:8000 (2 uvicorn workers)
docker compose up -d scheduler              # optional: weekly retrain, Sunday 05:00 Asia/Jerusalem
```

To run a test-mode training instead (train/test split, metrics only, nothing registered):

```bash
docker compose run --rm trainer --mode test
```

Stop everything:

```bash
docker compose --profile train --profile loadtest down
```

## Run without Docker

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt             # installs CPU-only torch through the extra index

set -a && source .env && set +a

mlflow server --host 127.0.0.1 --port 5000 \
  --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlartifacts &

python -m training.train_pipeline --mode test         # evaluate on the last 7 days
python -m training.train_pipeline --mode production   # train on all data, register, set @champion

uvicorn serving.app:app --port 8000
```

## Call the API

```bash
curl localhost:8000/health
# {"status": "ok", "model_version": "3"}

curl -X POST localhost:8000/predict -H 'Content-Type: application/json' -d '{
  "session_dt": "2026-01-09 16:52:51",
  "register_date": "2026-01-09 16:54:27",
  "campaign_id": 120227360861540306,
  "page": "example.com/app/business-loans",
  "device_type": "mobile",
  "auto_country": "United States",
  "auto_state": "Florida",
  "business_type": "LLC",
  "credit_score": "Good (650-719)",
  "industry": "construction",
  "loan_amount": "$100,000+",
  "loan_reason": "Business expansion",
  "monthly_revenue": "$50,000+",
  "time_in_business": "2+ years",
  "fname": "Jane",
  "lname": "Doe",
  "cellphone": 5550100000
}'
```

The response maps each brand to `{rank, expected_payout}`. The full input schema is in [serving/schemas.py](08-final/serving/schemas.py). Invalid input returns `422`. A user with fewer than 5 of the 8 survey answers returns `NO_RESULT`, which matches the researcher's own filtering rule.

The API serves whichever version has the `@champion` alias **when it starts**. Restart the API after a new production run.

### Rollback

Every production run registers a new version. Each version contains the model and its code (`code_paths`). To roll back, move the `@champion` alias to an earlier version, then restart the API:

```bash
set -a && source .env && set +a
python rollback.py                # newest version older than the current champion
python rollback.py --version 2    # a specific version
docker compose restart api
```

Example output:

```
bl_ranker@champion: v4 -> v2. Restart the API to serve it.
```

Without `--version`, the script picks the newest version older than the current champion, so it skips deleted versions. It refuses to run, and leaves `@champion` unchanged, when the target version doesn't exist, when it is already the champion, or when there is no older version. `GET /health` reports the version being served, so you can confirm the rollback after the restart. To roll forward again, run `python rollback.py --version <newer version>`.

Against the Docker stack, run the script from the host with `MLFLOW_TRACKING_URI=http://localhost:5000`. To roll back on Databricks, set `MLFLOW_TRACKING_URI=databricks` and `REGISTERED_MODEL_NAME=workspace.bl.bl_ranker`.

---

## Load test

```bash
tests/load/run_load_tests.sh --docker       # k6 in a container, against the compose API
tests/load/run_load_tests.sh --local        # local k6, against BASE_URL (default http://localhost:8000)
```

The test uses an open model (`constant-arrival-rate`) with 200 users sampled from the dataset. Each rate runs as its own stage. You can change the defaults with `RATES=0.5,1,2,3` and `STAGE_SECONDS=60`. Results are written to `tests/load/results/summary-<timestamp>.json`.

Measured results:

| | p50 | p95 | p99 |
|---|---|---|---|
| Original predictor (loads everything per request) | 8.7 s | — | — |
| Load once at startup, 0.5 req/s | 1.19 s | 1.83 s | 2.06 s |

Above about 1 req/s, latency is limited by the hosted TabPFN API (60 predictions/min), not by the server. At 2 req/s requests queue. At 3 req/s the API starts returning 429 errors. The Part 2 write-up discusses this and the options for fixing it (local TabPFN, caching, fallback).

---

## Databricks

Training and the model registry can also run on Databricks. Serving stays in Docker. The same training code runs in both places, and only the configuration changes. [databricks_job.py](08-final/databricks_job.py) maps job parameters and a secret scope to the environment variables the pipeline already reads.

On every deploy the bundle builds the code into a wheel ([pyproject.toml](08-final/pyproject.toml)) and uploads it to the `workspace.bl.artifacts` volume, and the serverless job installs it like any other package. Dependencies still come from `requirements.txt`. The job doesn't load code from the workspace file system, because serverless failed to read bundle files there (`[Errno 5] Input/output error`).

One-time workspace setup:

```bash
databricks auth login --host <workspace-url> --profile bl
export DATABRICKS_CONFIG_PROFILE=bl

databricks schemas create bl workspace
databricks volumes create workspace bl data MANAGED
databricks volumes create workspace bl artifacts MANAGED
databricks fs cp bl_full_data.csv dbfs:/Volumes/workspace/bl/data/
databricks secrets create-scope bl
databricks secrets put-secret bl TABPFN_TOKEN
```

Deploy and run:

```bash
databricks bundle validate
databricks bundle deploy                    # dev target: names get a prefix, schedule is paused
databricks bundle run bl_training --params mode=test
databricks bundle deploy -t prod            # prod: workspace.bl.bl_ranker, Sunday 05:00 Asia/Jerusalem
```

The model is registered in Unity Catalog as `workspace.bl.bl_ranker`. To serve it from Docker, set `MLFLOW_TRACKING_URI=databricks`, `MLFLOW_REGISTRY_URI=databricks-uc`, and `REGISTERED_MODEL_NAME=workspace.bl.bl_ranker`.

---

## Notes

- The researcher's code is **not modified**. Test metrics come from parsing the researcher's training log, and the log is stored as a run artifact.
- The predictor reads a module-level global, so each API process handles one request at a time behind a lock. The API scales by adding uvicorn workers (`API_WORKERS`).
- The TabPFN API has a daily token quota that resets at 00:00 UTC. When the quota runs out, training and `/predict` both fail until it resets.
- The design decisions, known issues and possible improvements are covered in the Part 2 write-up.
