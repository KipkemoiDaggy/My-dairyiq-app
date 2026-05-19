"""
Anomaly & Disease Detection — Z-Score Three-Rule Framework
===========================================================
Each cow's daily production is evaluated against three independent rules:

Rule 1 — Z-Score Deviation (personal 7-day rolling baseline)
    Compute rolling 7-day mean and std (shifted by 1 day so today is not
    in its own baseline).
    Z = (today - rolling_mean) / rolling_std
    |Z| > 2 SD  → MEDIUM
    |Z| > 3 SD  → HIGH

Rule 2 — Sudden Drop Below 75% of 7-Day Rolling Mean
    If today's yield < 75% of the 7-day rolling mean → HIGH
    Flags acute illness (e.g. mastitis, toxic plant ingestion).

Rule 3 — Sustained Downward Trend (Linear Regression over 14-day window)
    Fit a linear regression over the last 14 days of yield.
    If slope < -0.2 AND R² > 0.6 → MEDIUM
    (Consistent, well-fitted decline beyond normal lactation taper.)

Severity mapping:
    HIGH   → immediate veterinary attention recommended
    MEDIUM → monitor closely, check feed and environment
    normal → production within expected range
"""

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# ── Thresholds ────────────────────────────────────────────────────────────────
ROLLING_WINDOW   = 7      # days for Rule 1 & Rule 2 baseline
Z_MEDIUM         = 2.0    # z-score threshold → MEDIUM
Z_HIGH           = 3.0    # z-score threshold → HIGH
DROP_THRESHOLD   = 0.75   # fraction of rolling mean → HIGH (Rule 2)
TREND_WINDOW     = 14     # days for Rule 3 regression window
SLOPE_THRESHOLD  = -0.2   # slope (L/day) below which trend is flagged
R2_THRESHOLD     = 0.6    # minimum R² for trend flag to be valid


# ── Core per-cow detection ────────────────────────────────────────────────────

def detect_anomalies_for_cow(milk_df: pd.DataFrame) -> pd.DataFrame:
    """
    Run all three anomaly rules on a single cow's complete history.

    Parameters
    ----------
    milk_df : DataFrame with at least 'record_date' and 'total_yield' columns.

    Returns
    -------
    DataFrame with extra columns:
        rolling_mean, rolling_std, z_score,
        anomaly_severity ('HIGH' | 'MEDIUM' | 'normal'),
        is_anomaly (bool), anomaly_reason (str)
    """
    if len(milk_df) < ROLLING_WINDOW:
        df = milk_df.copy().sort_values("record_date").reset_index(drop=True)
        df["rolling_mean"]    = np.nan
        df["rolling_std"]     = np.nan
        df["z_score"]         = np.nan
        df["anomaly_severity"] = "insufficient_data"
        df["is_anomaly"]      = False
        df["anomaly_reason"]  = ""
        return df

    df = milk_df.copy().sort_values("record_date").reset_index(drop=True)

    # ── Rule 1: Z-score against 7-day rolling baseline ────────────────────────
    df["rolling_mean"] = (
        df["total_yield"]
        .rolling(ROLLING_WINDOW, min_periods=4)
        .mean()
        .shift(1)
    )
    df["rolling_std"] = (
        df["total_yield"]
        .rolling(ROLLING_WINDOW, min_periods=4)
        .std()
        .shift(1)
    )
    df["z_score"] = (df["total_yield"] - df["rolling_mean"]) / (
        df["rolling_std"].replace(0, np.nan) + 1e-6
    )

    # ── Initialise severity columns ───────────────────────────────────────────
    df["anomaly_severity"] = "normal"
    df["anomaly_reason"]   = ""

    # Rule 1 — MEDIUM: |Z| > 2 SD (negative direction only)
    mask_medium_z = df["z_score"] < -Z_MEDIUM
    df.loc[mask_medium_z, "anomaly_severity"] = "MEDIUM"
    df.loc[mask_medium_z, "anomaly_reason"]   = "Z-score > 2 SD below personal baseline"

    # Rule 1 — HIGH: |Z| > 3 SD (negative direction only)
    mask_high_z = df["z_score"] < -Z_HIGH
    df.loc[mask_high_z, "anomaly_severity"] = "HIGH"
    df.loc[mask_high_z, "anomaly_reason"]   = "Z-score > 3 SD below personal baseline"

    # ── Rule 2: Below 75% of 7-day rolling mean → HIGH ───────────────────────
    mask_drop = df["total_yield"] < (df["rolling_mean"] * DROP_THRESHOLD)
    df.loc[mask_drop, "anomaly_severity"] = "HIGH"
    df.loc[mask_drop, "anomaly_reason"]   = (
        "Yield below 75% of 7-day rolling mean (acute drop)"
    )

    # ── Rule 3: LR slope < -0.2 with R² > 0.6 → MEDIUM ──────────────────────
    rule3_flags = _compute_trend_flags(df)
    # Only upgrade to MEDIUM if not already HIGH
    for idx in rule3_flags:
        if df.at[idx, "anomaly_severity"] == "normal":
            df.at[idx, "anomaly_severity"] = "MEDIUM"
            df.at[idx, "anomaly_reason"]   = (
                f"Sustained linear decline (slope < {SLOPE_THRESHOLD} L/day, "
                f"R² > {R2_THRESHOLD}) over {TREND_WINDOW}-day window"
            )

    df["is_anomaly"] = df["anomaly_severity"].isin(["MEDIUM", "HIGH"])
    return df


