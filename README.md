# BL Ranker — MLOps Home Assignment

This repo turns the researcher's BL payout model (CatBoost + TabPFN) into a production system:

- a **training pipeline** with test and production modes, tracked in MLflow
- a **model registry** with versioning, `champion` and `challenger` aliases
- a **two-gate promotion**: an offline metrics gate, then a shadow test on live traffic
- a **FastAPI serving endpoint** that takes one user and returns ranked brands
- a **load test** (k6) that reports median and tail latency
- a **weekly retrain** (Sunday 05:00, Asia/Jerusalem), with Kubernetes, Docker and Databricks options
- **GitOps deployment** on Kubernetes: ArgoCD syncs the cluster from git, and model promotions and rollbacks roll out with no downtime

The repo is built in stages. Each numbered folder is a self-contained snapshot that adds one step to the previous one. **[09-gitops/](09-gitops/) is the deliverable.** The earlier folders show how the design developed.

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
| [08-shadow-model/](08-shadow-model/) | 07 plus a rollback script and two-gate promotion (offline gate + shadow model) |
| [09-gitops/](09-gitops/) | The final version: serving on Kubernetes, deployed by ArgoCD from git, zero-downtime model rollouts and rollbacks |

All commands below run from inside `09-gitops/`.

---

## Layout of `09-gitops/`

```
researcher/     original researcher code, logic unchanged (only file paths come from env vars)
ranker/         BLRankerModel (MLflow pyfunc wrapper) + registry config
gates/          promotion gates: offline_gate.py (metrics), shadow_gate.py (live comparison), gate_config.py (thresholds)
training/       train_pipeline.py: runs the researcher training, logs to MLflow, registers the model
serving/        FastAPI app (/predict, /health), Pydantic input schema, shadow.py (mirrors requests to the challenger)
scheduler/      crontab: weekly retrain (Sun 05:00) + daily shadow gate (06:00)
tests/load/     k6 load test, user sampler, runner script
databricks.yml  Databricks Asset Bundle (experiment, registered model, scheduled job)
databricks_job.py  adapter: Databricks job parameters → the same training pipeline
pyproject.toml  packages the code as a wheel for the Databricks job
rollback.py     moves the @champion alias to an earlier model version and commits it to git
gitops/         write_back.py: commits the deployed champion/challenger versions to git (deploy/charts/bl-ranker/models.yaml)
deploy/         Kubernetes: Helm chart, ArgoCD apps (app of apps), Terraform that installs ArgoCD
Dockerfile, docker-compose.yml, requirements.txt, .env.example
docker-compose.databricks.yml  override: API serves the model from the Databricks registry
```

## Prerequisites

