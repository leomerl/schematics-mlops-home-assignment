import os
import mlflow
from ranker.bl_ranker_model import BLRankerModel
from ranker.prod_artifacts import ArtifactKeys, ProdArtifacts
from ranker.registry import Registry

MISSING_ARTIFACT_ERROR = "Expected production artifact not found: {}"
REGISTRATION_ERROR = "Model was logged but not registered - no version to alias"
MODEL_NAME = "model"


def log_training_prod_results(output_dir: str) -> None:
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
        registered_model_name=Registry.REGISTERED_MODEL_NAME,
    )
    if model_info.registered_model_version is None:
        raise RuntimeError(REGISTRATION_ERROR)
    mlflow.MlflowClient().set_registered_model_alias(
        Registry.REGISTERED_MODEL_NAME, Registry.CHAMPION_ALIAS, str(model_info.registered_model_version)
    )
