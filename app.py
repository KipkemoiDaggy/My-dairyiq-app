"""
DairyMind — Dairy Farm Management System
==========================================
Pages:
  🏠  Dashboard          — KPIs, today's production, active alerts
  🐄  Cow Management     — Register and manage cows
  🥛  Log Milk Records   — Daily milk entry (single or bulk)
  📈  Milk Forecasting   — Linear Regression forecast per cow & herd
  🚨  Health Alerts      — Anomaly detection & alert management
  📋  Health Records     — Vet log per cow
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta

import database as db
import forecasting as fc
import anomaly_detection as ad

import auth
import login_page

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DairyIQ — Milk Production Intelligence",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Professional CSS theme ────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Background */
[data-testid="stAppViewContainer"] > .main { background:#F0F3F4; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#0d2137 0%,#1B4F72 100%) !important; }
[data-testid="stSidebar"] * { color:#e8f0f7 !important; }
[data-testid="stSidebar"] .stRadio label { color:#c8dae8 !important; font-size:0.88rem; }
[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p { color:#ffffff !important; font-weight:600; }
[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,0.15) !important; }
[data-testid="stSidebar"] button { background:rgba(255,255,255,0.1) !important; color:#fff !important; border:1px solid rgba(255,255,255,0.2) !important; border-radius:8px !important; }

/* Page header */
.diq-page-banner {
    background: linear-gradient(135deg,#1B4F72,#1a6b3a);
    border-radius:12px; padding:1.4rem 1.8rem 1.2rem;
    margin-bottom:1.5rem;
    box-shadow:0 4px 16px rgba(27,79,114,0.18);
}
.diq-page-banner h1 { color:#fff; font-size:1.7rem; font-weight:800; margin:0 0 0.2rem; }
.diq-page-banner p  { color:rgba(255,255,255,0.78); font-size:0.87rem; margin:0; line-height:1.5; }

/* Section title */
.section-title { font-size:1.05rem; font-weight:700; color:#1B4F72; margin-top:1.2rem 0 0.4rem; }

/* KPI cards */
[data-testid="metric-container"] {
    background:#ffffff;
    border:1px solid #e2e8f0;
    border-radius:12px;
    padding:1rem 1.2rem;
    box-shadow:0 2px 8px rgba(27,79,114,0.07);
}
div[data-testid="stMetricValue"] > div { font-size:1.9rem !important; font-weight:700 !important; color:#1B4F72 !important; }
div[data-testid="stMetricLabel"] { font-size:0.78rem !important; font-weight:600 !important; color:#64748b !important; text-transform:uppercase; letter-spacing:0.05em; }

/* Alert cards — strict two-level system */
.alert-high {
    background:#FFEBEE; border-left:5px solid #C62828;
    padding:0.85rem 1.1rem; border-radius:8px; margin-bottom:0.7rem;
    box-shadow:0 2px 6px rgba(198,40,40,0.12);
    color:#1a1a1a;
}
.alert-medium {
    background:#FFF176; border-left:5px solid #F9A825;
    padding:0.85rem 1.1rem; border-radius:8px; margin-bottom:0.7rem;
    box-shadow:0 2px 6px rgba(249,168,37,0.12);
    color:#1a1a1a;
}

/* Info/explanation boxes */
.diq-info-box {
    background:#eaf4fb; border:1px solid #bee3f8;
    border-radius:10px; padding:1rem 1.2rem;
    margin-bottom:1rem; font-size:0.88rem; color:#1B2631; line-height:1.6;
}
.diq-info-box b, .diq-info-box strong { color:#1B2631; }

/* Force readable contrast in Streamlit native alert boxes */
[data-testid="stNotification"] > div,
[data-testid="stAlert"] > div,
div[data-baseweb="notification"] {
    color: #1B2631 !important;
}
div[data-baseweb="notification"] * {
    color: #1B2631 !important;
}

/* Dataframes */
[data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06); }

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab"] { font-weight:600; font-size:0.88rem; }

/* Footer */
.diq-footer {
    text-align:center; color:#64748b; font-size:0.73rem;
    padding:1.8rem 0 0.5rem; border-top:1px solid #e2e8f0; margin-top:2.5rem;
}
</style>
""", unsafe_allow_html=True)

# ── Database init ─────────────────────────────────────────────────────────────
db.initialize_db()
db.normalize_alert_severities()   # remap any legacy severity labels in DB

# ── Auth init ─────────────────────────────────────────────────────────────────
auth.init_auth_tables()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login_page.show_login_page()
    st.stop()

# Load sample data for guest automatically
if st.session_state.get("guest_mode"):
    import sample_data
    if not db.cow_exists(user_id=0):
        sample_data.generate_all()

