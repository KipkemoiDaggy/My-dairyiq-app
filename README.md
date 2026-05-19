# 🐄 DairyMind — Dairy Farm Management System

A smart dairy farm management system with **milk production forecasting** and
**automated disease/anomaly detection**, built with Python and Streamlit.

---

## Features

| Module | Description |
|--------|-------------|
| 🏠 Dashboard | Live KPIs, herd production trend, active alerts |
| 🐄 Cow Management | Register cows, view individual profiles and health scores |
| 🥛 Log Milk Records | Single or bulk daily milk entry (morning + evening) |
| 📈 Milk Forecasting | Wood's Lactation Curve model — 7–30 day forecast per cow & herd |
| 🚨 Health Alerts | Statistical anomaly detection with z-score + sudden-drop rules |
| 📋 Health Records | Vet log — diagnose, treat, and track conditions per cow |

---

## Setup Instructions

### 1. Prerequisites
Make sure you have **Python 3.9+** installed.

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run app.py
```

The app will open automatically at `http://localhost:8501`

### 4. Load sample data
On first launch, click **⚡ Load Sample Data** in the sidebar. This generates
6 months of realistic data for 10 cows, including three injected illness events
to demonstrate the anomaly detection.

---

## How the ML Works

### Milk Production Forecasting — Wood's Lactation Curve
```
y(t) = a × t^b × exp(−c × t)
```
- `t` = days in milk (DIM)
- `a`, `b`, `c` = parameters fitted per cow using `scipy.optimize.curve_fit`
- Peak production occurs at `t_peak = b / c`
- Confidence bands shown at ±1.5 standard deviations of fitted residuals

### Anomaly / Disease Detection — Three-Rule Statistical System
| Rule | Trigger | Severity |
|------|---------|----------|
| Z-score baseline | < 1.8 std below 14-day personal mean | Warning |
| Z-score baseline | < 2.5 std below 14-day personal mean | Critical |
| Sudden drop | < 72% of 3-day moving average | Critical |
| Sustained decline | Declining for 5+ consecutive days | Warning |

---

## Project Structure
```
dairy_farm/
├── app.py               # Main Streamlit UI (all pages)
├── database.py          # SQLite database — all CRUD operations
├── forecasting.py       # Wood's lactation curve + forecasting logic
├── anomaly_detection.py # Statistical anomaly detection + health scores
├── sample_data.py       # Realistic data generator (10 cows, 180 days)
├── requirements.txt     # Python dependencies
└── README.md
```

The database (`dairy_farm.db`) is created automatically on first run.

---

## Tech Stack
- **Streamlit** — web UI
- **Pandas / NumPy** — data processing
- **SciPy** — Wood's model parameter fitting (`curve_fit`)
- **Plotly** — interactive charts
- **SQLite** — embedded database (no server required)
