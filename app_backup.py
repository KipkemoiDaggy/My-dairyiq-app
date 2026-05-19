"""
DairyMind — Dairy Farm Management System
==========================================
Pages:
  🏠  Dashboard          — KPIs, today's production, active alerts
  🐄  Cow Management     — Register and manage cows
  🥛  Log Milk Records   — Daily milk entry (single or bulk)
  📈  Milk Forecasting   — Wood's curve forecast per cow & herd
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

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DairyMind",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {font-size:2rem; font-weight:700; color:#1a5276; margin-bottom:0.2rem;}
    .sub-header  {font-size:0.95rem; color:#666; margin-bottom:1.5rem;}
    .alert-critical {background:#fdecea; border-left:4px solid #e74c3c;
                     padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.5rem;}
    .alert-warning  {background:#fef9e7; border-left:4px solid #f39c12;
                     padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.5rem;}
    .metric-card    {background:#f8f9fa; border-radius:8px; padding:1rem;
                     border:1px solid #e9ecef;}
    .section-title  {font-size:1.1rem; font-weight:600; color:#2c3e50; margin-top:1rem;}
    div[data-testid="stMetricValue"] > div {font-size:1.8rem !important;}
</style>
""", unsafe_allow_html=True)

# ── Database init ─────────────────────────────────────────────────────────────
db.initialize_db()


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🐄 DairyMind")
    st.markdown("*Smart Dairy Farm Management*")
    st.divider()

    page = st.radio(
        "Navigate",
        ["🏠 Dashboard", "🐄 Cow Management", "🥛 Log Milk Records",
         "📈 Milk Forecasting", "🚨 Health Alerts", "📋 Health Records"],
        label_visibility="collapsed",
    )

    st.divider()

    # Quick sample-data loader
    if not db.cow_exists():
        st.info("No data found. Load sample data to get started.")
    if st.button("⚡ Load Sample Data", use_container_width=True):
        with st.spinner("Generating 6 months of farm data…"):
            import sample_data
            sample_data.generate_all()
        st.success("Sample data loaded!")
        st.rerun()

    if st.button("🗑️ Demo Mode", use_container_width=True):
            import sqlite3
            conn = sqlite3.connect('dairy_farm.db')
            conn.execute("DELETE FROM cows")
            conn.execute("DELETE FROM milk_records")
            conn.execute("DELETE FROM health_records")
            conn.execute("DELETE FROM alerts")
            conn.commit()
            conn.close()
            st.success("Database cleared!")
            st.rerun()

    st.caption(f"Today: {date.today().strftime('%d %b %Y')}")


# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def severity_badge(s):
    colors = {"critical": "#e74c3c", "warning": "#f39c12", "normal": "#27ae60"}
    return f'<span style="color:{colors.get(s,"#999")};font-weight:700;">{"🔴" if s=="critical" else "🟡" if s=="warning" else "🟢"} {s.upper()}</span>'


def health_score_color(score):
    if score >= 90: return "#27ae60"
    if score >= 75: return "#2ecc71"
    if score >= 60: return "#f39c12"
    if score >= 40: return "#e67e22"
    return "#e74c3c"


