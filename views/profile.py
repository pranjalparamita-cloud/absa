"""
views/profile.py — My Account.
--------------------------------
Just the two things that matter: your name and your password.
No photo upload, no phone, no bio, no avatar upload — removed on purpose.
"""
import streamlit as st

from auth import valid_username, password_issues, verify_password, hash_password
from database import get_user_by_id, get_user_by_login, update_user, log_event, fetch_df
from ui_helpers import header


def page_profile():
    user = st.session_state.user
    header("My Account", "Change your name or your password.")

    hist = fetch_df("SELECT COUNT(*) c FROM analysis_history WHERE user_id=?", (user["id"],))
    logins = fetch_df("SELECT COUNT(*) c FROM activity_logs WHERE user_id=? AND event_type IN ('login','google_login')",
                      (user["id"],))
    st.markdown(f"""<div class="review-type-line" style="margin-bottom:16px;">
        <span class="review-type-chip">👤 {user['username']}</span>
        <span class="review-type-chip">{user['email']}</span>
        <span class="review-type-chip pos">{int(hist['c'][0]) if len(hist) else 0} analyses</span>
        <span class="review-type-chip">{int(logins['c'][0]) if len(logins) else 0} logins</span>
      </div>""", unsafe_allow_html=True)

    # ---- edit form ----
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown("##### ✏️ Edit profile")
    new_username = st.text_input("Username", value=user["username"])

    if st.button("💾 Save changes", width="stretch"):
        if not valid_username(new_username):
            st.error("Username must be 3–20 chars: letters, numbers, underscore.")
        else:
            other = get_user_by_login(new_username)
            if other and other["id"] != user["id"]:
                st.error("That username is already taken.")
            else:
                update_user(user["id"], username=new_username.strip())
                st.session_state.user = get_user_by_id(user["id"])
                log_event(st.session_state.user, "update_profile", f"Updated profile (username={new_username})")
                st.success("Profile saved!")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="glass" style="margin-top:14px;">', unsafe_allow_html=True)
    st.markdown("##### 🔑 Change password")
    if user["provider"] == "google":
        st.info("You signed in with Google — set an email password below to also enable email login.")
        old = None
    else:
        old = st.text_input("Current password", type="password")
    new1 = st.text_input("New password", type="password")
    new2 = st.text_input("Confirm new password", type="password")
    if st.button("🔐 Update password", width="stretch"):
        if old is not None and not verify_password(old or "", user["password_hash"], user["salt"]):
            st.error("Current password is incorrect.")
        elif (issues := password_issues(new1 or "")):
            st.error("New password needs " + ", ".join(issues) + ".")
        elif new1 != new2:
            st.error("New passwords do not match.")
        else:
            phash, salt = hash_password(new1)
            update_user(user["id"], password_hash=phash, salt=salt)
            st.session_state.user = get_user_by_id(user["id"])
            log_event(st.session_state.user, "change_password", "Changed password")
            st.success("Password updated!")
    st.markdown("</div>", unsafe_allow_html=True)
