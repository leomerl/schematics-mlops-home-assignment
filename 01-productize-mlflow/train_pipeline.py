import glob
import os
import tempfile
import mlflow
import logging
from bl_models_train import BLPayoutModelsFit
from parse_logs import parse_metrics

# mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])

NO_LOG_ERROR = "No training log found in {}"

with tempfile.TemporaryDirectory() as output_dir:
    with mlflow.start_run():
        mlflow.log_params({
            "train_test": True,
            "input_file": os.environ["INPUT_FILE"],
            "model_class": "BLPayoutModelsFit",
        })

        model = BLPayoutModelsFit(
            os.environ["INPUT_PATH"],
            os.environ["INPUT_FILE"],
            os.path.join(output_dir, ""),
            train_test=True,
        )
        
        model.fit_()

        log_files = glob.glob(os.path.join(output_dir, "*.log"))
        if not log_files:
            raise FileNotFoundError(NO_LOG_ERROR.format(output_dir))
        
        mlflow.log_artifact(log_files[0], artifact_path="logs")
        with open(log_files[0]) as f:
            metrics, daily = parse_metrics(f.read())
        mlflow.log_metrics(metrics)
        for day, day_metrics in daily.items():
            mlflow.log_metrics(day_metrics, step=day)

    logging.shutdown()