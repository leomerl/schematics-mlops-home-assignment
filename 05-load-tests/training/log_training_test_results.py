import mlflow
from training.parse_logs import parse_metrics


def log_training_test_results(log_file: str) -> None:
    with open(log_file) as f:
        metrics, daily = parse_metrics(f.read())
    mlflow.log_metrics(metrics)
    for day, day_metrics in daily.items():
        mlflow.log_metrics(day_metrics, step=day)
