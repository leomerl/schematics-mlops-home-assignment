import os
import tempfile
import mlflow
from datetime import datetime
from researcher.bl_models_train import BLPayoutModelsFit
from training.log_dataset import log_dataset
from training.log_training_results import log_training_results
from training.parse_args import Modes, parse_args
from training.training_config import TRAINING_CONFIG

args = parse_args()
train_test = args.mode == Modes.TEST

with tempfile.TemporaryDirectory(prefix="bl_train_") as output_dir:
    with mlflow.start_run(run_name=f"{args.mode}-{datetime.now():%Y%m%d-%H%M}"):
        mlflow.set_tag("mode", args.mode)
        mlflow.log_params({
            "train_test": train_test,
            "input_file": os.environ["INPUT_FILE"],
            "model_class": "BLPayoutModelsFit",
        })
        mlflow.log_params(TRAINING_CONFIG)
        log_dataset(os.path.join(os.environ["INPUT_PATH"], os.environ["INPUT_FILE"]))

        model = BLPayoutModelsFit(
            os.environ["INPUT_PATH"],
            os.environ["INPUT_FILE"],
            os.path.join(output_dir, ""),
            train_test=train_test,
        )
        model.fit_()
        
        log_training_results(output_dir, train_test)
        for handler in model.logger.handlers[:]:
            handler.close()
            model.logger.removeHandler(handler)
