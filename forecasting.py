"""
Milk Production Forecasting — Individual Cow Level
===================================================
Uses scikit-learn LinearRegression trained on each cow's own production
history to generate a 30-day forward forecast with confidence interval bounds.

Predictor variables
-------------------
    days_in_milk (DIM)  : continuous proxy for lactation stage
    season              : integer 0-3 (Winter/Spring/Summer/Autumn) derived
                          from the record month
    parity_proxy        : normalised record index as a proxy for parity /
                          cumulative lactation experience

Target
------
    total_yield : daily milk production (litres)

Metrics returned
----------------
    R²  : coefficient of determination (in-sample fit quality)
    MAE : Mean Absolute Error (litres/day)

Confidence intervals
--------------------
    ±1.96 × residual standard deviation (≈ 95% band)
"""

import numpy as np
import pandas as pd
from datetime import timedelta
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error


# ── Season helper ─────────────────────────────────────────────────────────────

def _month_to_season(month: int) -> int:
    """Map calendar month to season integer (0=Winter, 1=Spring, 2=Summer, 3=Autumn)."""
    return {12: 0, 1: 0, 2: 0,
            3: 1, 4: 1, 5: 1,
            6: 2, 7: 2, 8: 2,
            9: 3, 10: 3, 11: 3}[month]


# ── Individual-cow Linear Regression forecast ─────────────────────────────────

def forecast_cow_production(milk_df: pd.DataFrame, days_ahead: int = 30):
    """
    Forecast a single cow's daily milk production for the next `days_ahead` days
    using a LinearRegression model trained on that cow's own history.

    Parameters
    ----------
    milk_df    : DataFrame from database.get_all_milk_records_for_cow().
                 Must contain 'record_date', 'total_yield', and 'dim'.
    days_ahead : Number of future days to predict (default 30).

    Returns
    -------
    hist_df     : Historical records with 'fitted_yield' column added.
    forecast_df : Future predictions with columns:
                      date, predicted_yield, lower_bound, upper_bound.
    model_info  : dict — {'model', 'r2', 'mae', 'residual_std'}.
    """
    if milk_df.empty or len(milk_df) < 10:
        return pd.DataFrame(), pd.DataFrame(), {}

    hist_df = milk_df.copy().sort_values("record_date").reset_index(drop=True)
    hist_df["record_date"] = pd.to_datetime(hist_df["record_date"])
    hist_df["dim"] = hist_df["dim"].astype(float)

    # ── Build features ────────────────────────────────────────────────────────
    hist_df["season"]       = hist_df["record_date"].dt.month.map(_month_to_season)
    hist_df["parity_proxy"] = np.linspace(0, 1, len(hist_df))   # normalised index

    FEATURES = ["dim", "season", "parity_proxy"]
    X = hist_df[FEATURES].values
    y = hist_df["total_yield"].values

    # ── Fit model ─────────────────────────────────────────────────────────────
    model = LinearRegression()
    model.fit(X, y)

    y_fitted = np.maximum(model.predict(X), 0)
    hist_df["fitted_yield"] = np.round(y_fitted, 2)

    # ── In-sample metrics ─────────────────────────────────────────────────────
    r2  = round(r2_score(y, y_fitted), 4)
    mae = round(mean_absolute_error(y, y_fitted), 2)
    residual_std = float(np.std(y - y_fitted))

    model_info = {
        "model":        "Linear Regression",
        "r2":           r2,
        "mae":          mae,
        "residual_std": round(residual_std, 2),
    }

    # ── Forward forecast ──────────────────────────────────────────────────────
    last_date = hist_df["record_date"].max()
    last_dim  = float(hist_df["dim"].max())

    future_rows = []
    for i in range(1, days_ahead + 1):
        fdate   = last_date + timedelta(days=i)
        f_dim   = last_dim + i
        f_seas  = _month_to_season(fdate.month)
        f_ppar  = 1.0          # extrapolate beyond training (end of lactation proxy)

        pred = float(model.predict([[f_dim, f_seas, f_ppar]])[0])
        pred = max(pred, 0)

        ci = 1.96 * residual_std
        future_rows.append({
            "date":            fdate,
            "predicted_yield": round(pred, 2),
            "lower_bound":     round(max(pred - ci, 0), 2),
            "upper_bound":     round(pred + ci, 2),
        })

    forecast_df = pd.DataFrame(future_rows)

    return hist_df, forecast_df, model_info
