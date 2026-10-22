import glob
import os
import mlflow
from training.log_training_prod_results import log_training_prod_results
from training.log_training_test_results import log_training_test_results

NO_LOG_ERROR = "No training log found in {}"


def log_training_results(output_dir: str, train_test: bool) -> None:
    log_files = glob.glob(os.path.join(output_dir, "*.log"))
    if not log_files:
        raise FileNotFoundError(NO_LOG_ERROR.format(output_dir))

    mlflow.log_artifact(log_files[0], artifact_path="logs")
    if train_test:
        log_training_test_results(log_files[0])
    else:
        log_training_prod_results(output_dir)
