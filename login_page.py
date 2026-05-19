"""
login_page.py — DairyIQ authentication UI
"""

import streamlit as st
import auth
from datetime import date

# ── Shared CSS injected once ──────────────────────────────────────────────────
_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Page background ── */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0d2137 0%, #1B4F72 50%, #1a6b3a 100%);
    min-height: 100vh;
}
[data-testid="stHeader"] { background: transparent !important; }

/* ── Hero card ── */
.diq-hero {
    text-align: center;
    padding: 2.5rem 1rem 1rem;
}
.diq-logo {
    font-size: 5rem;
    line-height: 1;
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.4));
}
.diq-title {
    font-size: 2.4rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin: 0.6rem 0 0.2rem;
    text-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.diq-title span { color: #27AE60; }
.diq-tagline {
    font-size: 1rem;
    color: rgba(255,255,255,0.75);
    margin-bottom: 0.3rem;
}
.diq-powered {
    font-size: 0.78rem;
    color: rgba(255,255,255,0.45);
    font-style: italic;
    margin-bottom: 2rem;
}

/* ── Feature pills ── */
.diq-pills {
    display: flex;
    justify-content: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 2rem;
}
.diq-pill {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    color: #ffffff;
    padding: 0.3rem 0.85rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    backdrop-filter: blur(4px);
}

/* ── Auth card ── */
.diq-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 2.2rem 2rem 1.8rem;
    box-shadow: 0 20px 60px rgba(0,0,0,0.35);
    max-width: 460px;
    margin: 0 auto 2rem;
}
.diq-card-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1B4F72;
    margin-bottom: 1.4rem;
    padding-bottom: 0.7rem;
    border-bottom: 2px solid #F0F3F4;
}

/* ── Override Streamlit widget colours inside card ── */
div[data-testid="stForm"] .stTextInput input,
div[data-testid="stForm"] .stSelectbox select {
    border-radius: 8px !important;
    border: 1.5px solid #d0d7de !important;
    font-size: 0.92rem !important;
}
div[data-testid="stForm"] .stTextInput input:focus {
    border-color: #27AE60 !important;
    box-shadow: 0 0 0 3px rgba(39,174,96,0.15) !important;
}

/* ── Primary button → green ── */
div[data-testid="stForm"] button[kind="primaryFormSubmit"],
div[data-testid="stForm"] button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #1e8449, #27AE60) !important;
    border: none !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border-radius: 8px !important;
    padding: 0.6rem 1rem !important;
    letter-spacing: 0.3px;
    transition: opacity 0.15s;
}
div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
    opacity: 0.88 !important;
}

/* ── Footer ── */
.diq-footer {
    text-align: center;
    color: rgba(255,255,255,0.45);
    font-size: 0.72rem;
    padding: 1rem 0 1.5rem;
}

/* ── Force readable text inside Streamlit native boxes on dark page ── */
[data-testid="stNotification"],
[data-testid="stAlert"],
.stAlert > div,
[data-testid="stInfoMessage"],
[data-testid="stSuccessMessage"],
[data-testid="stWarningMessage"],
[data-testid="stErrorMessage"] {
    background: #ffffff !important;
    color: #1B2631 !important;
    border-radius: 8px !important;
}
[data-testid="stNotification"] *,
[data-testid="stAlert"] *,
.stAlert > div * {
    color: #1B2631 !important;
}

/* ── Guest description box ── */
.diq-guest-desc {
    background: #f8fdf9;
    border: 1.5px solid #27AE60;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
    color: #1B2631;
    font-size: 0.9rem;
    line-height: 1.6;
}

/* ── Radio tab labels (Login / Create Account / Continue as Guest) ── */
[data-testid="stRadio"] label,
[data-testid="stRadio"] div[role="radiogroup"] label,
[data-testid="stRadio"] p {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
}
/* Active radio dot */
[data-testid="stRadio"] input[type="radio"]:checked + div,
[data-testid="stRadio"] input[type="radio"]:checked ~ div {
    border-color: #27AE60 !important;
}
/* Highlight the selected tab label */
[data-testid="stRadio"] label:has(input:checked) p,
[data-testid="stRadio"] label:has(input:checked) {
    color: #27AE60 !important;
    text-decoration: underline;
    text-decoration-color: #27AE60;
    text-underline-offset: 3px;
}

