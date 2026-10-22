import re

class MetricNames:
    CB_PRECISION = "cb_precision"
    CB_RECALL = "cb_recall"
    CB_F1 = "cb_f1"
    PAYOUT_MAE = "payout_mae"
    PAYOUT_MAPE = "payout_mape"
    CB_F1_DAILY = "cb_f1_daily"
    CB_SUPPORT = "cb_support"
    CB_SUPPORT_DAILY = "cb_support_daily"
    PAYOUT_MAE_THR = "payout_mae_thr{}"
    PAYOUT_MAPE_THR = "payout_mape_thr{}"


class LogPatterns:
    REPORT_HEADER = "CB accuracy report"
    PAYOUT_MAE = re.compile(r"mean_absolute_error:([\d.]+)")
    PAYOUT_MAPE = re.compile(r"mean_absolute_percentage_error:([\d.]+)")
    LEAD_ROW = re.compile(r"^\s+1\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)", re.MULTILINE)
    THRESHOLD = re.compile(r"thr: (\d+)")

PARSING_ERROR = "Could not parse metrics from log text"

def parse_metrics(log_text):
    metrics = {}
    daily = {}

    blocks = log_text.split(LogPatterns.REPORT_HEADER)[1:]
    for i, block in enumerate(blocks):
        match = LogPatterns.LEAD_ROW.search(block)
        if not match:
            continue
        precision, recall, f1, support = match.groups()
        precision, recall, f1, support = float(precision), float(recall), float(f1), int(support)
        if i ==0:
            metrics[MetricNames.CB_PRECISION] = precision
            metrics[MetricNames.CB_RECALL] = recall
            metrics[MetricNames.CB_F1] = f1
            metrics[MetricNames.CB_SUPPORT] = support
        else:
            daily[i] = {MetricNames.CB_F1_DAILY: f1, MetricNames.CB_SUPPORT_DAILY: support}


    mae = LogPatterns.PAYOUT_MAE.search(log_text)
    mape = LogPatterns.PAYOUT_MAPE.search(log_text)
    if not mae or not mape or MetricNames.CB_F1 not in metrics:
        raise ValueError(PARSING_ERROR)

    metrics[MetricNames.PAYOUT_MAE] = float(mae.group(1))
    metrics[MetricNames.PAYOUT_MAPE] = float(mape.group(1))

    parts = LogPatterns.THRESHOLD.split(log_text)
    for thr, text in zip(parts[1::2], parts[2::2]):
        mae = LogPatterns.PAYOUT_MAE.search(text)
        mape = LogPatterns.PAYOUT_MAPE.search(text)
        if mae and mape:
            metrics[MetricNames.PAYOUT_MAE_THR.format(thr)] = float(mae.group(1))
            metrics[MetricNames.PAYOUT_MAPE_THR.format(thr)] = float(mape.group(1))

    return metrics, daily

"""
metrics = {
        "cb_precision": 0.41, "cb_recall": 0.54, "cb_f1": 0.47, "cb_support": 1658,
        "payout_mae": 2.34, "payout_mape": 0.054,
        "payout_mae_thr5": 2.34, "payout_mape_thr5": 0.054,
}

daily = {
        1: {"cb_f1_daily": 0.55, "cb_support_daily": 537},
        2: {"cb_f1_daily": 0.55, "cb_support_daily": 492},
        ...
}
"""