# ── Current user ──────────────────────────────────────────────────────────────
user_id = st.session_state.get("user_id")

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""<div style='padding:0.6rem 0 0.2rem;'>
        <div style='font-size:1.6rem;font-weight:800;letter-spacing:-0.5px;'>🐄 DairyIQ</div>
        <div style='font-size:0.72rem;opacity:0.6;margin-top:0.1rem;'>Milk Production Intelligence System</div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    _NAV_ITEMS = {
        "🏠 Dashboard":       "KPIs, herd trend & live alerts",
        "🐄 Cow Management":  "Register cows & view profiles",
        "🥛 Log Milk Records": "Daily yield entry — single or bulk",
        "📈 Milk Forecasting": "30-day LR forecasts per cow & herd",
        "🚨 Health Alerts":    "Z-Score anomaly scan & alert log",
        "📋 Health Records":   "Veterinary conditions & treatments",
    }
    page = st.radio(
        "Navigate",
        list(_NAV_ITEMS.keys()),
        label_visibility="collapsed",
    )
    st.markdown(
        f"<div style='font-size:0.72rem;opacity:0.55;margin-top:-0.6rem;padding-left:0.3rem;'>"
        f"{_NAV_ITEMS[page]}</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    if not st.session_state.get("guest_mode"):
        with st.expander("👤 My Profile"):
            import sqlite3
            conn = sqlite3.connect('dairy_farm.db')
            user = conn.execute(
                "SELECT full_name, date_of_birth, farm_name, email FROM users WHERE id=?",
                (st.session_state.get("user_id"),)
            ).fetchone()
            conn.close()
            if user:
                st.markdown(f"**Name:** {user[0] or '—'}")
                st.markdown(f"**Email:** {user[3]}")
                st.markdown(f"**Date of Birth:** {user[1] or '—'}")
                st.markdown(f"**Farm Name:** {user[2] or '—'}")

    st.divider()
    if not st.session_state.get("guest_mode"):
        st.caption(f"👤 {st.session_state.get('user_email','')}")
    if st.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.caption(f"📅 {date.today().strftime('%d %b %Y')}") 


# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def page_banner(icon, title, subtitle):
    """Render the gradient page header banner."""
    st.markdown(
        f'<div class="diq-page-banner">'
        f'<h1>{icon} {title}</h1>'
        f'<p>{subtitle}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def diq_footer():
    st.markdown(
        '<div class="diq-footer">DairyIQ &copy; 2026</div>',
        unsafe_allow_html=True,
    )


def severity_badge(s):
    """Return an HTML severity badge — strict HIGH (red) / MEDIUM (yellow) only."""
    _SEV = _normalize_severity_label(s)
    if _SEV == "HIGH":
        return '<span style="color:#C62828;font-weight:700;">&#9679; HIGH</span>'
    elif _SEV == "MEDIUM":
        return '<span style="color:#F9A825;font-weight:700;">&#9679; MEDIUM</span>'
    return '<span style="color:#27ae60;font-weight:700;">&#9679; NORMAL</span>'


def _normalize_severity_label(s: str) -> str:
    """Map any legacy label to the canonical HIGH | MEDIUM | normal."""
    s = (s or "").strip().upper()
    if s in ("HIGH", "CRITICAL", "SEVERE"):
        return "HIGH"
    if s in ("MEDIUM", "WARNING", "WARN", "LOW"):
        return "MEDIUM"
    return "normal"


def health_score_color(score):
    if score >= 90: return "#27ae60"
    if score >= 75: return "#2ecc71"
    if score >= 60: return "#f39c12"
    if score >= 40: return "#e67e22"
    return "#e74c3c"


def cow_select(label="Select Cow", key=None, user_id=None):
    cows = db.get_all_cows(user_id=user_id)
    if cows.empty:
        st.warning("No cows registered yet. Go to Cow Management first.")
        return None, None
    options = {f"{r['name']} ({r['tag_number']})": r["id"] for _, r in cows.iterrows()}
    choice = st.selectbox(label, list(options.keys()), key=key)
    return options[choice], choice


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

if page == "🏠 Dashboard":
    page_banner("🏠", "Farm Dashboard",
        "Real-time milk production monitoring, early anomaly detection using Z-Score analysis, "
        "and 30-day yield forecasting using Linear Regression for individual cows and herd-level planning.")

    total_cows, today_prod, yesterday_prod, active_alerts = db.get_herd_summary(user_id=user_id)
    delta_prod  = today_prod - yesterday_prod
    avg_per_cow = round(today_prod / total_cows, 1) if total_cows else 0

    # ── KPI row ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🐄 Active Cows", total_cows)
    c2.metric("🥛 Today's Production", f"{today_prod:.1f} L",
              delta=f"{delta_prod:+.1f} L vs yesterday")
    c3.metric("📊 Avg per Cow", f"{avg_per_cow} L")
    c4.metric("🚨 Active Alerts", active_alerts,
              delta="Needs attention" if active_alerts > 0 else "All clear",
              delta_color="inverse")

    st.divider()

    col_left, col_right = st.columns([3, 2])

    # ── 30-day herd production trend ─────────────────────────────────────────
    with col_left:
        st.markdown('<p class="section-title">📈 30-Day Herd Production Trend</p>', unsafe_allow_html=True)
        trend_df = db.get_milk_records(days=30, user_id=user_id)
        if not trend_df.empty:
            daily = (
                trend_df.groupby("record_date")["total_yield"].sum().reset_index()
            )
            daily.columns = ["Date", "Total (L)"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily["Date"], y=daily["Total (L)"],
                mode="lines+markers",
                line=dict(color="#1a5276", width=2.5),
                marker=dict(size=5),
                fill="tozeroy",
                fillcolor="rgba(26,82,118,0.1)",
                name="Daily Total",
            ))
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=260,
                xaxis_title="", yaxis_title="Litres",
                plot_bgcolor="white",
                yaxis=dict(gridcolor="#f0f0f0"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No production records yet.")

    # ── Active alerts panel ───────────────────────────────────────────────────
    with col_right:
        st.markdown('<p class="section-title">🚨 Active Alerts</p>', unsafe_allow_html=True)
        alerts_df = db.get_active_alerts(user_id=user_id)
        if alerts_df.empty:
            st.success("✅ No active alerts — herd looks healthy!")
        else:
            for _, alert in alerts_df.head(6).iterrows():
                sev = _normalize_severity_label(alert["severity"])
                cls  = "alert-high" if sev == "HIGH" else "alert-medium"
                icon = "🔴" if sev == "HIGH" else "🟡"
                st.markdown(
                    f'<div class="{cls}">{icon} <b>{alert["cow_name"]}</b> '
                    f'— {alert["message"][:100]}…</div>',
                    unsafe_allow_html=True,
                )
            if len(alerts_df) > 6:
                st.caption(f"+ {len(alerts_df)-6} more alerts. See Health Alerts page.")

    st.divider()

    # ── Today's per-cow production ────────────────────────────────────────────
    st.markdown('<p class="section-title">🥛 Today\'s Production by Cow</p>', unsafe_allow_html=True)
    today_df = db.get_milk_records(days=1, user_id=user_id)
    today_only = today_df[today_df["record_date"] == date.today().isoformat()]

    if today_only.empty:
        st.info("No milk records entered for today yet. Go to **Log Milk Records** to add them.")
    else:
        today_only = today_only.sort_values("total_yield", ascending=True)
        avg_line = today_only["total_yield"].mean()
        fig2 = go.Figure(go.Bar(
            x=today_only["total_yield"],
            y=today_only["cow_name"],
            orientation="h",
            marker_color=[
                "#e74c3c" if v < avg_line * 0.75 else
                "#f39c12" if v < avg_line * 0.90 else
                "#27ae60"
                for v in today_only["total_yield"]
            ],
            text=[f"{v:.1f}L" for v in today_only["total_yield"]],
            textposition="outside",
        ))
        fig2.add_vline(x=avg_line, line_dash="dash", line_color="#666",
                       annotation_text=f"Avg {avg_line:.1f}L")
        fig2.update_layout(
            margin=dict(l=0, r=60, t=10, b=0),
            height=max(250, len(today_only) * 35),
            xaxis_title="Litres", yaxis_title="",
            plot_bgcolor="white",
        )
        st.plotly_chart(fig2, use_container_width=True)

    diq_footer()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: COW MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🐄 Cow Management":
    page_banner("🐄", "Cow Management",
        "Register new cows, view herd roster with health scores, and inspect individual production histories.")

    tab1, tab2 = st.tabs(["📋 All Cows", "➕ Register New Cow"])

    with tab1:
        cows_df = db.get_all_cows(user_id=user_id)
        if cows_df.empty:
            st.info("No cows registered yet.")
        else:
            rows = []
            for _, cow in cows_df.iterrows():
                milk = db.get_all_milk_records_for_cow(cow["id"])
                last7 = milk.tail(7)["total_yield"].mean() if not milk.empty else 0
                score, label = ad.get_health_score(milk) if not milk.empty else (75, "—")
                rows.append({
                    "Name": cow["name"],
                    "Tag": cow["tag_number"],
                    "Breed": cow["breed"],
                    "Lactation Start": cow["lactation_start_date"],
                    "7-Day Avg (L)": round(last7, 1),
                    "Health": label,
                    "Score": score,
                })
            display = pd.DataFrame(rows)

            def color_health(val):
                c = {"Excellent":"#d5f5e3","Good":"#eafaf1","Monitor":"#fef9e7",
                     "Concern":"#fdebd0","Critical":"#fdecea"}.get(val, "white")
                return f"background-color:{c}"

            st.dataframe(
                display.style.map(color_health, subset=["Health"]),
                use_container_width=True, hide_index=True,
            )

            st.divider()
            st.markdown("#### 🔍 Individual Cow Profile")
            cow_id, _ = cow_select("Select a cow to view", key="profile_cow", user_id=user_id)
            if cow_id:
                cow = db.get_cow_by_id(cow_id)
                milk = db.get_all_milk_records_for_cow(cow_id)
                score, label = ad.get_health_score(milk)
                color = health_score_color(score)

                cc1, cc2, cc3, cc4 = st.columns(4)
                cc1.metric("Name", cow["name"])
                cc2.metric("Breed", cow["breed"])
                cc3.metric("Tag #", cow["tag_number"])
                cc4.metric("Health Score", f"{score}/100 — {label}")

                if not milk.empty:
                    recent = milk.tail(14)
                    fig = go.Figure(go.Scatter(
                        x=recent["record_date"], y=recent["total_yield"],
                        mode="lines+markers", line=dict(color=color, width=2),
                        name="Daily yield",
                    ))
                    fig.update_layout(
                        title="Last 14 Days Production",
                        height=220, margin=dict(l=0,r=0,t=30,b=0),
                        plot_bgcolor="white",
                        yaxis=dict(gridcolor="#f0f0f0"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("#### Register a New Cow")
        with st.form("add_cow_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Cow Name *")
            tag = col2.text_input("Tag Number *", placeholder="e.g. KE-011")
            breed = col1.selectbox("Breed", ["Friesian","Holstein","Jersey","Ayrshire","Guernsey","Cross-breed","Other"])
            dob = col2.date_input("Date of Birth", value=date.today() - timedelta(days=365*4))
            lac_start = col1.date_input("Lactation Start Date", value=date.today() - timedelta(days=30))
            notes = st.text_area("Notes (optional)")
            submitted = st.form_submit_button("✅ Register Cow", use_container_width=True)
            if submitted:
                if not name or not tag:
                    st.error("Name and Tag Number are required.")
                else:
                    ok, msg = db.add_cow(name, tag, breed, dob.isoformat(), lac_start.isoformat(), notes, user_id=user_id)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    diq_footer()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: LOG MILK RECORDS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🥛 Log Milk Records":
    page_banner("🥛", "Log Milk Records",
        "Enter morning and evening yields for individual cows or submit bulk entries for the full herd at once.")

    tab1, tab2 = st.tabs(["Single Cow Entry", "📦 Bulk Entry (All Cows)"])

    with tab1:
        cow_id, _ = cow_select("Select Cow", key="milk_log_cow", user_id=user_id)
        if cow_id:
            with st.form("single_milk_form"):
                col1, col2, col3 = st.columns(3)
                rec_date = col1.date_input("Date", value=date.today())
                morning = col2.number_input("Morning Yield (L)", min_value=0.0, step=0.1, format="%.1f")
                evening = col3.number_input("Evening Yield (L)", min_value=0.0, step=0.1, format="%.1f")
                notes = st.text_input("Notes (optional)")
                save = st.form_submit_button("💾 Save Record", use_container_width=True)

            if save:
                ok, msg = db.add_milk_record(cow_id, rec_date.isoformat(), morning, evening, notes, user_id=user_id)
                if ok:
                    st.success(f"✅ {msg} — Total: {morning+evening:.1f}L")
                else:
                    st.error(f"❌ {msg}")

            # Recent records
            st.divider()
            recent = db.get_milk_records(cow_id=cow_id, days=14, user_id=user_id)
            if not recent.empty:
                st.markdown("**Last 14 days:**")
                show = recent[["record_date","morning_yield","evening_yield","total_yield","notes"]].copy()
                show.columns = ["Date","Morning (L)","Evening (L)","Total (L)","Notes"]
                st.table(show.sort_values("Date", ascending=False))

    with tab2:
        st.markdown("Enter today's production for all cows at once.")
        bulk_date = st.date_input("Date for bulk entry", value=date.today())
        cows_df = db.get_all_cows(user_id=user_id)

        if cows_df.empty:
            st.info("No cows registered.")
        else:
            bulk_data = {}
            for _, cow in cows_df.iterrows():
                st.markdown(f"**{cow['name']} ({cow['tag_number']})**")
                b1, b2 = st.columns(2)
                m = b1.number_input(f"Morning (L)", min_value=0.0, step=0.1,
                                    key=f"bulk_m_{cow['id']}", format="%.1f")
                e = b2.number_input(f"Evening (L)", min_value=0.0, step=0.1,
                                    key=f"bulk_e_{cow['id']}", format="%.1f")
                bulk_data[cow["id"]] = (m, e)

            if st.button("💾 Save All Records", use_container_width=True, type="primary"):
                saved, skipped = 0, 0
                for cid, (m, e) in bulk_data.items():
                    if m + e > 0:
                        ok, _ = db.add_milk_record(cid, bulk_date.isoformat(), m, e, user_id=user_id)
                        saved += 1 if ok else 0
                    else:
                        skipped += 1
                st.success(f"✅ Saved {saved} records. Skipped {skipped} zero-yield entries.")

    diq_footer()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: MILK FORECASTING
# ═════════════════════════════════════════════════════════════════════════════

elif page == "📈 Milk Forecasting":
    page_banner("📈", "Milk Production Forecasting",
        "30-day yield forecasts generated using Multiple Linear Regression trained on days in milk, parity, and season. "
        "Individual cow and herd-level forecasts include 95% confidence interval bands. "
        "Model accuracy is reported as R² and Mean Absolute Error in litres per day.")

    st.markdown(
        '<div class="diq-info-box">'
        '<b>💡 How forecasting works:</b> A scikit-learn LinearRegression model is trained on each cow\'s own '
        'historical records using <b>days in milk</b>, <b>season</b>, and a <b>parity proxy</b> as predictors. '
        'The herd-level model additionally uses lag features (1-, 3-, 7-, 14-day averages) and herd size. '
        'Forecasts extend up to 30 days forward with a ±1.96σ confidence band.'
        '</div>',
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["🐄 Individual Cow", "🌐 Herd Forecast"])

    with tab1:
        cow_id, cow_label = cow_select("Select Cow", key="forecast_cow", user_id=user_id)
        days_ahead = st.slider("Forecast horizon (days)", 7, 30, 30)

        if cow_id:
            milk_df = db.get_all_milk_records_for_cow(cow_id)

            if milk_df.empty or len(milk_df) < 10:
                st.warning("Need at least 10 days of records to generate a forecast.")
            else:
                with st.spinner("Training Linear Regression model…"):
                    hist_df, forecast_df, model_info = fc.forecast_cow_production(milk_df, days_ahead)

                if forecast_df.empty:
                    st.error("Could not generate forecast for this cow.")
                else:
                    # ── Model metrics row ─────────────────────────────────────
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Model", model_info.get("model", "Linear Regression"))
                    m2.metric(
                        "R² (fit quality)",
                        f"{model_info.get('r2', 0):.4f}",
                        help="1.0 = perfect fit. Values above 0.7 indicate a reliable model.",
                    )
                    m3.metric(
                        "MAE",
                        f"{model_info.get('mae', 0):.2f} L/day",
                        help="Mean Absolute Error — average daily prediction error on training data.",
                    )

                    # ── Forecast chart ────────────────────────────────────────
                    fig = go.Figure()

                    fig.add_trace(go.Scatter(
                        x=hist_df["record_date"], y=hist_df["total_yield"],
                        mode="markers",
                        marker=dict(color="#7fb3d3", size=5, opacity=0.7),
                        name="Actual Production",
                    ))

                    if "fitted_yield" in hist_df.columns:
                        fig.add_trace(go.Scatter(
                            x=hist_df["record_date"], y=hist_df["fitted_yield"],
                            mode="lines",
                            line=dict(color="#1a5276", width=2),
                            name="LR Fitted (Historical)",
                        ))

                    fig.add_trace(go.Scatter(
                        x=forecast_df["date"], y=forecast_df["predicted_yield"],
                        mode="lines+markers",
                        line=dict(color="#e74c3c", width=2.5, dash="dot"),
                        marker=dict(size=6, color="#e74c3c"),
                        name=f"{days_ahead}-Day LR Forecast",
                    ))

                    fig.add_trace(go.Scatter(
                        x=pd.concat([forecast_df["date"], forecast_df["date"][::-1]]),
                        y=pd.concat([forecast_df["upper_bound"], forecast_df["lower_bound"][::-1]]),
                        fill="toself",
                        fillcolor="rgba(231,76,60,0.12)",
                        line=dict(color="rgba(255,255,255,0)"),
                        name="95% Confidence Band",
                        showlegend=True,
                    ))

                    try:
                        fig.add_vline(
                            x=str(date.today()),
                            line_dash="dash", line_color="gray",
                            annotation_text="Today",
                        )
                    except:
                        pass

                    fig.update_layout(
                        title=f"LR Forecast — {cow_label}  |  R² = {model_info.get('r2',0):.4f}  |  MAE = {model_info.get('mae',0):.2f} L/day",
                        xaxis_title="Date", yaxis_title="Litres / Day",
                        height=450,
                        plot_bgcolor="white",
                        yaxis=dict(gridcolor="#f0f0f0"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("#### Forecast Values")
                    tbl = forecast_df[["date", "predicted_yield", "lower_bound", "upper_bound"]].copy()
                    tbl.columns = ["Date", "Predicted (L)", "Lower Bound (L)", "Upper Bound (L)"]
                    tbl["Date"] = tbl["Date"].astype(str)
                    st.dataframe(tbl, hide_index=True, use_container_width=True)

                    total_forecast = forecast_df["predicted_yield"].sum()
                    st.info(f"📦 Estimated total production over next {days_ahead} days: **{total_forecast:.1f} L**")

    with tab2:
        st.markdown("### 📊 Herd-Level Linear Regression Forecast")
        h_days = st.slider("Forecast horizon (days)", 7, 30, 30, key="herd_days")

        import mlr_forecasting as mlr

        st.divider()

        with st.spinner("Training herd-level MLR model and generating forecast…"):
            forecast_df, metrics, fitted_df = mlr.forecast_herd_mlr(
                days_ahead=h_days, user_id=user_id
            )

        if "error" in metrics:
            st.warning(f"⚠️ {metrics['error']}")
        else:
            # ── Model metrics row ─────────────────────────────────────────────
            m1, m2, m3 = st.columns(3)
            m1.metric("R² Score", f"{metrics['r2']:.4f}", help="Closer to 1.0 = better fit")
            m2.metric("MAE", f"{metrics['mae']:.1f} L/day", help="Mean Absolute Error on training data")
            m3.metric("Training Days", metrics["train_samples"])

            if not forecast_df.empty:
                total_mlr = forecast_df["mlr_predicted"].sum()
                st.metric(
                    "Projected Herd Total",
                    f"{total_mlr:.0f} L",
                    help=f"Cumulative herd production over the next {h_days} days",
                )

                fig_mlr = go.Figure()

                if not fitted_df.empty:
                    fig_mlr.add_trace(go.Scatter(
                        x=fitted_df["record_date"].astype(str),
                        y=fitted_df["total_yield"],
                        mode="markers",
                        marker=dict(color="#aed6f1", size=4, opacity=0.5),
                        name="Actual (Historical)",
                    ))
                    fig_mlr.add_trace(go.Scatter(
                        x=fitted_df["record_date"].astype(str),
                        y=fitted_df["fitted_yield"],
                        mode="lines",
                        line=dict(color="#7fb3d3", width=1.5, dash="dot"),
                        name="MLR Fitted (Historical)",
                    ))


                fig_mlr.add_trace(go.Scatter(
                    x=forecast_df["date"],
                    y=forecast_df["mlr_predicted"],
                    mode="lines+markers",
                    line=dict(color="#e74c3c", width=2.5),
                    marker=dict(size=6),
                    name="MLR Forecast",
                ))
                fig_mlr.add_trace(go.Scatter(
                    x=pd.concat([forecast_df["date"], forecast_df["date"][::-1]]),
                    y=pd.concat([forecast_df["upper_bound"], forecast_df["lower_bound"][::-1]]),
                    fill="toself",
                    fillcolor="rgba(231,76,60,0.10)",
                    line=dict(color="rgba(255,255,255,0)"),
                    name="95% Confidence Band",
                ))
                fig_mlr.update_layout(
                    title=f"Herd MLR Forecast — Next {h_days} Days  |  R² = {metrics['r2']:.4f}  |  MAE = {metrics['mae']:.1f} L/day",
                    xaxis_title="Date", yaxis_title="Total Litres",
                    height=420, plot_bgcolor="white",
                    yaxis=dict(gridcolor="#f0f0f0"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_mlr, use_container_width=True)

                st.markdown("#### Forecast Values")
                st.dataframe(
                    forecast_df.rename(columns={
                        "date":          "Date",
                        "mlr_predicted": "Predicted (L)",
                        "lower_bound":   "Lower Bound (L)",
                        "upper_bound":   "Upper Bound (L)",
                    }),
                    hide_index=True, use_container_width=True,
                )

            with st.expander("📊 Model Details — Feature Importance"):
                summary = mlr.get_model_summary(user_id=user_id)
                if "importance_df" in summary:
                    fig_imp = go.Figure(go.Bar(
                        x=summary["importance_df"]["Importance"],
                        y=summary["importance_df"]["Feature"],
                        orientation="h",
                        marker_color="#1a5276",
                    ))
                    fig_imp.update_layout(
                        title="Feature Importance (Absolute Scaled Coefficients)",
                        height=300, plot_bgcolor="white",
                        margin=dict(l=0, r=0, t=40, b=0),
                    )
                    st.plotly_chart(fig_imp, use_container_width=True)
                    st.caption(
                        f"R² = {summary['r2']} | MAE = {summary['mae']} L/day | "
                        f"Trained on {summary['train_samples']} days"
                    )

    diq_footer()
# ═════════════════════════════════════════════════════════════════════════════
# PAGE: HEALTH ALERTS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🚨 Health Alerts":
    page_banner("🚨", "Health Alerts & Anomaly Detection",
        "Z-Score anomaly detection monitors each cow's yield against her personal historical baseline. "
        "Alerts trigger when yield deviates beyond 2 or 3 standard deviations, drops below 75% of the "
        "7-day rolling mean, or shows a sustained linear decline over a 14-day window.")

    st.markdown(
        '<div class="diq-info-box">'
        '<b>🔍 Three-rule detection framework:</b><br>'
        '🟡 <b>Rule 1 — Z-Score MEDIUM:</b> yield &gt; 2 SD below personal 7-day rolling baseline &nbsp;|&nbsp; '
        '🔴 <b>Rule 1 — Z-Score HIGH:</b> yield &gt; 3 SD below baseline<br>'
        '🔴 <b>Rule 2 — Acute Drop HIGH:</b> today\'s yield &lt; 75% of 7-day rolling mean (flags mastitis, toxic ingestion)<br>'
        '🟡 <b>Rule 3 — Trend MEDIUM:</b> linear regression slope &lt; −0.2 L/day with R² &gt; 0.6 over a 14-day window<br>'
        '<small>Early detection allows treatment before major yield loss — typical mastitis can be caught 2–3 days before visible symptoms.</small>'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("🔍 Run Z-Score Anomaly Scan", type="primary", use_container_width=True):
            with st.spinner("Running Z-Score scan across all cows…"):
                stat_anomalies = ad.run_anomaly_scan(save_alerts=True, user_id=user_id)
            if stat_anomalies:
                st.warning(f"📊 Found **{len(stat_anomalies)}** anomaly event(s). See alerts below.")
            else:
                st.success("✅ Z-Score scan complete — no anomalies detected.")

    with col2:
        if st.button("🗑️ Clear All Resolved Alerts", use_container_width=True):
            db.clear_old_resolved_alerts(days=0, user_id=user_id)
            st.success("Cleared.")

    st.divider()

    alerts_df = db.get_active_alerts(user_id=user_id)

    if alerts_df.empty:
        st.success("✅ No active alerts at this time.")
    else:
        st.markdown(f"### 🔔 {len(alerts_df)} Active Alert(s)")

        for _, alert in alerts_df.iterrows():
            sev  = _normalize_severity_label(alert["severity"])
            icon = "🔴" if sev == "HIGH" else "🟡"
            cls  = "alert-high" if sev == "HIGH" else "alert-medium"
            atype_label = alert["alert_type"].replace("_", " ").title()

            with st.container():
                st.markdown(
                    f'<div class="{cls}">'
                    f'<b>{icon} <span style="color:{"#C62828" if sev=="HIGH" else "#F9A825"}">{sev}</span></b>'
                    f' — <b>{alert["cow_name"]}</b> ({alert["tag_number"]})<br>'
                    f'{alert["message"]}<br>'
                    f'<small>📅 {alert["alert_date"]} &nbsp;|&nbsp; Rule: {atype_label}</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"✅ Mark Resolved", key=f"resolve_{alert['id']}"):
                    db.resolve_alert(int(alert["id"]))
                    st.rerun()

    st.divider()

    st.markdown("### 🩺 Herd Health Scores")
    cows_df = db.get_all_cows(user_id=user_id)
    if not cows_df.empty:
        health_rows = []
        for _, cow in cows_df.iterrows():
            milk = db.get_all_milk_records_for_cow(cow["id"])
            score, label = ad.get_health_score(milk) if not milk.empty else (0, "No data")
            health_rows.append({
                "Cow": cow["name"],
                "Tag": cow["tag_number"],
                "Score": score,
                "Status": label,
            })
        health_df = pd.DataFrame(health_rows).sort_values("Score")

        fig = go.Figure(go.Bar(
            x=health_df["Score"],
            y=health_df["Cow"],
            orientation="h",
            marker_color=[health_score_color(s) for s in health_df["Score"]],
            text=[f"{s}/100 — {l}" for s, l in zip(health_df["Score"], health_df["Status"])],
            textposition="outside",
        ))
        fig.add_vline(x=75, line_dash="dash", line_color="#f39c12",
                      annotation_text="Healthy threshold")
        fig.update_layout(
            height=max(300, len(health_df) * 38),
            margin=dict(l=0, r=100, t=10, b=0),
            xaxis=dict(range=[0, 115], title="Health Score"),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.markdown("### 🔎 Detailed Anomaly View")
    cow_id, _ = cow_select("Inspect a specific cow", key="anomaly_cow", user_id=user_id)
    if cow_id:
        milk_df = db.get_all_milk_records_for_cow(cow_id)
        if milk_df.empty:
            st.info("No milk records for this cow.")
        else:
            analyzed = ad.detect_anomalies_for_cow(milk_df)
            recent_analyzed = analyzed.tail(60)

            fig = go.Figure()
            normal = recent_analyzed[~recent_analyzed["is_anomaly"]]
            fig.add_trace(go.Scatter(
                x=normal["record_date"], y=normal["total_yield"],
                mode="markers",
                marker=dict(color="#27ae60", size=6),
                name="Normal",
            ))
            warns = recent_analyzed[recent_analyzed["anomaly_severity"] == "MEDIUM"]
            if not warns.empty:
                fig.add_trace(go.Scatter(
                    x=warns["record_date"], y=warns["total_yield"],
                    mode="markers",
                    marker=dict(color="#f39c12", size=10, symbol="diamond"),
                    name="Warning",
                ))
            crits = recent_analyzed[recent_analyzed["anomaly_severity"] == "HIGH"]
            if not crits.empty:
                fig.add_trace(go.Scatter(
                    x=crits["record_date"], y=crits["total_yield"],
                    mode="markers",
                    marker=dict(color="#e74c3c", size=12, symbol="x"),
                    name="Critical",
                ))
            if "rolling_mean" in recent_analyzed.columns:
                fig.add_trace(go.Scatter(
                    x=recent_analyzed["record_date"],
                    y=recent_analyzed["rolling_mean"],
                    mode="lines",
                    line=dict(color="#7fb3d3", dash="dot", width=1.5),
                    name="14-Day Rolling Mean",
                ))

            fig.update_layout(
                title="Last 60 Days — Anomaly Detection Overlay",
                xaxis_title="Date", yaxis_title="Litres",
                height=380, plot_bgcolor="white",
                yaxis=dict(gridcolor="#f0f0f0"),
            )
            st.plotly_chart(fig, use_container_width=True)

            anomaly_count = recent_analyzed["is_anomaly"].sum()
            if anomaly_count:
                st.warning(f"⚠️ {anomaly_count} anomalous day(s) detected in the last 60 records.")
                st.dataframe(
                    recent_analyzed[recent_analyzed["is_anomaly"]][
                        ["record_date","total_yield","rolling_mean","z_score","anomaly_severity","anomaly_reason"]
                    ].rename(columns={
                        "record_date":"Date","total_yield":"Yield (L)",
                        "rolling_mean":"Expected (L)","z_score":"Z-Score",
                        "anomaly_severity":"Severity","anomaly_reason":"Reason",
                    }).sort_values("Date", ascending=False),
                    hide_index=True, use_container_width=True,
                )
            else:
                st.success("✅ No anomalies detected for this cow in the last 60 days.")

    diq_footer()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: HEALTH RECORDS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "📋 Health Records":
    page_banner("📋", "Health Records",
        "Log and track veterinary conditions, treatments, and follow-up dates for each cow in the herd.")

    tab1, tab2 = st.tabs(["📖 View Records", "➕ Log New Record"])

    with tab1:
        view_mode = st.radio("View", ["All Cows", "Single Cow"], horizontal=True)

        if view_mode == "Single Cow":
            cow_id, _ = cow_select("Select Cow", key="health_view_cow", user_id=user_id)
            records = db.get_health_records(cow_id=cow_id, user_id=user_id) if cow_id else pd.DataFrame()
        else:
            records = db.get_health_records(user_id=user_id)

        if records.empty:
            st.info("No health records found.")
        else:
            for _, rec in records.iterrows():
                status = "✅ Resolved" if rec.get("resolved") else "🔄 Ongoing"
                with st.expander(f"{rec['cow_name']} ({rec['tag_number']}) — {rec['condition']} — {rec['record_date']} — {status}"):
                    r1, r2 = st.columns(2)
                    r1.markdown(f"**Condition:** {rec['condition']}")
                    r1.markdown(f"**Treatment:** {rec.get('treatment','—')}")
                    r2.markdown(f"**Follow-up:** {rec.get('follow_up_date','—')}")
                    r2.markdown(f"**Status:** {status}")
                    st.markdown(f"**Vet Notes:** {rec.get('vet_notes','—')}")
                    if not rec.get("resolved"):
                        if st.button("Mark as Resolved", key=f"res_hr_{rec['id']}"):
                            db.resolve_health_record(int(rec["id"]))
                            st.rerun()

    with tab2:
        st.markdown("#### Log a New Health Record")
        cow_id, _ = cow_select("Cow", key="health_add_cow", user_id=user_id)
        if cow_id:
            with st.form("health_form"):
                h1, h2 = st.columns(2)
                rec_date = h1.date_input("Date of Condition", value=date.today())
                condition = h2.selectbox("Condition / Diagnosis", [
                    "Mastitis", "Bloat", "Lameness", "Milk Fever", "Ketosis",
                    "Pneumonia", "Diarrhoea", "Eye Infection", "Tick Fever",
                    "East Coast Fever", "Routine Check", "Vaccination", "Other",
                ])
                treatment = st.text_input("Treatment Administered")
                vet_notes = st.text_area("Vet Notes / Observations")
                follow_up = st.date_input("Follow-up Date (optional)",
                                          value=date.today() + timedelta(days=7))
                save = st.form_submit_button("💾 Save Health Record", use_container_width=True)

            if save:
                ok, msg = db.add_health_record(
                    cow_id, rec_date.isoformat(), condition,
                    treatment, vet_notes, follow_up.isoformat(),
                    user_id=user_id,
                )
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    diq_footer()
