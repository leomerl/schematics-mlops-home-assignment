import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any
from scipy.stats import kendalltau

SHADOW_URL = os.environ.get("SHADOW_URL")
SAMPLE_RATE = float(os.environ.get("SHADOW_SAMPLE_RATE", "0.05"))
LOG_PATH = os.environ.get("SHADOW_LOG_PATH", "/tmp/shadow_log.jsonl")
PREDICT_PATH = "/predict"
TIMEOUT_SECONDS = 60
NO_CHALLENGER_STATUS = 503
RANK = "rank"

logger = logging.getLogger(__name__)


class Headers:
    VERSION = "X-Model-Version"
    LATENCY = "X-Predict-Ms"


class Fields:
    TIMESTAMP_MS = "timestamp_ms"
    CHAMPION_VERSION = "champion_version"
    CHALLENGER_VERSION = "challenger_version"
    CHAMPION_LATENCY_MS = "champion_latency_ms"
    CHALLENGER_LATENCY_MS = "challenger_latency_ms"
    CHALLENGER_ERROR = "challenger_error"
    TOP1_MATCH = "top1_match"
    KENDALL_TAU = "kendall_tau"


def should_mirror() -> bool:
    return bool(SHADOW_URL) and random.random() < SAMPLE_RATE


def is_ranking(result: Any) -> bool:
    return isinstance(result, dict) and bool(result) and all(isinstance(value, dict) and RANK in value for value in result.values())


def top_brand(ranking: dict) -> str:
    return min(ranking, key=lambda brand: ranking[brand][RANK])


def compare(champion: Any, challenger: Any) -> dict:
    if not (is_ranking(champion) and is_ranking(challenger)):
        return {Fields.TOP1_MATCH: is_ranking(champion) == is_ranking(challenger), Fields.KENDALL_TAU: None}

    common = sorted(set(champion) & set(challenger))
    tau = None
    if len(common) >= 2:
        value = kendalltau([champion[b][RANK] for b in common], [challenger[b][RANK] for b in common]).statistic
        tau = None if value != value else float(value)
    return {Fields.TOP1_MATCH: top_brand(champion) == top_brand(challenger), Fields.KENDALL_TAU: tau}


def record(entry: dict) -> None:
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def mirror(payload: dict, champion_result: Any, champion_latency_ms: float, champion_version: str) -> None:
    entry = {
        Fields.TIMESTAMP_MS: int(time.time() * 1000),
        Fields.CHAMPION_VERSION: champion_version,
        Fields.CHAMPION_LATENCY_MS: champion_latency_ms,
    }
    request = urllib.request.Request(
        SHADOW_URL + PREDICT_PATH, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:
            challenger_result = json.load(reply)
            entry[Fields.CHALLENGER_VERSION] = reply.headers.get(Headers.VERSION)
            entry[Fields.CHALLENGER_LATENCY_MS] = float(reply.headers.get(Headers.LATENCY, "nan"))
            entry[Fields.CHALLENGER_ERROR] = False
            entry.update(compare(champion_result, challenger_result))
    except urllib.error.HTTPError as error:
        if error.code == NO_CHALLENGER_STATUS:
            return
        entry[Fields.CHALLENGER_VERSION] = error.headers.get(Headers.VERSION)
        entry[Fields.CHALLENGER_ERROR] = True
    except TimeoutError:
        entry[Fields.CHALLENGER_VERSION] = None
        entry[Fields.CHALLENGER_ERROR] = True
    except urllib.error.URLError as error:
        logger.warning("Shadow service unreachable, request not mirrored: %s", error.reason)
        return
    record(entry)