def cow_select(label="Select Cow", key=None):
    cows = db.get_all_cows()
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
    st.markdown('<p class="main-header">🏠 Farm Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Live overview of your herd health and production</p>', unsafe_allow_html=True)

    total_cows, today_prod, yesterday_prod, active_alerts = db.get_herd_summary()
    delta_prod = today_prod - yesterday_prod
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
        trend_df = db.get_milk_records(days=30)
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
        alerts_df = db.get_active_alerts()
        if alerts_df.empty:
            st.success("✅ No active alerts — herd looks healthy!")
        else:
            for _, alert in alerts_df.head(6).iterrows():
                cls = "alert-critical" if alert["severity"] == "critical" else "alert-warning"
                icon = "🔴" if alert["severity"] == "critical" else "🟡"
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
    today_df = db.get_milk_records(days=1)
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


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: COW MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🐄 Cow Management":
    st.markdown('<p class="main-header">🐄 Cow Management</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 All Cows", "➕ Register New Cow"])

    with tab1:
        cows_df = db.get_all_cows()
        if cows_df.empty:
            st.info("No cows registered yet.")
        else:
            # Enrich with last 7-day avg and health score
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
            cow_id, _ = cow_select("Select a cow to view", key="profile_cow")
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
                    ok, msg = db.add_cow(name, tag, breed, dob.isoformat(), lac_start.isoformat(), notes)
                if ok:
                        st.success(f"✅ {msg}")
                else:
                        st.error(f"❌ {msg}")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: LOG MILK RECORDS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🥛 Log Milk Records":
    st.markdown('<p class="main-header">🥛 Log Milk Records</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Single Cow Entry", "📦 Bulk Entry (All Cows)"])

    with tab1:
        cow_id, _ = cow_select("Select Cow", key="milk_log_cow")
        if cow_id:
            with st.form("single_milk_form"):
                col1, col2, col3 = st.columns(3)
                rec_date = col1.date_input("Date", value=date.today())
                morning = col2.number_input("Morning Yield (L)", min_value=0.0, step=0.1, format="%.1f")
                evening = col3.number_input("Evening Yield (L)", min_value=0.0, step=0.1, format="%.1f")
                notes = st.text_input("Notes (optional)")
                save = st.form_submit_button("💾 Save Record", use_container_width=True)

            if save:
                ok, msg = db.add_milk_record(cow_id, rec_date.isoformat(), morning, evening, notes)
                if ok:
                    st.success(f"✅ {msg} — Total: {morning+evening:.1f}L")
                else:
                    st.error(f"❌ {msg}")

            # Recent records
            st.divider()
            recent = db.get_milk_records(cow_id=cow_id, days=14)
            if not recent.empty:
                st.markdown("**Last 14 days:**")
                show = recent[["record_date","morning_yield","evening_yield","total_yield","notes"]].copy()
                show.columns = ["Date","Morning (L)","Evening (L)","Total (L)","Notes"]
                st.table(show.sort_values("Date", ascending=False))
                
    with tab2:
        st.markdown("Enter today's production for all cows at once.")
        bulk_date = st.date_input("Date for bulk entry", value=date.today())
        cows_df = db.get_all_cows()

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
                        ok, _ = db.add_milk_record(cid, bulk_date.isoformat(), m, e)
                        saved += 1 if ok else 0
                    else:
                        skipped += 1
                st.success(f"✅ Saved {saved} records. Skipped {skipped} zero-yield entries.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: MILK FORECASTING
# ═════════════════════════════════════════════════════════════════════════════

elif page == "📈 Milk Forecasting":
    st.markdown('<p class="main-header">📈 Milk Production Forecasting</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Uses Wood\'s Lactation Curve model to project future production</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🐄 Individual Cow", "🌐 Herd Forecast"])

    with tab1:
        cow_id, cow_label = cow_select("Select Cow", key="forecast_cow")
        days_ahead = st.slider("Forecast horizon (days)", 7, 30, 14)

        if cow_id:
            milk_df = db.get_all_milk_records_for_cow(cow_id)

            if milk_df.empty or len(milk_df) < 10:
                st.warning("Need at least 10 days of records to generate a forecast.")
            else:
                with st.spinner("Fitting lactation curve…"):
                    hist_df, forecast_df, model_info = fc.forecast_cow_production(milk_df, days_ahead)

                if forecast_df.empty:
                    st.error("Could not generate forecast for this cow.")
                else:
                    # ── Model info metrics ────────────────────────────────────
                    if "peak_yield" in model_info:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Model", model_info.get("model", "—"))
                        m2.metric("Predicted Peak Yield", f"{model_info['peak_yield']} L/day")
                        m3.metric("Peak Day (DIM)", f"Day {int(model_info['peak_dim'])}")

                    # ── Chart ─────────────────────────────────────────────────
                    fig = go.Figure()

                    # Actual historical
                    fig.add_trace(go.Scatter(
                        x=hist_df["record_date"], y=hist_df["total_yield"],
                        mode="markers",
                        marker=dict(color="#7fb3d3", size=5, opacity=0.7),
                        name="Actual Production",
                    ))

                    # Fitted curve on historical
                    if "fitted_yield" in hist_df.columns:
                        fig.add_trace(go.Scatter(
                            x=hist_df["record_date"], y=hist_df["fitted_yield"],
                            mode="lines",
                            line=dict(color="#1a5276", width=2),
                            name="Fitted Curve (Wood's Model)",
                        ))

                    # Forecast
                    fig.add_trace(go.Scatter(
                        x=forecast_df["date"], y=forecast_df["predicted_yield"],
                        mode="lines+markers",
                        line=dict(color="#e74c3c", width=2.5, dash="dot"),
                        marker=dict(size=6, color="#e74c3c"),
                        name=f"{days_ahead}-Day Forecast",
                    ))

                    # Confidence band
                    fig.add_trace(go.Scatter(
                        x=pd.concat([forecast_df["date"], forecast_df["date"][::-1]]),
                        y=pd.concat([forecast_df["upper_bound"], forecast_df["lower_bound"][::-1]]),
                        fill="toself",
                        fillcolor="rgba(231,76,60,0.12)",
                        line=dict(color="rgba(255,255,255,0)"),
                        name="Confidence Band",
                        showlegend=True,
                    ))

                    # Vertical line at today
                    fig.add_vline(
                        x=date.today().isoformat(),
                        line_dash="dash", line_color="gray",
                        annotation_text="Today",
                    )

                    fig.update_layout(
                        title=f"Production Forecast — {cow_label}",
                        xaxis_title="Date", yaxis_title="Litres / Day",
                        height=450,
                        plot_bgcolor="white",
                        yaxis=dict(gridcolor="#f0f0f0"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # ── Forecast table ────────────────────────────────────────
                    st.markdown("#### Forecast Values")
                    tbl = forecast_df[["date","predicted_yield","lower_bound","upper_bound"]].copy()
                    tbl.columns = ["Date", "Predicted (L)", "Lower Bound (L)", "Upper Bound (L)"]
                    tbl["Date"] = tbl["Date"].astype(str)
                    st.dataframe(tbl, hide_index=True, use_container_width=True)

                    total_forecast = forecast_df["predicted_yield"].sum()
                    st.info(f"📦 Estimated total production over next {days_ahead} days: **{total_forecast:.1f} L**")

    with tab2:
        st.markdown("### Herd-Level Forecast")
        h_days = st.slider("Forecast horizon (days)", 7, 30, 14, key="herd_days")

        cows_df = db.get_all_cows()
        if cows_df.empty:
            st.info("No cows found.")
        else:
            with st.spinner(f"Forecasting production for {len(cows_df)} cows…"):
                herd_df = fc.forecast_herd(cows_df, h_days)

            if herd_df.empty:
                st.warning("Not enough data to generate herd forecast.")
            else:
                total = herd_df["predicted_total"].sum()
                st.metric("Projected Total Herd Production", f"{total:.0f} L",
                          help=f"Over next {h_days} days")

                fig = go.Figure(go.Bar(
                    x=herd_df["date"],
                    y=herd_df["predicted_total"],
                    marker_color="#1a5276",
                    text=[f"{v:.0f}L" for v in herd_df["predicted_total"]],
                    textposition="outside",
                ))
                fig.update_layout(
                    title=f"Predicted Daily Herd Production — Next {h_days} Days",
                    xaxis_title="Date", yaxis_title="Total Litres",
                    height=380, plot_bgcolor="white",
                    yaxis=dict(gridcolor="#f0f0f0"),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(herd_df.rename(columns={"date":"Date","predicted_total":"Predicted Total (L)"}),
                             hide_index=True, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: HEALTH ALERTS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🚨 Health Alerts":
    st.markdown('<p class="main-header">🚨 Health Alerts & Anomaly Detection</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Statistical detection of abnormal milk production patterns</p>', unsafe_allow_html=True)

    # ── How it works expander ─────────────────────────────────────────────────
    with st.expander("ℹ️ How anomaly detection works"):
        st.markdown("""
        The system monitors each cow's daily production against three rules:

        | Rule | Trigger | Severity |
        |------|---------|----------|
        | **Z-score baseline** | Production < 1.8 std deviations below personal 14-day average | Warning |
        | **Z-score baseline** | Production < 2.5 std deviations below personal 14-day average | Critical |
        | **Sudden drop** | Today < 72% of the 3-day moving average (acute illness) | Critical |
        | **Sustained decline** | Falling production for 5+ consecutive days | Warning |

        Early detection allows treatment before major yield loss — typical mastitis, for example,
        can be detected 2–3 days before visible symptoms.
        """)

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("🔍 Run Anomaly Scan Now", type="primary", use_container_width=True):
            with st.spinner("Scanning all cows for production anomalies…"):
                anomalies = ad.run_anomaly_scan(save_alerts=True)
            if anomalies:
                st.warning(f"Found **{len(anomalies)}** anomaly event(s). Alerts saved below.")
            else:
                st.success("✅ No anomalies detected — all cows are within normal range.")

    with col2:
        if st.button("🗑️ Clear All Resolved Alerts", use_container_width=True):
            db.clear_old_resolved_alerts(days=0)
            st.success("Cleared.")

    st.divider()

    # ── Active alerts ─────────────────────────────────────────────────────────
    alerts_df = db.get_active_alerts()

    if alerts_df.empty:
        st.success("✅ No active alerts at this time.")
    else:
        st.markdown(f"### 🔔 {len(alerts_df)} Active Alert(s)")

        for _, alert in alerts_df.iterrows():
            sev = alert["severity"]
            icon = "🔴" if sev == "critical" else "🟡"
            cls = "alert-critical" if sev == "critical" else "alert-warning"

            with st.container():
                st.markdown(
                    f'<div class="{cls}">'
                    f'<b>{icon} {sev.upper()}</b> — <b>{alert["cow_name"]}</b> ({alert["tag_number"]})<br>'
                    f'{alert["message"]}<br>'
                    f'<small>📅 {alert["alert_date"]} &nbsp;|&nbsp; Type: {alert["alert_type"]}</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"✅ Mark Resolved", key=f"resolve_{alert['id']}"):
                    db.resolve_alert(int(alert["id"]))
                    st.rerun()

    st.divider()

    # ── Herd health score overview ────────────────────────────────────────────
    st.markdown("### 🩺 Herd Health Scores")
    cows_df = db.get_all_cows()
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

    # ── Per-cow anomaly detail ────────────────────────────────────────────────
    st.markdown("### 🔎 Detailed Anomaly View")
    cow_id, _ = cow_select("Inspect a specific cow", key="anomaly_cow")
    if cow_id:
        milk_df = db.get_all_milk_records_for_cow(cow_id)
        if milk_df.empty:
            st.info("No milk records for this cow.")
        else:
            analyzed = ad.detect_anomalies_for_cow(milk_df)
            recent_analyzed = analyzed.tail(60)

            fig = go.Figure()
            # Normal points
            normal = recent_analyzed[~recent_analyzed["is_anomaly"]]
            fig.add_trace(go.Scatter(
                x=normal["record_date"], y=normal["total_yield"],
                mode="markers",
                marker=dict(color="#27ae60", size=6),
                name="Normal",
            ))
            # Warning anomalies
            warns = recent_analyzed[recent_analyzed["anomaly_severity"] == "warning"]
            if not warns.empty:
                fig.add_trace(go.Scatter(
                    x=warns["record_date"], y=warns["total_yield"],
                    mode="markers",
                    marker=dict(color="#f39c12", size=10, symbol="diamond"),
                    name="Warning",
                ))
            # Critical anomalies
            crits = recent_analyzed[recent_analyzed["anomaly_severity"] == "critical"]
            if not crits.empty:
                fig.add_trace(go.Scatter(
                    x=crits["record_date"], y=crits["total_yield"],
                    mode="markers",
                    marker=dict(color="#e74c3c", size=12, symbol="x"),
                    name="Critical",
                ))
            # Rolling mean
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


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: HEALTH RECORDS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "📋 Health Records":
    st.markdown('<p class="main-header">📋 Health Records</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📖 View Records", "➕ Log New Record"])

    with tab1:
        view_mode = st.radio("View", ["All Cows", "Single Cow"], horizontal=True)

        if view_mode == "Single Cow":
            cow_id, _ = cow_select("Select Cow", key="health_view_cow")
            records = db.get_health_records(cow_id=cow_id) if cow_id else pd.DataFrame()
        else:
            records = db.get_health_records()

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
        cow_id, _ = cow_select("Cow", key="health_add_cow")
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
                )
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
