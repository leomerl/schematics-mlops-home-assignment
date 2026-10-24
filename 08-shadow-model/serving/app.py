import logging
import os
import time
import mlflow
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from ranker.registry import Registry
from serving import shadow
from serving.schemas import UserData

MODEL_FORMAT = "models:/{}/{}"
MODEL_ALIAS = os.environ.get("MODEL_ALIAS", Registry.CHAMPION_ALIAS)
NO_MODEL_ERROR = "No model behind @{}"
PREDICT_ERROR = "Prediction failed"

logger = logging.getLogger(__name__)
state = {"model": None, "version": None}

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        version = MlflowClient().get_model_version_by_alias(Registry.REGISTERED_MODEL_NAME, MODEL_ALIAS).version
    except MlflowException:
        if MODEL_ALIAS == Registry.CHAMPION_ALIAS:
            raise
        version = None
    if version is not None:
        state["model"] = mlflow.pyfunc.load_model(MODEL_FORMAT.format(Registry.REGISTERED_MODEL_NAME, version))
    state["version"] = None if version is None else str(version)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "alias": MODEL_ALIAS, "model_version": state["version"]}

@app.post("/predict")
def predict(user: UserData, response: Response, background_tasks: BackgroundTasks):
    version_header = {shadow.Headers.VERSION: str(state["version"])}
    if state["model"] is None:
        raise HTTPException(status_code=503, detail=NO_MODEL_ERROR.format(MODEL_ALIAS), headers=version_header)

    started = time.perf_counter()
    try:
        result = state["model"].predict(pd.DataFrame([user.model_dump()]))
    except Exception as error:
        logger.exception(PREDICT_ERROR)
        raise HTTPException(status_code=500, detail=PREDICT_ERROR, headers=version_header) from error
    latency_ms = (time.perf_counter() - started) * 1000

    response.headers.update(version_header)
    response.headers[shadow.Headers.LATENCY] = f"{latency_ms:.1f}"
    if shadow.should_mirror():
        background_tasks.add_task(shadow.mirror, user.model_dump(mode="json"), result, latency_ms, state["version"])
    return result