- Python 3.13
- Docker with Compose v2
- For the Kubernetes deployment: a cluster (minikube for local), kubectl, Helm and Terraform
- A TabPFN API token from [Prior Labs](https://priorlabs.ai)
- The dataset `bl_full_data.csv`. It holds personal data, so it is **not in git**. Put it in `09-gitops/`.
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
docker compose run --rm trainer             # production training → registers a new version, runs the offline gate
docker compose up -d api api-shadow         # API at http://localhost:8000 (2 workers) + shadow service for @challenger
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
python -m training.train_pipeline --mode production   # evaluate, train on all data, register, offline gate
python -m gates.shadow_gate                           # promote the challenger if the shadow test passed

uvicorn serving.app:app --port 8000
```

## Call the API

```bash
curl localhost:8000/health
# {"status": "ok", "alias": "champion", "model_version": "3"}

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

The response maps each brand to `{rank, expected_payout}`. The full input schema is in [serving/schemas.py](09-gitops/serving/schemas.py). Invalid input returns `422`. A user with fewer than 5 of the 8 survey answers returns `NO_RESULT`, which matches the researcher's own filtering rule.

On Kubernetes, each service serves the version pinned in git ([deploy/charts/bl-ranker/models.yaml](09-gitops/deploy/charts/bl-ranker/models.yaml)). Under Docker Compose there is no pinned version, so the API serves whichever version has the `@champion` alias when it starts.

### Promotion: two gates

A new model only replaces the champion after it passes two gates.

1. **Offline gate** ([gates/offline_gate.py](09-gitops/gates/offline_gate.py)), at the end of every production run. The run first trains in test mode to get holdout metrics, then trains on all data and registers the version **without** moving `@champion`. The version passes if CatBoost F1 ≥ 0.40 and payout MAE ≤ $3.00, F1 dropped by at most 0.03 and MAE rose by at most 10% from the champion's, and the data has at least as many rows and ends no earlier. A pass gives it the `@challenger` alias. A failure leaves it registered with its reasons in the `offline_gate_reasons` tag. The very first model becomes champion directly (`bootstrap`).
2. **Shadow gate** ([gates/shadow_gate.py](09-gitops/gates/shadow_gate.py)), daily at 06:00. The `api-shadow` service serves `@challenger`. After the API answers a user, it sends 5% of requests (`SHADOW_SAMPLE_RATE`) to the shadow service in the background and logs the comparison to `/shadow/shadow_log.jsonl`: versions, latencies, whether the top brand matches, and the Kendall tau rank correlation. User data is not logged. After at least 20 hours and 30 mirrored requests, the gate promotes the challenger if top-1 agreement ≥ 70%, mean Kendall tau ≥ 0.5, challenger errors ≤ 2%, and its p95 latency ≤ 1.5× the champion's. Otherwise it removes `@challenger`. Not enough data yet means it waits and checks again the next day.

Thresholds are in [gates/gate_config.py](09-gitops/gates/gate_config.py). Every decision is written as tags on the model version (`offline_gate`, `shadow_gate`, `*_reasons`, `shadow_*` statistics), so the registry shows why each version was or wasn't promoted.

The shadow service is a separate process on purpose. The researcher's predictor keeps the user in a module-level global, and MLflow imports a model's code only once per process, so two models in one process would share that global and run the same code.

Each gate decision is also committed to git: the gate first updates `models.yaml` (see [Kubernetes and GitOps](#kubernetes-and-gitops)), then moves the alias. ArgoCD rolls the change out. Under Docker Compose, which has no git write-back, restart the services after a promotion: `docker compose restart api api-shadow`.

### Rollback

Every production run registers a new version. Each version contains the model and its code (`code_paths`). On Kubernetes, rolling back is a git change: either `git revert` the promotion commit, or run `rollback.py`, which commits the earlier version to `models.yaml` and moves `@champion`. ArgoCD then rolls the API back with no downtime. Under Docker Compose, run the script and restart the API:

```bash
set -a && source .env && set +a
python rollback.py                # newest version older than the current champion
python rollback.py --version 2    # a specific version
docker compose restart api
```

Example output:

```
committed to main: bl_ranker: v2 champion (rollback from v4)
bl_ranker@champion: v4 -> v2
```

Without `--version`, the script picks the newest version older than the current champion, so it skips deleted versions. It refuses to run, and leaves `@champion` unchanged, when the target version doesn't exist, when it is already the champion, or when there is no older version. `GET /health` reports the version being served, so you can confirm the rollback after the restart. To roll forward again, run `python rollback.py --version <newer version>`.

Against the Docker stack, run the script from the host with `MLFLOW_TRACKING_URI=http://localhost:5000`. To roll back on Databricks, set `MLFLOW_TRACKING_URI=databricks` and `REGISTERED_MODEL_NAME=workspace.bl.bl_ranker`.

---

## Kubernetes and GitOps

Production serving runs on Kubernetes and is deployed by ArgoCD from this git repo. Git is the source of truth for what runs: nobody runs `kubectl apply` or restarts a service by hand.

```
gate passes ──commit──▶ git: models.yaml ──ArgoCD sync──▶ Deployment spec changes ──▶ rolling update
                         (champion: '3')                    (MODEL_VERSION=3)           new pod ready → old pod removed
```

**What is in [deploy/](09-gitops/deploy/):**

- [bootstrap/](09-gitops/deploy/bootstrap/) and [modules/argocd/](09-gitops/deploy/modules/argocd/): Terraform that installs ArgoCD with its Helm chart.
- [root-app.yaml](09-gitops/deploy/root-app.yaml): the ArgoCD "app of apps". It watches [apps/](09-gitops/deploy/apps/) and creates every Application it finds there.
- [apps/bl-ranker.yaml](09-gitops/deploy/apps/bl-ranker.yaml): deploys the chart into the `bl-ranker` namespace with automatic sync, `prune` and `selfHeal` (manual changes in the cluster are reverted to what git says).
- [charts/bl-ranker/](09-gitops/deploy/charts/bl-ranker/): the Helm chart.
  - `api` serves the champion (2 replicas) and `api-shadow` serves the challenger (1 replica).
  - `mlflow` is the registry (sqlite and artifacts on a volume).
  - The `training` CronJob runs Sunday 05:00 and the `shadow-gate` CronJob runs daily at 06:00.
  - [models.yaml](09-gitops/deploy/charts/bl-ranker/models.yaml) holds the deployed versions. The gates write to it, and nobody else does.

**Why there's no downtime:**

- The Deployments use `RollingUpdate` with `maxUnavailable: 0` and `maxSurge: 1`. Kubernetes starts a new pod and sends it traffic only after its readiness probe (`/health`) passes. Uvicorn answers only after the model has loaded. Only then does Kubernetes remove an old pod.
- A `preStop` sleep keeps the old pod serving while it is taken out of the Service, and a 90 s grace period lets in-flight predictions finish.
- If a new version fails to load, its pod never becomes ready, the rollout stalls and the old pods keep serving.
- A PodDisruptionBudget keeps at least one `api` pod up during node maintenance.

The same mechanism covers new models, rollbacks, new images and crashed pods.

**Model versions in git.** `models.yaml` holds `champion` and `challenger`. The value is a version number, `none` (no model), or empty (serve whatever `@champion` points to at startup, used before the first gate runs). The chart passes it to the pods as `MODEL_VERSION`. A change to it changes the pod spec, and that triggers the rollout. [gitops/write_back.py](09-gitops/gitops/write_back.py) clones the repo, edits the file, commits as `bl-ranker-gates`, and pushes, with retries if someone else pushed first. It authenticates with `GITOPS_TOKEN`, a GitHub token that can write to the repo.

The registry aliases still move as before, so the registry shows what was approved and git shows what is deployed. Git is updated first. If the push fails, the gate fails and the alias doesn't move, so the two never disagree.

**Set up a local cluster:**

```bash
minikube start --memory=6g --cpus=4

cd deploy/bootstrap && terraform init && terraform apply && cd ../..   # installs ArgoCD

docker build --target app -t bl-ranker:local . && minikube image load bl-ranker:local

kubectl create namespace bl-ranker
kubectl -n bl-ranker create secret generic bl-ranker-secrets \
  --from-literal=TABPFN_TOKEN=... --from-literal=GITOPS_TOKEN=...

kubectl apply -f deploy/root-app.yaml       # ArgoCD takes over from here
```

To give the training CronJob its data, copy the dataset into the `training-data` volume (for example, from a temporary pod that mounts it, with `kubectl cp`). To see the ArgoCD UI: `kubectl -n argocd port-forward svc/argocd-server 8080:443`. The `admin` password is in the `argocd-initial-admin-secret` secret. To call the API: `kubectl -n bl-ranker port-forward svc/api 8000:8000`.

**Databricks registry.** Set `databricks.enabled: true` and `databricks.host` in `values.yaml`, and add `DATABRICKS_TOKEN` to the secret. The pods then read models from Unity Catalog. The in-cluster MLflow and the training CronJob are turned off, because Databricks trains. Set `GITOPS_REPO_URL` and `GITOPS_TOKEN` in the Databricks job too, so the offline gate commits its challenger.

**Images.** The chart uses `image.repository` and `image.tag` from `values.yaml`. Locally the image is loaded into minikube. In a real cluster, CI builds the image, pushes it to a registry, and commits the new tag to `values.yaml`, and ArgoCD rolls it out the same way.

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

Training and the model registry can also run on Databricks. Serving stays in Kubernetes or Docker. The same training code runs in both places, and only the configuration changes. [databricks_job.py](09-gitops/databricks_job.py) maps job parameters and a secret scope to the environment variables the pipeline already reads.

On every deploy the bundle builds the code into a wheel ([pyproject.toml](09-gitops/pyproject.toml)) and uploads it to the `workspace.bl.artifacts` volume, and the serverless job installs it like any other package. Dependencies still come from `requirements.txt`. The job doesn't load code from the workspace file system, because serverless failed to read bundle files there (`[Errno 5] Input/output error`).

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

The model is registered in Unity Catalog as `workspace.bl.bl_ranker` (`dev` deploys use `workspace.bl.dev_<user>_bl_ranker`). To serve it from Docker instead of the local MLflow server, add `DATABRICKS_HOST` and `DATABRICKS_TOKEN` to `.env` (see `.env.example`) and start the API with the override file:

```bash
docker compose -f docker-compose.yml -f docker-compose.databricks.yml up -d api
curl localhost:8000/health        # model_version is the Unity Catalog version behind @champion
```

The override points MLflow at Databricks (`databricks-uc` registry) and removes the API's dependency on the local `mlflow` service. In production, the token would be a service principal's OAuth secret rather than a personal token.

---

## Notes

- The researcher's code is **not modified**. Test metrics come from parsing the researcher's training log, and the log is stored as a run artifact.
- The predictor reads a module-level global, so each API process handles one request at a time behind a lock. On Kubernetes the API scales by adding pods (`serving.champion.replicas`). Under Compose it scales by adding uvicorn workers (`API_WORKERS`).
- The TabPFN API has a daily token quota that resets at 00:00 UTC. When the quota runs out, training and `/predict` both fail until it resets.
- The design decisions, known issues and possible improvements are covered in the Part 2 write-up.
