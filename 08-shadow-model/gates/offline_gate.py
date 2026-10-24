import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from gates.gate_config import GateStatus, OfflineGate, VersionTags
from ranker.registry import Registry
from training.parse_logs import MetricNames

DATA_ROWS = "data_rows"
DATA_END = "data_end"
GATED_KEYS = (MetricNames.CB_F1, MetricNames.PAYOUT_MAE, DATA_ROWS, DATA_END)


def check_offline(candidate: dict, baseline: dict | None) -> list[str]:
    failures = []
    f1, mae = float(candidate[MetricNames.CB_F1]), float(candidate[MetricNames.PAYOUT_MAE])
    if f1 < OfflineGate.MIN_CB_F1:
        failures.append(f"cb_f1 {f1:.3f} below floor {OfflineGate.MIN_CB_F1}")
    if mae > OfflineGate.MAX_PAYOUT_MAE:
        failures.append(f"payout_mae {mae:.3f} above ceiling {OfflineGate.MAX_PAYOUT_MAE}")
    if baseline is None:
        return failures

    base_f1, base_mae = float(baseline[MetricNames.CB_F1]), float(baseline[MetricNames.PAYOUT_MAE])
    if f1 < base_f1 - OfflineGate.MAX_F1_DROP:
        failures.append(f"cb_f1 {f1:.3f} dropped more than {OfflineGate.MAX_F1_DROP} from champion {base_f1:.3f}")
    if mae > base_mae * (1 + OfflineGate.MAX_MAE_RISE):
        failures.append(f"payout_mae {mae:.3f} rose more than {OfflineGate.MAX_MAE_RISE:.0%} from champion {base_mae:.3f}")
    if int(candidate[DATA_ROWS]) < int(baseline[DATA_ROWS]):
        failures.append(f"data_rows {candidate[DATA_ROWS]} fewer than champion's {baseline[DATA_ROWS]}")
    if str(candidate[DATA_END]) < str(baseline[DATA_END]):
        failures.append(f"data_end {candidate[DATA_END]} earlier than champion's {baseline[DATA_END]}")
    return failures


def champion_baseline(client: MlflowClient, name: str) -> tuple[bool, dict | None]:
    try:
        champion = client.get_model_version_by_alias(name, Registry.CHAMPION_ALIAS)
    except MlflowException:
        return False, None
    tags = {key: champion.tags.get(VersionTags.EVAL_PREFIX + key) for key in GATED_KEYS}
    return True, tags if all(value is not None for value in tags.values()) else None


def apply_offline_gate(version: str, candidate: dict) -> str:
    client = MlflowClient()
    name = Registry.REGISTERED_MODEL_NAME
    for key in GATED_KEYS:
        client.set_model_version_tag(name, version, VersionTags.EVAL_PREFIX + key, str(candidate[key]))

    has_champion, baseline = champion_baseline(client, name)
    failures = check_offline(candidate, baseline) if has_champion else []
    if not has_champion:
        status = GateStatus.BOOTSTRAP
        client.set_registered_model_alias(name, Registry.CHAMPION_ALIAS, version)
    elif failures:
        status = GateStatus.FAILED
        client.set_model_version_tag(name, version, VersionTags.OFFLINE_REASONS, "; ".join(failures))
    else:
        status = GateStatus.PASSED
        client.set_registered_model_alias(name, Registry.CHALLENGER_ALIAS, version)

    client.set_model_version_tag(name, version, VersionTags.OFFLINE_GATE, status)
    mlflow.set_tag(VersionTags.OFFLINE_GATE, status)
    print(f"{name} v{version}: offline gate {status}" + (f" ({'; '.join(failures)})" if failures else ""))
    return status
