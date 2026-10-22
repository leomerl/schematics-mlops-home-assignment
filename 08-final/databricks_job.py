import argparse
import os
import runpy
import sys
from databricks.sdk.runtime import dbutils
from training.parse_args import Modes

SECRET_SCOPE = "bl"
TABPFN_TOKEN_KEY = "TABPFN_TOKEN"
PIPELINE_MODULE = "training.train_pipeline"


def parse_job_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BL training pipeline as a Databricks job")
    parser.add_argument("--mode", choices=[Modes.TEST, Modes.PRODUCTION], required=True)
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--model-name", required=True)
    return parser.parse_args()


args = parse_job_args()

os.environ[TABPFN_TOKEN_KEY] = dbutils.secrets.get(scope=SECRET_SCOPE, key=TABPFN_TOKEN_KEY)
os.environ["INPUT_PATH"] = os.path.join(args.input_path, "")
os.environ["INPUT_FILE"] = args.input_file
os.environ["MLFLOW_EXPERIMENT_NAME"] = args.experiment_name
os.environ["REGISTERED_MODEL_NAME"] = args.model_name
os.environ["MLFLOW_TRACKING_URI"] = "databricks"

sys.argv = [sys.argv[0], "--mode", args.mode]
runpy.run_module(PIPELINE_MODULE, run_name="__main__")