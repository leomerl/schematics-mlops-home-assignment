import argparse
import os
import runpy
import shutil
import sys
import tempfile
from importlib import metadata, import_module
from databricks.sdk.runtime import dbutils
from training.parse_args import Modes
from utils.dir_names import DirNames
from utils.pip_requirements import PIP_REQUIREMENTS

SECRET_SCOPE = "bl"
TABPFN_TOKEN_KEY = "TABPFN_TOKEN"
PIPELINE_MODULE = "training.train_pipeline"
DISTRIBUTION_NAME = "bl-ranker"
TORCH_CPU_INDEX = "--extra-index-url https://download.pytorch.org/whl/cpu"


def parse_job_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BL training pipeline as a Databricks job")
    parser.add_argument("--mode", choices=[Modes.TEST, Modes.PRODUCTION], required=True)
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--model-name", required=True)
    return parser.parse_args()


def prepare_workdir() -> str:
    workdir = tempfile.mkdtemp(prefix="bl_job_")
    for package in (DirNames.RANKER, DirNames.RESEARCHER):
        source = import_module(package).__path__[0]
        shutil.copytree(source, os.path.join(workdir, package), ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(workdir, PIP_REQUIREMENTS), "w") as f:
        f.write("\n".join([TORCH_CPU_INDEX, *(metadata.requires(DISTRIBUTION_NAME) or [])]) + "\n")
    return workdir


def main() -> None:
    args = parse_job_args()

    os.environ[TABPFN_TOKEN_KEY] = dbutils.secrets.get(scope=SECRET_SCOPE, key=TABPFN_TOKEN_KEY)
    os.environ["INPUT_PATH"] = os.path.join(args.input_path, "")
    os.environ["INPUT_FILE"] = args.input_file
    os.environ["MLFLOW_EXPERIMENT_NAME"] = args.experiment_name
    os.environ["REGISTERED_MODEL_NAME"] = args.model_name
    os.environ["MLFLOW_TRACKING_URI"] = "databricks"

    os.chdir(prepare_workdir())
    sys.argv = [sys.argv[0], "--mode", args.mode]
    runpy.run_module(PIPELINE_MODULE, run_name="__main__")


if __name__ == "__main__":
    main()
