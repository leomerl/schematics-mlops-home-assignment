import os


class OfflineGate:
    MIN_CB_F1 = 0.40
    MAX_PAYOUT_MAE = 3.0
    MAX_F1_DROP = 0.03
    MAX_MAE_RISE = 0.10


class ShadowGate:
    MIN_HOURS = float(os.environ.get("SHADOW_MIN_HOURS", "20"))
    MIN_SAMPLES = int(os.environ.get("SHADOW_MIN_SAMPLES", "30"))
    MIN_TOP1_AGREEMENT = 0.7
    MIN_KENDALL_TAU = 0.5
    MAX_ERROR_RATE = 0.02
    MAX_LATENCY_RATIO = 1.5


class VersionTags:
    OFFLINE_GATE = "offline_gate"
    OFFLINE_REASONS = "offline_gate_reasons"
    SHADOW_GATE = "shadow_gate"
    SHADOW_REASONS = "shadow_gate_reasons"
    EVAL_PREFIX = "eval_"
    SHADOW_PREFIX = "shadow_"


class GateStatus:
    BOOTSTRAP = "bootstrap"
    PASSED = "passed"
    FAILED = "failed"
    WAITING = "waiting"
