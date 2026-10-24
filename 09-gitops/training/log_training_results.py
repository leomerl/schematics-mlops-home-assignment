import glob
import os
import mlflow

NO_LOG_ERROR = "No training log found in {}"
LOG_ARTIFACT_PATH = "logs"
EVAL_LOG_ARTIFACT_PATH = "logs/evaluation"


def log_researcher_log(output_dir: str, artifact_path: str = LOG_ARTIFACT_PATH) -> str:
    log_files = glob.glob(os.path.join(output_dir, "*.log"))
    if not log_files:
        raise FileNotFoundError(NO_LOG_ERROR.format(output_dir))

    mlflow.log_artifact(log_files[0], artifact_path=artifact_path)
    return log_files[0]
