import json
import os
import time
import numpy as np
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from gates.gate_config import GateStatus, ShadowGate, VersionTags
from gitops.write_back import NO_MODEL, Slot, write_models
from ranker.registry import Registry
from serving.shadow import LOG_PATH, Fields

P95 = 95
MS_PER_HOUR = 3_600_000


def read_records(path: str, since_ms: int, version: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        records = [json.loads(line) for line in f if line.strip()]
    return [
        r for r in records
        if r[Fields.TIMESTAMP_MS] >= since_ms and r.get(Fields.CHALLENGER_VERSION) in (version, None)
    ]


def check_shadow(records: list[dict], hours_in_shadow: float) -> tuple[str, list[str], dict]:
    if hours_in_shadow < ShadowGate.MIN_HOURS:
        return GateStatus.WAITING, [f"in shadow {hours_in_shadow:.1f}h of {ShadowGate.MIN_HOURS}h"], {}
    if len(records) < ShadowGate.MIN_SAMPLES:
        return GateStatus.WAITING, [f"{len(records)} of {ShadowGate.MIN_SAMPLES} mirrored requests"], {}

    answered = [r for r in records if not r[Fields.CHALLENGER_ERROR]]
    taus = [r[Fields.KENDALL_TAU] for r in answered if r.get(Fields.KENDALL_TAU) is not None]
    stats = {
        "samples": len(records),
        "error_rate": 1 - len(answered) / len(records),
        "top1_agreement": float(np.mean([r[Fields.TOP1_MATCH] for r in answered])) if answered else 0.0,
        "mean_kendall_tau": float(np.mean(taus)) if taus else None,
        "champion_p95_ms": float(np.percentile([r[Fields.CHAMPION_LATENCY_MS] for r in answered], P95)) if answered else None,
        "challenger_p95_ms": float(np.percentile([r[Fields.CHALLENGER_LATENCY_MS] for r in answered], P95)) if answered else None,
    }

    failures = []
    if stats["error_rate"] > ShadowGate.MAX_ERROR_RATE:
        failures.append(f"error rate {stats['error_rate']:.1%} above {ShadowGate.MAX_ERROR_RATE:.0%}")
    if stats["top1_agreement"] < ShadowGate.MIN_TOP1_AGREEMENT:
        failures.append(f"top-1 agreement {stats['top1_agreement']:.0%} below {ShadowGate.MIN_TOP1_AGREEMENT:.0%}")
    if stats["mean_kendall_tau"] is not None and stats["mean_kendall_tau"] < ShadowGate.MIN_KENDALL_TAU:
        failures.append(f"mean Kendall tau {stats['mean_kendall_tau']:.2f} below {ShadowGate.MIN_KENDALL_TAU}")
    if answered and stats["challenger_p95_ms"] > stats["champion_p95_ms"] * ShadowGate.MAX_LATENCY_RATIO:
        failures.append(f"p95 {stats['challenger_p95_ms']:.0f} ms above {ShadowGate.MAX_LATENCY_RATIO}x champion's {stats['champion_p95_ms']:.0f} ms")
    return (GateStatus.FAILED if failures else GateStatus.PASSED), failures, stats


def main() -> None:
    client = MlflowClient()
    name = Registry.REGISTERED_MODEL_NAME
    try:
        challenger = client.get_model_version_by_alias(name, Registry.CHALLENGER_ALIAS)
    except MlflowException:
        print(f"{name}: no @{Registry.CHALLENGER_ALIAS}, nothing to evaluate")
        return

    version = str(challenger.version)
    created_ms = int(challenger.creation_timestamp)
    hours = (time.time() * 1000 - created_ms) / MS_PER_HOUR
    status, reasons, stats = check_shadow(read_records(LOG_PATH, created_ms, version), hours)

    for key, value in stats.items():
        client.set_model_version_tag(name, version, VersionTags.SHADOW_PREFIX + key, str(value))
    client.set_model_version_tag(name, version, VersionTags.SHADOW_GATE, status)
    client.set_model_version_tag(name, version, VersionTags.SHADOW_REASONS, "; ".join(reasons) or "none")

    if status == GateStatus.PASSED:
        write_models({Slot.CHAMPION: version, Slot.CHALLENGER: NO_MODEL}, f"{name}: v{version} champion (shadow gate passed)")
        client.set_registered_model_alias(name, Registry.CHAMPION_ALIAS, version)
        client.delete_registered_model_alias(name, Registry.CHALLENGER_ALIAS)
    elif status == GateStatus.FAILED:
        write_models({Slot.CHALLENGER: NO_MODEL}, f"{name}: v{version} challenger removed (shadow gate failed)")
        client.delete_registered_model_alias(name, Registry.CHALLENGER_ALIAS)
    print(f"{name} v{version}: shadow gate {status}" + (f" ({'; '.join(reasons)})" if reasons else ""))


if __name__ == "__main__":
    main()
