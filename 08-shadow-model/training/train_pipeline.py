import os
import tempfile
import mlflow
from datetime import datetime
from gates.offline_gate import apply_offline_gate
from researcher.bl_models_train import BLPayoutModelsFit
from training.log_dataset import log_dataset
from training.log_training_prod_results import log_training_prod_results
from training.log_training_results import EVAL_LOG_ARTIFACT_PATH, log_researcher_log
from training.log_training_test_results import log_training_test_results
from training.parse_args import Modes, parse_args
from training.training_config import TRAINING_CONFIG


def fit(output_dir: str, train_test: bool) -> None:
    model = BLPayoutModelsFit(
        os.environ["INPUT_PATH"],
        os.environ["INPUT_FILE"],
        os.path.join(output_dir, ""),
        train_test=train_test,
    )
    model.fit_()
    for handler in model.logger.handlers[:]:
        handler.close()
        model.logger.removeHandler(handler)


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
        data_stats = log_dataset(os.path.join(os.environ["INPUT_PATH"], os.environ["INPUT_FILE"]))

        if train_test:
            fit(output_dir, train_test=True)
            log_training_test_results(log_researcher_log(output_dir))
        else:
            with tempfile.TemporaryDirectory(prefix="bl_eval_") as eval_dir:
                fit(eval_dir, train_test=True)
                metrics = log_training_test_results(log_researcher_log(eval_dir, EVAL_LOG_ARTIFACT_PATH))
            fit(output_dir, train_test=False)
            log_researcher_log(output_dir)
            version = log_training_prod_results(output_dir)
            apply_offline_gate(version, {**metrics, **data_stats})
