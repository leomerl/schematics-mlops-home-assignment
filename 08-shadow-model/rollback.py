import argparse
from mlflow import MlflowClient
from ranker.registry import Registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Point the champion alias at an earlier model version")
    parser.add_argument("--version", type=int, help="target version, default: the newest version older than the current champion")
    return parser.parse_args()


def previous_version(client: MlflowClient, current: int) -> int:
    versions = client.search_model_versions(f"name='{Registry.REGISTERED_MODEL_NAME}'")
    older = [int(v.version) for v in versions if int(v.version) < current]
    if not older:
        raise SystemExit(f"No version older than {current} to roll back to")
    return max(older)


def main():
    args = parse_args()
    client = MlflowClient()
    name = Registry.REGISTERED_MODEL_NAME

    current = int(client.get_model_version_by_alias(name, Registry.CHAMPION_ALIAS).version)
    target = args.version or previous_version(client, current)
    if target == current:
        raise SystemExit(f"Version {current} is already @{Registry.CHAMPION_ALIAS}")

    client.get_model_version(name, str(target))
    client.set_registered_model_alias(name, Registry.CHAMPION_ALIAS, str(target))
    print(f"{name}@{Registry.CHAMPION_ALIAS}: v{current} -> v{target}. Restart the API to serve it.")


if __name__ == "__main__":
    main()