def _compute_trend_flags(df: pd.DataFrame) -> list:
    """
    Return a list of DataFrame indices where the 14-day trailing regression
    slope < SLOPE_THRESHOLD and R² > R2_THRESHOLD.
    """
    flagged = []
    yields = df["total_yield"].values

    for i in range(TREND_WINDOW - 1, len(df)):
        window = yields[i - TREND_WINDOW + 1: i + 1]
        if np.isnan(window).any():
            continue
        x = np.arange(len(window), dtype=float)
        slope, _, r_value, _, _ = scipy_stats.linregress(x, window)
        r2 = r_value ** 2
        if slope < SLOPE_THRESHOLD and r2 > R2_THRESHOLD:
            flagged.append(df.index[i])

    return flagged


def _normalize_severity(s: str) -> str:
    """
    Enforce the canonical two-level severity schema.

    Mapping
    -------
    HIGH, CRITICAL, SEVERE         → 'HIGH'
    MEDIUM, WARNING, WARN, LOW,
    or anything else               → 'MEDIUM'
    """
    s = (s or "").strip().upper()
    if s in ("HIGH", "CRITICAL", "SEVERE"):
        return "HIGH"
    return "MEDIUM"


# ── Full-herd scan ─────────────────────────────────────────────────────────────

def run_anomaly_scan(save_alerts: bool = True, user_id=None) -> list:
    """
    Scan ALL active cows and return detected anomalies from the last 3 days.

    Parameters
    ----------
    save_alerts : bool  — persist new alerts to the database.
    user_id     : int   — filter cows by user (None = all users).

    Returns
    -------
    list of dicts, one per anomaly event.
    """
    import database as db

    cows_df      = db.get_all_cows(user_id=user_id)
    all_anomalies = []

    for _, cow in cows_df.iterrows():
        cow_id   = int(cow["id"])
        cow_name = cow["name"]
        tag      = cow["tag_number"]

        milk_df = db.get_all_milk_records_for_cow(cow_id)
        if milk_df.empty or len(milk_df) < ROLLING_WINDOW:
            continue

        analyzed = detect_anomalies_for_cow(milk_df)
        recent   = analyzed.tail(3)

        for _, row in recent.iterrows():
            if not row["is_anomaly"]:
                continue

            severity = _normalize_severity(row["anomaly_severity"])   # always 'HIGH' or 'MEDIUM'
            actual   = row["total_yield"]
            expected = row.get("rolling_mean", actual)
            if pd.isna(expected):
                expected = actual
            drop_pct = max(0, (1 - actual / (expected + 1e-6)) * 100)
            reason   = row["anomaly_reason"]

            message = (
                f"{cow_name} ({tag}): produced {actual:.1f}L "
                f"(expected ≈{expected:.1f}L, {drop_pct:.0f}% below baseline). "
                f"Reason: {reason}."
            )

            # ── Derive per-rule alert_type label ──────────────────────────
            reason_lower = reason.lower()
            if "75%" in reason_lower or "acute drop" in reason_lower or "rolling mean" in reason_lower:
                alert_type = "zscore_rule2"
            elif "linear decline" in reason_lower or "slope" in reason_lower or "trend" in reason_lower:
                alert_type = "zscore_rule3"
            else:
                # Default: Rule 1 (Z-score SD deviation)
                alert_type = "zscore_rule1"

            anomaly = {
                "cow_id":         cow_id,
                "cow_name":       cow_name,
                "tag_number":     tag,
                "date":           row["record_date"],
                "actual_yield":   round(actual, 1),
                "expected_yield": round(float(expected), 1),
                "drop_pct":       round(drop_pct, 1),
                "z_score":        (
                    round(float(row["z_score"]), 2)
                    if not pd.isna(row.get("z_score", np.nan))
                    else None
                ),
                "severity":   severity,
                "reason":     reason,
                "alert_type": alert_type,
                "message":    message,
            }
            all_anomalies.append(anomaly)

            if save_alerts:
                db.save_alert(
                    cow_id=cow_id,
                    alert_date=row["record_date"],
                    alert_type=alert_type,
                    message=message,
                    severity=severity,
                    user_id=user_id,
                )

    return all_anomalies


# ── Health score ──────────────────────────────────────────────────────────────

def get_health_score(milk_df: pd.DataFrame) -> tuple:
    """
    Compute a 0-100 health score for a cow based on recent vs. baseline
    production using the same 7-day rolling window.

    Score bands:
        90-100 → Excellent
        75-89  → Good
        60-74  → Monitor
        40-59  → Concern
        0-39   → Critical
    """
    if len(milk_df) < 7:
        return 75, "Insufficient data"

    df = milk_df.sort_values("record_date")
    if len(df) >= 14:
        baseline = df["total_yield"].iloc[-14:-7].mean()
        recent   = df["total_yield"].iloc[-7:].mean()
    else:
        half     = len(df) // 2
        baseline = df["total_yield"].iloc[:half].mean()
        recent   = df["total_yield"].iloc[half:].mean()

    if baseline == 0:
        return 75, "Good"

    ratio = recent / baseline
    score = int(min(100, max(0, ratio * 100)))

    if score >= 90:
        label = "Excellent"
    elif score >= 75:
        label = "Good"
    elif score >= 60:
        label = "Monitor"
    elif score >= 40:
        label = "Concern"
    else:
        label = "Critical"

    return score, label
