import mlflow
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import FastAPI
from mlflow import MlflowClient
from ranker.registry import Registry
from serving.schemas import UserData

MODEL_FORMAT = "models:/{}/{}"

state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    version = MlflowClient().get_model_version_by_alias(
        Registry.REGISTERED_MODEL_NAME, Registry.CHAMPION_ALIAS
    ).version
    state["model"] = mlflow.pyfunc.load_model(MODEL_FORMAT.format(Registry.REGISTERED_MODEL_NAME, version))
    state["version"] = version
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "model_version": state["version"]}

@app.post("/predict")
def predict(user: UserData):
    return state["model"].predict(pd.DataFrame([user.model_dump()]))