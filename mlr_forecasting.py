"""
MLR Forecasting Module
=======================
Two-level Multiple Linear Regression forecasting:

(a) Individual cow  — see forecasting.forecast_cow_production()
    Features: days_in_milk, season, parity_proxy
    Returns:  30-day forecast + R² + MAE

(b) Herd level      — train on the full herd's daily aggregate history
    Features: day_of_week, month, num_cows, lag_1/3/7/14, avg_dim
    Target:   total herd production (litres/day)
    Returns:  30-day aggregate forecast + R² + MAE + feature importance
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
from datetime import date, timedelta
import database as db


# ── (a) Individual-cow convenience wrapper ────────────────────────────────────

def forecast_cow_mlr(milk_df: pd.DataFrame, days_ahead: int = 30):
    """
    Thin wrapper around forecasting.forecast_cow_production().
    Keeps import surface consistent for callers that use mlr_forecasting.

    Returns
    -------
    hist_df, forecast_df, model_info   (same contract as forecasting module)
    """
    import forecasting as fc
    return fc.forecast_cow_production(milk_df, days_ahead=days_ahead)


# ── Feature engineering ────────────────────────────────────────────────────────

def build_herd_daily_df(user_id=None):
    """
    Aggregate milk records into a daily herd-level DataFrame
    with all features needed for the herd MLR model.
    """
    milk_df = db.get_milk_records(days=365, user_id=user_id)
    if milk_df.empty:
        return pd.DataFrame()

    daily = (
        milk_df.groupby("record_date")
        .agg(
            total_yield=("total_yield", "sum"),
            num_cows=("cow_id", "nunique"),
            avg_dim=("dim", "mean"),
        )
        .reset_index()
    )
    daily["record_date"] = pd.to_datetime(daily["record_date"])
    daily = daily.sort_values("record_date").reset_index(drop=True)

    # Date features
    daily["day_of_week"] = daily["record_date"].dt.dayofweek
    daily["month"]       = daily["record_date"].dt.month

    # Lag features
    daily["lag_1"]  = daily["total_yield"].shift(1)
    daily["lag_3"]  = daily["total_yield"].rolling(3,  min_periods=1).mean().shift(1)
    daily["lag_7"]  = daily["total_yield"].rolling(7,  min_periods=3).mean().shift(1)
    daily["lag_14"] = daily["total_yield"].rolling(14, min_periods=7).mean().shift(1)

    # Drop rows with NaN (first few rows without lag data)
    daily = daily.dropna().reset_index(drop=True)

    return daily


FEATURE_COLS = ["day_of_week", "month", "num_cows", "lag_1", "lag_3", "lag_7", "lag_14", "avg_dim"]


# ── (b) Herd-level model training ─────────────────────────────────────────────

def train_mlr_model(user_id=None):
    """
    Train the herd-level MLR model on historical daily aggregate data.

    Returns
    -------
    model       : fitted LinearRegression
    scaler      : fitted StandardScaler
    metrics     : dict — {mae, r2, intercept, feature_importance, train_samples}
    daily_df    : the full prepared DataFrame (with fitted_yield)
    """
    daily_df = build_herd_daily_df(user_id=user_id)

    if daily_df.empty or len(daily_df) < 30:
        return None, None, {"error": "Not enough data (need at least 30 days of records)"}, daily_df

    X = daily_df[FEATURE_COLS].values
    y = daily_df["total_yield"].values

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    y_pred = model.predict(X_scaled)
    mae    = round(mean_absolute_error(y, y_pred), 2)
    r2     = round(r2_score(y, y_pred), 4)

    # Absolute scaled coefficients as feature importance proxy
    importance = dict(zip(FEATURE_COLS, np.abs(model.coef_).round(3)))

    metrics = {
        "mae":                mae,
        "r2":                 r2,
        "intercept":          round(float(model.intercept_), 2),
        "feature_importance": importance,
        "train_samples":      len(daily_df),
    }

    return model, scaler, metrics, daily_df


# ── (b) Herd-level rolling forecast ───────────────────────────────────────────

def forecast_herd_mlr(days_ahead: int = 30, user_id=None):
    """
    Forecast total herd production for the next `days_ahead` days using the
    herd-level MLR model with autoregressive (rolling) feature construction.

    Returns
    -------
    forecast_df : DataFrame — [date, mlr_predicted, lower_bound, upper_bound]
    metrics     : dict — {mae, r2, train_samples, ...}
    fitted_df   : DataFrame — historical rows with 'fitted_yield' column
    """
    model, scaler, metrics, daily_df = train_mlr_model(user_id=user_id)

    if model is None:
        return pd.DataFrame(), metrics, pd.DataFrame()

    # Historical fitted values for chart overlay
    X_hist        = daily_df[FEATURE_COLS].values
    X_hist_scaled = scaler.transform(X_hist)
    fitted        = model.predict(X_hist_scaled)
    daily_df      = daily_df.copy()
    daily_df["fitted_yield"] = np.maximum(fitted, 0)

    # Residual std → 95% confidence interval
    residuals    = daily_df["total_yield"].values - daily_df["fitted_yield"].values
    residual_std = float(np.std(residuals))

    # Seed rolling history with known values
    history  = daily_df["total_yield"].tolist()
    last_row = daily_df.iloc[-1]

    forecast_rows = []
    today = date.today()

    for i in range(1, days_ahead + 1):
        fdate = today + timedelta(days=i)

        lag_1  = history[-1]
        lag_3  = float(np.mean(history[-3:]))
        lag_7  = float(np.mean(history[-7:]))  if len(history) >= 7  else float(np.mean(history))
        lag_14 = float(np.mean(history[-14:])) if len(history) >= 14 else float(np.mean(history))

        features = np.array([[
            fdate.weekday(),
            fdate.month,
            last_row["num_cows"],
            lag_1,
            lag_3,
            lag_7,
            lag_14,
            float(last_row["avg_dim"]) + i,
        ]])

        pred = float(model.predict(scaler.transform(features))[0])
        pred = max(pred, 0)

        ci = 1.96 * residual_std
        forecast_rows.append({
            "date":          fdate.isoformat(),
            "mlr_predicted": round(pred, 1),
            "lower_bound":   round(max(pred - ci, 0), 1),
            "upper_bound":   round(pred + ci, 1),
        })
        history.append(pred)

    forecast_df = pd.DataFrame(forecast_rows)
    return forecast_df, metrics, daily_df


# ── Model summary ──────────────────────────────────────────────────────────────

def get_model_summary(user_id=None):
    """
    Return a readable summary of the herd MLR model's coefficients and performance.
    """
    _, _, metrics, _ = train_mlr_model(user_id=user_id)

    if "error" in metrics:
        return metrics

    feature_names = {
        "day_of_week": "Day of Week",
        "month":       "Month (Seasonality)",
        "num_cows":    "Number of Cows",
        "lag_1":       "Yesterday's Production",
        "lag_3":       "3-Day Average",
        "lag_7":       "7-Day Average",
        "lag_14":      "14-Day Average",
        "avg_dim":     "Avg Days in Milk",
    }

    importance_df = pd.DataFrame([
        {"Feature": feature_names[k], "Importance": v}
        for k, v in sorted(
            metrics["feature_importance"].items(),
            key=lambda x: x[1], reverse=True,
        )
    ])

    return {
        "mae":           metrics["mae"],
        "r2":            metrics["r2"],
        "train_samples": metrics["train_samples"],
        "importance_df": importance_df,
    }
