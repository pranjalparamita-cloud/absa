"""
views/admin.py — Admin Panel (admins only).
-------------------------------------------
Full user tracking: login times, every action, logout/leave times,
session durations, activity charts, role management, CSV exports.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from charts import style_fig
from database import fetch_df, get_conn, log_event
from ui_helpers import header


def page_admin():
    user = st.session_state.user
    if not user.get("is_admin"):
        st.error("⛔ Admins only.")
        return
    header("Admin Panel — User Tracking",
           "Monitor logins, live activity, analyses and session/leave times for every user.")
    log_event(user, "view_admin", "Opened admin panel")

    users_df = fetch_df("SELECT id,username,email,provider,is_admin,created_at,last_login FROM users ORDER BY id")
    logs_df = fetch_df("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 2000")
    hist_df = fetch_df("SELECT * FROM analysis_history ORDER BY id DESC LIMIT 2000")

    m1, m2, m3, m4 = st.columns(4)
    today = datetime.now().strftime("%Y-%m-%d")
    active_today = (int(logs_df[logs_df["timestamp"].astype(str).str.startswith(today)]["user_id"].nunique())
                    if not logs_df.empty else 0)
    for col, label, val, sub in [
        (m1, "TOTAL USERS", len(users_df), f"{int(users_df['is_admin'].sum())} admins"),
        (m2, "ACTIVE TODAY", active_today, f"{len(logs_df)} events logged"),
        (m3, "TOTAL ANALYSES", len(hist_df), "across all users"),
        (m4, "TOTAL LOGINS", int((logs_df['event_type'].isin(['login', 'google_login'])).sum()) if not logs_df.empty else 0, "email + google"),
    ]:
        col.markdown(f"""<div class="glass" style="text-align:center;">
          <div class="kpi-label">{label}</div><div class="kpi-value">{val}</div>
          <div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🕵️ Live User Tracking", "👥 Users", "📈 Analytics", "📥 Export"])

    with tab1:
        st.markdown("##### Who did what, when — including login & leave (logout) times")
        f1, f2, f3 = st.columns([1.4, 1, 1.4])
        with f1:
            q_user = st.text_input("Filter by username/email", key="adm_q")
        with f2:
            ev_types = ["All"] + sorted(logs_df["event_type"].unique().tolist()) if not logs_df.empty else ["All"]
            q_ev = st.selectbox("Event", ev_types)
        with f3:
            q_sess = st.text_input("Session ID (optional)", key="adm_s")
        view = logs_df.copy()
        if not view.empty:
            if q_user:
                view = view[view["username"].str.contains(q_user, case=False, na=False) |
                             view["email"].str.contains(q_user, case=False, na=False)]
            if q_ev != "All":
                view = view[view["event_type"] == q_ev]
            if q_sess:
                view = view[view["session_id"].str.contains(q_sess, na=False)]
        st.dataframe(view[["timestamp", "username", "email", "event_type", "detail", "session_id"]] if not view.empty else view,
                     width="stretch", hide_index=True, height=420)

        st.markdown("##### ⏱️ Session durations (login → logout/leave)")
        if not logs_df.empty:
            sess = logs_df[logs_df["event_type"].isin(["login", "google_login", "logout"])].copy()
            sess["timestamp"] = pd.to_datetime(sess["timestamp"])
            rows = []
            for (uid, uname, sid), g in sess.groupby(["user_id", "username", "session_id"]):
                g = g.sort_values("timestamp")
                start = g[g["event_type"].isin(["login", "google_login"])]["timestamp"].min()
                end = g[g["event_type"] == "logout"]["timestamp"].max()
                if pd.notna(start):
                    rows.append({"User": uname,
                                 "Login at": start.strftime("%Y-%m-%d %H:%M:%S"),
                                 "Left at": end.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(end) else "— still in / closed tab —",
                                 "Duration": str(end - start).split(".")[0] if pd.notna(end) else "—"})
            st.dataframe(pd.DataFrame(rows).tail(50), width="stretch", hide_index=True)
            st.caption("Note: clicking **Logout** records an exact leave time. If a user just closes the tab, "
                       "their last activity timestamp above is the best available leave signal.")

    with tab2:
        st.markdown("##### Registered users")
        st.dataframe(users_df, width="stretch", hide_index=True)
        st.markdown("##### Promote / demote admin")
        c_a, c_b = st.columns([2, 1])
        with c_a:
            target = st.selectbox("User email", users_df["email"].tolist() if not users_df.empty else [])
        with c_b:
            role = st.selectbox("Role", ["User", "Admin"])
        if st.button("Apply role", type="secondary"):
            if target == user["email"] and role == "User":
                st.error("You cannot demote your own account — ask another admin to do it.")
            else:
                conn = get_conn()
                conn.execute("UPDATE users SET is_admin=? WHERE email=?", (1 if role == "Admin" else 0, target))
                conn.commit()
                conn.close()
                log_event(user, "admin_action", f"Set {target} → {role}")
                st.success(f"{target} is now {role}.")
                st.rerun()

    with tab3:
        if logs_df.empty:
            st.info("No activity yet.")
        else:
            logs_df["timestamp"] = pd.to_datetime(logs_df["timestamp"])
            d1 = logs_df[logs_df["event_type"].isin(["login", "google_login"])].copy()
            g1, g2 = st.columns(2)
            # Real containers, not HTML wrappers: an unclosed <div> renders as
            # an empty box and leaves the chart outside it.
            with g1:
                with st.container(key="admin-card-logins", border=False):
                    if not d1.empty:
                        d1["day"] = d1["timestamp"].dt.strftime("%d %b")
                        fig = px.bar(d1.groupby("day").size().reset_index(name="logins"), x="day", y="logins",
                                     title="Logins per day", color_discrete_sequence=["#9333ea"])
                        st.plotly_chart(style_fig(fig, 320), width="stretch")
                    else:
                        st.info("No logins yet.")
            with g2:
                with st.container(key="admin-card-events", border=False):
                    ev = logs_df["event_type"].value_counts().reset_index()
                    ev.columns = ["event", "count"]
                    fig = px.pie(ev, names="event", values="count", hole=0.5,
                                 title="Event distribution",
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(style_fig(fig, 320), width="stretch")
            with st.container(key="admin-card-active", border=False):
                top = logs_df["username"].value_counts().head(10).reset_index()
                top.columns = ["user", "events"]
                fig = px.bar(top, x="user", y="events", title="Most active users (events)",
                             color_discrete_sequence=["#ec4899"])
                st.plotly_chart(style_fig(fig, 320), width="stretch")

    with tab4:
        st.markdown("##### Download data")
        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button("⬇️ Users CSV", users_df.to_csv(index=False).encode(),
                               "users.csv", "text/csv", type="secondary")
        with e2:
            st.download_button("⬇️ Activity logs CSV", logs_df.to_csv(index=False).encode(),
                               "activity_logs.csv", "text/csv", type="secondary")
        with e3:
            st.download_button("⬇️ Analyses CSV", hist_df.to_csv(index=False).encode(),
                               "all_analyses.csv", "text/csv", type="secondary")