/* ── All form field labels ── */
.stTextInput label,
.stSelectbox label,
.stDateInput label,
.stNumberInput label,
.stTextArea label,
.stCheckbox label,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* ── Helper text, captions, small hints ── */
.stTextInput [data-testid="InputInstructions"],
.stTextInput small,
.stForm small,
[data-testid="stHelperText"],
[data-testid="InputInstructions"],
div[data-testid="stMarkdownContainer"] p,
.stCaption,
small {
    color: #D5D8DC !important;
}

/* ── Input field backgrounds and typed text ── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox select,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea,
[data-baseweb="select"] div {
    background-color: #F8F9FA !important;
    color: #1B2631 !important;
    border-color: #ced4da !important;
}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #6c757d !important;
}
/* Focus ring stays green */
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #27AE60 !important;
    box-shadow: 0 0 0 3px rgba(39,174,96,0.2) !important;
    background-color: #ffffff !important;
}

/* ── Date-picker specific ── */
[data-testid="stDateInput"] input {
    background-color: #F8F9FA !important;
    color: #1B2631 !important;
}

/* ── Divider lines inside forms ── */
hr { border-color: rgba(255,255,255,0.15) !important; }

/* ── Section headers (####) rendered inside card ── */
h4 { color: #FFFFFF !important; }

/* ── Caption text (e.g. "Code sent to: email") ── */
[data-testid="stCaptionContainer"] p,
.stMarkdown caption,
caption { color: #D5D8DC !important; }
</style>
"""


def show_login_page():
    """Renders the full DairyIQ login / register UI."""

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # ── Hero banner ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="diq-hero">
        <div class="diq-logo">🐄</div>
        <div class="diq-title">Dairy<span>IQ</span></div>
        <div class="diq-tagline">
            Milk Production Intelligence System
        </div>
        <div class="diq-powered">
            Powered by Z-Score Anomaly Detection &amp; Linear Regression Forecasting
        </div>
        <div class="diq-pills">
            <span class="diq-pill">🔍 Monitor your herd</span>
            <span class="diq-pill">⚠️ Detect anomalies early</span>
            <span class="diq-pill">📈 Forecast with precision</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Mode selector ─────────────────────────────────────────────────────────
    if st.session_state.get("verified_success"):
        st.session_state["auth_mode"] = "🔑 Login"
        st.session_state.pop("verified_success", None)

    default_index = ["🔑 Login", "📝 Create Account", "👤 Continue as Guest"].index(
        st.session_state.get("auth_mode", "🔑 Login")
    )

    mode = st.radio(
        "Choose an option:",
        ["🔑 Login", "📝 Create Account", "👤 Continue as Guest"],
        horizontal=True,
        label_visibility="collapsed",
        index=default_index,
        key="auth_radio",
    )
    if mode != st.session_state.get("auth_mode"):
        st.session_state["auth_mode"] = mode

    if st.session_state.get("show_verified_msg"):
        st.success("✅ Account verified successfully! Please log in.")
        st.session_state.pop("show_verified_msg", None)

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIN
    # ══════════════════════════════════════════════════════════════════════════
    if mode == "🔑 Login":
        st.markdown('<div class="diq-card"><div class="diq-card-title">🔑 Sign in to your account</div>', unsafe_allow_html=True)

        if st.session_state.get("show_forgot"):
            _forgot_password_ui()
            st.markdown('</div>', unsafe_allow_html=True)
            return False

        with st.form("login_form"):
            email    = st.text_input("Email Address", placeholder="you@example.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit   = st.form_submit_button("Sign In →", use_container_width=True, type="primary")

        if submit:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                ok, reason, user_id = auth.login_user(email, password)
                if ok:
                    st.session_state["authenticated"] = True
                    st.session_state["user_id"]       = user_id
                    st.session_state["user_email"]    = email.lower().strip()
                    st.session_state["guest_mode"]    = False
                    st.rerun()
                elif reason == "not_found":
                    st.error("❌ No account found with that email.")
                elif reason == "wrong_password":
                    st.error("❌ Wrong credentials. Please try again.")

        if st.button("Forgot Password?", use_container_width=True):
            st.session_state["show_forgot"] = True
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # CREATE ACCOUNT
    # ══════════════════════════════════════════════════════════════════════════
    elif mode == "📝 Create Account":
        st.markdown('<div class="diq-card"><div class="diq-card-title">📝 Create a New Account</div>', unsafe_allow_html=True)

        if st.session_state.get("show_verify"):
            _verify_ui(st.session_state.get("pending_verify_email", ""))
            st.markdown('</div>', unsafe_allow_html=True)
            return False

        with st.form("register_form"):
            full_name  = st.text_input("Full Name *", placeholder="John Doe")
            dob        = st.date_input("Date of Birth *",
                                       min_value=date(1900, 1, 1),
                                       max_value=date.today(),
                                       value=date(1990, 1, 1))
            farm_name  = st.text_input("Farm Name (optional)", placeholder="e.g. Sunshine Dairy Farm")
            st.divider()
            email      = st.text_input("Email Address *", placeholder="you@example.com")
            password   = st.text_input("Password *", type="password", help="Minimum 6 characters")
            confirm    = st.text_input("Confirm Password *", type="password")
            submit     = st.form_submit_button("Create Account →", use_container_width=True, type="primary")

        # reason is always defined here so the elif chain below never raises UnboundLocalError
        reason = None
        if submit:
            today = date.today()
            age   = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            if not full_name or not email or not password or not confirm:
                st.error("All required fields must be filled.")
            elif age < 18:
                st.error("❌ You must be at least 18 years old to create an account.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                with st.spinner("Creating your account…"):
                    ok, reason = auth.register_user(email, password, full_name, dob.isoformat(), farm_name)
                if ok:
                    st.success("✅ Account created! A verification code has been sent to your email.")
                    st.session_state["pending_verify_email"] = email
                    st.session_state["show_verify"]          = True
                    st.rerun()
                elif reason == "already_exists":
                    st.error("❌ An account with this email already exists.")
                    # ── Action buttons ────────────────────────────────────────
                    st.markdown(
                        '<div style="display:flex;gap:0.6rem;margin-top:0.5rem;">'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    btn_col1, btn_col2 = st.columns(2)
                    if btn_col1.button(
                        "🔑 Go to Login",
                        use_container_width=True,
                        key="reg_goto_login",
                    ):
                        st.session_state["auth_mode"]      = "🔑 Login"
                        st.session_state["auth_radio"]     = "🔑 Login"
                        # clear any leftover register state
                        st.session_state.pop("reg_show_forgot", None)
                        st.session_state.pop("reg_reset_step",  None)
                        st.rerun()

                    if btn_col2.button(
                        "🔒 Reset Password",
                        use_container_width=True,
                        key="reg_open_forgot",
                    ):
                        st.session_state["reg_show_forgot"] = True
                        st.session_state["reg_reset_step"]  = 1
                        st.session_state["reg_reset_email"] = email
                        st.rerun()

        # ── Inline forgot-password flow (shown when triggered above) ─────────
        if st.session_state.get("reg_show_forgot"):
            st.divider()
            step  = st.session_state.get("reg_reset_step", 1)
            r_email = st.session_state.get("reg_reset_email", "")

            if step == 1:
                st.markdown("#### 🔒 Reset Your Password")
                with st.form("reg_forgot_step1"):
                    reset_email = st.text_input(
                        "Registered email address",
                        value=r_email,
                        placeholder="you@example.com",
                    )
                    send_btn = st.form_submit_button(
                        "Send Reset Code →", use_container_width=True, type="primary"
                    )
                if send_btn:
                    ok, reason_r = auth.send_reset_code(reset_email)
                    if ok:
                        st.success("✅ Reset code sent! Check your inbox.")
                        st.session_state["reg_reset_email"] = reset_email
                        st.session_state["reg_reset_step"]  = 2
                        st.rerun()
                    elif reason_r == "not_found":
                        st.error("❌ No account found with that email.")
                    else:
                        st.error("❌ Could not send email. Try again.")

            elif step == 2:
                st.markdown("#### 🔒 Enter Reset Code & New Password")
                st.caption(f"Code sent to: **{r_email}**")
                with st.form("reg_forgot_step2"):
                    r_code    = st.text_input("6-digit reset code", max_chars=6, placeholder="123456")
                    r_new     = st.text_input("New Password", type="password")
                    r_confirm = st.text_input("Confirm New Password", type="password")
                    reset_btn = st.form_submit_button(
                        "Reset Password →", use_container_width=True, type="primary"
                    )
                if reset_btn:
                    if r_new != r_confirm:
                        st.error("Passwords do not match.")
                    elif len(r_new) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        ok, reason_r = auth.reset_password(r_email, r_code, r_new)
                        if ok:
                            st.success(
                                "✅ Password reset successfully. "
                                "You can now log in with your new password."
                            )
                            # Clean up and redirect to Login tab
                            st.session_state.pop("reg_show_forgot", None)
                            st.session_state.pop("reg_reset_step",  None)
                            st.session_state.pop("reg_reset_email", None)
                            st.session_state["auth_mode"]  = "🔑 Login"
                            st.session_state["auth_radio"] = "🔑 Login"
                            st.rerun()
                        elif reason_r == "invalid_code":
                            st.error("❌ Invalid code. Please check and try again.")
                        elif reason_r == "expired":
                            st.error("❌ Code expired. Click 'Send Reset Code' again.")

            if st.button("✕ Cancel", key="reg_cancel_forgot"):
                st.session_state.pop("reg_show_forgot", None)
                st.session_state.pop("reg_reset_step",  None)
                st.session_state.pop("reg_reset_email", None)
                st.rerun()

        elif reason is not None and reason == "invalid_format":
            st.error("❌ Please enter a valid email address.")
        elif reason is not None and reason == "domain_not_found":
            st.error("❌ This email domain does not exist. Please use a real email address.")
        elif reason is not None and reason == "email_failed":
            st.error("❌ Could not send verification email. Check your internet connection.")
        elif reason is not None and reason not in (None, "ok", "already_exists"):
            st.error(f"❌ Registration failed: {reason}")

    # Also show the inline reset flow even if submit wasn't just pressed
    # (persists across reruns after the buttons are clicked)
    elif st.session_state.get("reg_show_forgot"):
        step    = st.session_state.get("reg_reset_step", 1)
        r_email = st.session_state.get("reg_reset_email", "")

        if step == 1:
            st.markdown("#### 🔒 Reset Your Password")
            with st.form("reg_forgot_step1b"):
                reset_email = st.text_input(
                    "Registered email address",
                    value=r_email,
                    placeholder="you@example.com",
                )
                send_btn = st.form_submit_button(
                    "Send Reset Code →", use_container_width=True, type="primary"
                )
            if send_btn:
                ok, reason_r = auth.send_reset_code(reset_email)
                if ok:
                    st.success("✅ Reset code sent! Check your inbox.")
                    st.session_state["reg_reset_email"] = reset_email
                    st.session_state["reg_reset_step"]  = 2
                    st.rerun()
                elif reason_r == "not_found":
                    st.error("❌ No account found with that email.")
                else:
                    st.error("❌ Could not send email. Try again.")

        elif step == 2:
            st.markdown("#### 🔒 Enter Reset Code & New Password")
            st.caption(f"Code sent to: **{r_email}**")
            with st.form("reg_forgot_step2b"):
                r_code    = st.text_input("6-digit reset code", max_chars=6, placeholder="123456")
                r_new     = st.text_input("New Password", type="password")
                r_confirm = st.text_input("Confirm New Password", type="password")
                reset_btn = st.form_submit_button(
                    "Reset Password →", use_container_width=True, type="primary"
                )
            if reset_btn:
                if r_new != r_confirm:
                    st.error("Passwords do not match.")
                elif len(r_new) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    ok, reason_r = auth.reset_password(r_email, r_code, r_new)
                    if ok:
                        st.success(
                            "✅ Password reset successfully. "
                            "You can now log in with your new password."
                        )
                        st.session_state.pop("reg_show_forgot", None)
                        st.session_state.pop("reg_reset_step",  None)
                        st.session_state.pop("reg_reset_email", None)
                        st.session_state["auth_mode"]  = "🔑 Login"
                        st.session_state["auth_radio"] = "🔑 Login"
                        st.rerun()
                    elif reason_r == "invalid_code":
                        st.error("❌ Invalid code. Please check and try again.")
                    elif reason_r == "expired":
                        st.error("❌ Code expired. Click 'Send Reset Code' again.")

        if st.button("✕ Cancel", key="reg_cancel_forgot2"):
            st.session_state.pop("reg_show_forgot", None)
            st.session_state.pop("reg_reset_step",  None)
            st.session_state.pop("reg_reset_email", None)
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # GUEST MODE
    # ══════════════════════════════════════════════════════════════════════════
    elif mode == "👤 Continue as Guest":
        st.markdown('<div class="diq-card"><div class="diq-card-title">👤 Guest Preview Mode</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="diq-guest-desc">'
            '🧪 <b>Explore DairyIQ with sample herd data — no account required.</b><br>'
            'View anomaly alerts, production trends and 30-day forecasts '
            'using a pre-loaded 6-cow dataset. Changes are <b>not</b> saved permanently.'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Enter as Guest →", use_container_width=True, type="primary"):
            import database as db
            db.initialize_db()
            st.session_state["authenticated"] = True
            st.session_state["guest_mode"]    = True
            st.session_state["user_id"]       = 0
            st.session_state["user_email"]    = "guest"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="diq-footer">DairyIQ &copy; 2026</div>',
        unsafe_allow_html=True,
    )

    return False


# ── Verification UI ───────────────────────────────────────────────────────────
def _verify_ui(email):
    st.markdown("#### ✉️ Enter Verification Code")
    st.caption(f"Code sent to: **{email}**")

    with st.form("verify_form"):
        code   = st.text_input("6-digit code", max_chars=6, placeholder="123456")
        submit = st.form_submit_button("Verify →", use_container_width=True, type="primary")

    if submit:
        ok, reason = auth.verify_email_code(email, code)
        if ok:
            # ── Auto-login: fetch user_id and set session state ──────────────
            user_id = auth.get_user_id(email)
            st.session_state["authenticated"] = True
            st.session_state["user_id"]       = user_id
            st.session_state["user_email"]    = email.lower().strip()
            st.session_state["guest_mode"]    = False
            # Clean up verification state
            st.session_state.pop("show_verify",            None)
            st.session_state.pop("pending_verify_email",   None)
            st.session_state.pop("verified_success",       None)
            st.session_state.pop("show_verified_msg",      None)
            # Brief welcome before redirect
            st.success("🎉 Account created successfully! Welcome to DairyIQ.")
            st.rerun()
        elif reason == "invalid_code":
            st.error("❌ Invalid code. Please check and try again.")
        elif reason == "expired":
            st.error("❌ Code has expired. Please register again to get a new code.")



# ── Forgot password UI ────────────────────────────────────────────────────────
def _forgot_password_ui():
    st.markdown("#### 🔒 Reset Your Password")

    step = st.session_state.get("reset_step", 1)

    if step == 1:
        with st.form("forgot_form"):
            email  = st.text_input("Your registered email", placeholder="you@example.com")
            submit = st.form_submit_button("Send Reset Code →", use_container_width=True, type="primary")

        if submit:
            ok, reason = auth.send_reset_code(email)
            if ok:
                st.success("✅ Reset code sent to your email!")
                st.session_state["reset_email"] = email
                st.session_state["reset_step"]  = 2
                st.rerun()
            elif reason == "not_found":
                st.error("❌ No account found with that email.")
            else:
                st.error("❌ Could not send email. Try again.")

    elif step == 2:
        email = st.session_state.get("reset_email", "")
        st.caption(f"Reset code sent to: **{email}**")

        with st.form("reset_form"):
            code      = st.text_input("6-digit reset code", max_chars=6)
            new_pass  = st.text_input("New Password", type="password")
            confirm   = st.text_input("Confirm New Password", type="password")
            submit    = st.form_submit_button("Reset Password →", use_container_width=True, type="primary")

        if submit:
            if new_pass != confirm:
                st.error("Passwords do not match.")
            elif len(new_pass) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, reason = auth.reset_password(email, code, new_pass)
                if ok:
                    # Auto-login — take user straight into the dashboard
                    user_id = auth.get_user_id(email)
                    st.session_state["authenticated"]      = True
                    st.session_state["user_id"]            = user_id
                    st.session_state["user_email"]         = email.lower().strip()
                    st.session_state["guest_mode"]         = False
                    # Clear all lingering auth temp state
                    st.session_state.pop("show_forgot",          None)
                    st.session_state.pop("reset_step",           None)
                    st.session_state.pop("reset_email",          None)
                    st.session_state.pop("show_verify",          None)
                    st.session_state.pop("pending_verify_email", None)
                    st.rerun()
                elif reason == "invalid_code":
                    st.error("❌ Invalid reset code.")
                elif reason == "expired":
                    st.error("❌ Code expired. Please request a new one.")

    if st.button("← Back to Login"):
        st.session_state.pop("show_forgot", None)
        st.session_state.pop("reset_step", None)
        st.rerun()
