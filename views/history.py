"""
views/history.py — My Analysis History screen.
Lists every product the logged-in user has analysed + CSV download.
"""
import streamlit as st

from database import fetch_df
from ui_helpers import header


def page_history():
    user = st.session_state.user
    header("My Analysis History", "Every product you have analysed, with verdicts over time.")
    df = fetch_df("""SELECT product_name AS Item, platform AS Catalog, total_reviews AS Reviews,
                            positive AS Positive, neutral AS Neutral, negative AS Negative,
                            overall AS Verdict, timestamp AS Analysed_At
                     FROM analysis_history WHERE user_id=? ORDER BY id DESC""", (user["id"],))
    if df.empty:
        st.info("No analyses yet — open **🛍️ Product Explorer**, choose a product, and analyse its reviews.")
        return
    st.dataframe(df, width="stretch", hide_index=True)
    csv = df.to_csv(index=False).encode()
    st.download_button("⬇️ Download my history (CSV)", csv, "my_analysis_history.csv", "text/csv",
                       type="secondary")
