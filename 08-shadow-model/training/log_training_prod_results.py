import os
import mlflow
from mlflow.models import ModelSignature
from mlflow.types.schema import AnyType, ColSpec, Schema
from ranker.bl_ranker_model import BLRankerModel
from ranker.prod_artifacts import ArtifactKeys, ProdArtifacts
from ranker.registry import Registry
from serving.schemas import UserData
from utils.dir_names import DirNames
from utils.pip_requirements import PIP_REQUIREMENTS

MISSING_ARTIFACT_ERROR = "Expected production artifact not found: {}"
REGISTRATION_ERROR = "Model was logged but not registered - no version to alias"
MODEL_NAME = "model"

def build_signature() -> ModelSignature:
    inputs = Schema([ColSpec(AnyType(), name, required=False) for name in UserData.model_fields])
    outputs = Schema([ColSpec(AnyType())])
    return ModelSignature(inputs=inputs, outputs=outputs)

def log_training_prod_results(output_dir: str) -> str:

    for name in ProdArtifacts.ALL:
        path = os.path.join(output_dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError(MISSING_ARTIFACT_ERROR.format(path))

    model_info = mlflow.pyfunc.log_model(
        name=MODEL_NAME,
        python_model=BLRankerModel(),
        artifacts={
            ArtifactKeys.CATBOOST: os.path.join(output_dir, ProdArtifacts.CATBOOST),
            ArtifactKeys.TFM_CONTEXT: os.path.join(output_dir, ProdArtifacts.TFM_CONTEXT),
            ArtifactKeys.CLIENTS: os.path.join(output_dir, ProdArtifacts.CLIENTS),
        },
        signature=build_signature(),
        registered_model_name=Registry.REGISTERED_MODEL_NAME,
        code_paths=[DirNames.RANKER, DirNames.RESEARCHER],
        pip_requirements=PIP_REQUIREMENTS,
    )
    if model_info.registered_model_version is None:
        raise RuntimeError(REGISTRATION_ERROR)
    return str(model_info.registered_model_version)
