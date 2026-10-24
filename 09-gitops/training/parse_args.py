import argparse


class Modes:
    TEST = "test"
    PRODUCTION = "production"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the BL payout models and track them in MLflow")
    parser.add_argument("--mode", choices=[Modes.TEST, Modes.PRODUCTION], required=True)
    return parser.parse_args()
