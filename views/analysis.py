"""
views/analysis.py — Built-in Product Review Intelligence workspace.
------------------------------------------------------------------
The upload-first workflow has been replaced with a professional catalog:
- 5,000 searchable product-style listings across broad shopping categories
- autocomplete-style suggestions as the user searches
- 10 clearly labelled demo reviews per product, with a sentiment mix that
  varies by product (strong, average and weak items all exist in the catalog)
- aspect-based NLP dashboard and a complete review feed
"""
import html

import pandas as pd
import streamlit as st

from catalog import (catalog_categories, catalog_match_count, catalog_summary,
                     get_catalog_product, get_catalog_reviews, search_catalog)
from charts import (fig_donut, fig_bar, fig_sunburst, fig_radar,
                    fig_timeline, fig_rolling, fig_ratings)
from config import POS_COLOR, NEG_COLOR
from database import log_event, save_analysis
from nlp_engine import analyze_reviews
from ui_helpers import header, sent_badge, stars_text, money

CATALOG_NAME = "Built-in Product Catalog · generated demo data"


def _suggestions(query, limit=6):
    """Live suggestions that are actually useful.

    Without this, typing "head" returned six identical "Headlight Pair" variants
    because results were alphabetical. Candidates are now scored by where the
    match happened and then de-duplicated by product type, so one honest
    suggestion per kind of product comes back.
    """
    q = query.lower().strip()
    candidates = search_catalog(query, "All categories", limit=120)

    def score(p):
        title = p["title"].lower()
        brand = p["brand"].lower()
        ptype = p["product_type"].lower()
        if title.startswith(q):
            return 0
        if ptype.startswith(q):
            return 1
        if brand.startswith(q):
            return 2
        if q in ptype:
            return 3
        if q in brand:
            return 4
        return 5

    used_types, out = set(), []
    for product in sorted(candidates, key=lambda p: (score(p), p["title"])):
        key = product["product_type"].lower()
        if key in used_types:
            continue
        used_types.add(key)
        out.append(product)
        if len(out) >= limit:
            break
    return out


def _analyse_and_store(user, product, reviews):
    """Run the NLP once and remember the result for this product."""
    cached = st.session_state.get("catalog_analysis", {})
    if cached.get("product_id") == product["id"]:
        return cached["result"]
    result = analyze_reviews(reviews)
    st.session_state["catalog_analysis"] = {"product_id": product["id"], "result": result}
    save_analysis(user["id"], f"catalog:{product['id']}", product["title"], CATALOG_NAME,
                  result["total"], result["overall"]["positive"], result["overall"]["neutral"],
                  result["overall"]["negative"], result["verdict"])
    log_event(user, "catalog_analyse",
              f"Analysed {product['sku']} · {product['title']} → {result['verdict']}")
    return result


def _search_and_pick(user):
    """Step 1: type → suggestions appear → pick one. That is the whole interaction."""
    query = st.text_input(
        "Search a product",
        placeholder="Start typing… e.g. headphones, Samsung, air fryer, brake pad",
        key="catalog_query",
        label_visibility="collapsed",
    )

    selected_id = st.session_state.get("catalog_product_id")
    typed = (query or "").strip()

    # Nothing typed yet: show a few random products so the page is never empty
    # and a first-time visitor can click something immediately.
    if not typed:
        if not selected_id:
            picks = search_catalog("", "All categories", limit=8, offset=0)
            st.caption("Popular right now — or type above to search.")
            _pick_grid(user, picks)
        return

    suggestions = _suggestions(typed)
    if not suggestions:
        st.info(f"No product matches “{typed}”. Try one word — like “shoes”, “TV” or “Bosch”.")
        return

    st.caption(f"**{catalog_match_count(typed, 'All categories'):,}** products match “{typed}” — "
               f"pick one:")
    _pick_grid(user, suggestions, compact=True)

    # The chosen product takes over from here: analysis + reviews, automatically.
    if selected_id:
        _show_product(user, selected_id)


def _pick_grid(user, products, compact=False):
    """Clickable suggestion cards. One click = one product selected, no second button."""
    per_row = 2 if compact else 4
    for start in range(0, len(products), per_row):
        columns = st.columns(per_row)
        for index, product in enumerate(products[start:start + per_row]):
            with columns[index]:
                is_sel = st.session_state.get("catalog_product_id") == product["id"]
                if st.button(product["title"], key=f"pick_{product['id']}",
                             width="stretch", type="primary" if is_sel else "secondary"):
                    st.session_state["catalog_product_id"] = product["id"]
                    st.session_state.pop("catalog_analysis", None)
                    log_event(user, "catalog_product_view",
                              f"Opened {product['sku']} · {product['title']}")
                    st.rerun()
                st.markdown(f"<div class='suggest-meta'>{money(product.get('price'))} · "
                            f"{html.escape(product['product_type'])} · "
                            f"{product['review_count']} reviews</div>", unsafe_allow_html=True)


def _show_product(user, product_id):
    """Step 2: the product, its automatic analysis, and its reviews underneath."""
    product = get_catalog_product(product_id)
    if not product:
        st.session_state.pop("catalog_product_id", None)
        return
    reviews = get_catalog_reviews(product_id)
    average = sum(r["rating"] for r in reviews) / max(1, len(reviews))
    pos_n = sum(1 for r in reviews if r.get("seed_sentiment") == "positive")
    neu_n = sum(1 for r in reviews if r.get("seed_sentiment") == "neutral")
    neg_n = sum(1 for r in reviews if r.get("seed_sentiment") == "negative")

    st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="catalog-hero">
      <div class="hero-top">
        <div>
          <div class="gradient-title" style="font-size:1.55rem;">{html.escape(product['title'])}</div>
          <div class="subtitle" style="margin-top:4px;">
            <b>{html.escape(product['brand'])}</b> &nbsp;•&nbsp;
            {html.escape(product['product_type'])} &nbsp;•&nbsp; {money(product.get('price'))}
          </div>
        </div>
        <div class="hero-clear">✕</div>
      </div>
      <div class="review-type-line">
        <span class="review-type-chip">📝 {len(reviews)} review samples</span>
        <span class="review-type-chip pos">{pos_n} positive</span>
        <span class="review-type-chip neu">{neu_n} neutral</span>
        <span class="review-type-chip neg">{neg_n} negative</span>
        <span class="review-type-chip">⭐ {average:.1f} / 5</span>
      </div>
    </div>""", unsafe_allow_html=True)

    # The analysis runs by itself — no button to press.
    result = _analyse_and_store(user, product, reviews)
    _dashboard(result, product)
    _review_feed(reviews, result["rows"])


def _review_feed(reviews, analysed_rows=None):
    """Show every review below the product, as requested—not only a sample."""
    sentiment_by_index = {}
    if analysed_rows:
        sentiment_by_index = {index: row.get("sentiment", "neutral") for index, row in enumerate(analysed_rows)}

    st.markdown(f"### 💬 All catalog review samples ({len(reviews)})")
    st.caption("These are varied generated demonstration samples for this catalog item. "
               "The sentiment badge shows the NLP result after analysis; otherwise it shows the seeded review mix.")
    for index, review in enumerate(reviews):
        sentiment = sentiment_by_index.get(index, review.get("seed_sentiment", "neutral"))
        label = "NLP result" if analysed_rows else "Demo mix"
        review_text = html.escape(str(review["text"]))
        author = html.escape(str(review["author"]))
        date = html.escape(str(review["date"]))
        stars = stars_text(review.get("rating"))
        st.markdown(f"""<div class="review-feed">
          <b>{author}</b> <span class="small-note">• {date} • <span class="stars">{stars}</span></span>
          &nbsp;{sent_badge(sentiment)} <span class="small-note">{label}</span>
          <div class="review-feed-text">{review_text}</div>
        </div>""", unsafe_allow_html=True)


def _dashboard(result, product):
    title = html.escape(product["title"])
    st.markdown(f"### 📊 Review intelligence — {title}", unsafe_allow_html=True)
    overall = result["overall"]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">REVIEWS ANALYSED</div>
          <div class="kpi-value">{result['total']}</div><div class="kpi-sub">full product review feed</div></div>""",
                    unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">OVERALL VERDICT</div>
          <div style="font-size:1.4rem;font-weight:800;color:#6d28d9;">{result['verdict']}</div>
          <div class="kpi-sub">{result['pos_pct']:.1f}% positive reviews</div></div>""",
                    unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">POSITIVE / NEGATIVE</div>
          <div style="font-size:1.7rem;font-weight:800;"><span style="color:{POS_COLOR};">{overall['positive']}</span>
          <span style="color:#b9b3d9;"> / </span><span style="color:{NEG_COLOR};">{overall['negative']}</span></div>
          <div class="kpi-sub">{overall['neutral']} neutral reviews</div></div>""", unsafe_allow_html=True)
    with k4:
        best = max(result["aspects"], key=lambda aspect: result["aspects"][aspect]["positive"] - result["aspects"][aspect]["negative"])
        concern = min(result["aspects"], key=lambda aspect: result["aspects"][aspect]["positive"] - result["aspects"][aspect]["negative"])
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">TOP / WATCH ASPECT</div>
          <div style="font-size:1.1rem;font-weight:800;color:#047857;">👍 {best}</div>
          <div style="font-size:1rem;font-weight:700;color:#be123c;">⚠️ {concern}</div></div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_donut(overall), width="stretch")
    with c2:
        st.plotly_chart(fig_bar(result["aspects"]), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(fig_sunburst(result["aspects"], result["total"]), width="stretch")
    with c4:
        st.plotly_chart(fig_radar(result["aspects"]), width="stretch")

    dates = [row.get("date", "") for row in result["rows"]]
    sentiments = [row["sentiment"] for row in result["rows"]]
    trend = fig_timeline(dates, sentiments) if any(dates) else None
    st.plotly_chart(trend if trend else fig_rolling(sentiments), width="stretch")
    ratings = [row["rating"] for row in result["rows"] if row.get("rating") is not None]
    if ratings:
        st.plotly_chart(fig_ratings(ratings), width="stretch")

    detail = []
    for aspect, counts in result["aspects"].items():
        total = max(1, counts["positive"] + counts["neutral"] + counts["negative"])
        detail.append({"Aspect": aspect, "👍 Positive": counts["positive"], "😐 Neutral": counts["neutral"],
                       "👎 Negative": counts["negative"],
                       "Positivity %": round(counts["positive"] / total * 100, 1)})
    st.markdown("#### 🧩 Aspect detail")
    st.dataframe(pd.DataFrame(detail).sort_values("Positivity %", ascending=False),
                 width="stretch", hide_index=True)


def page_analysis():
    """One page, one path: search → suggestion → product → analysis → reviews."""
    user = st.session_state.user
    header("What do you want to check?",
           "Type a product. Pick it from the suggestions. The analysis appears immediately.")

    selected_id = st.session_state.get("catalog_product_id")
    if selected_id:
        product = get_catalog_product(selected_id)
        c1, c2 = st.columns([5, 1])
        with c2:
            if st.button("✕ Clear", width="stretch", type="secondary"):
                st.session_state.pop("catalog_product_id", None)
                st.session_state.pop("catalog_analysis", None)
                st.rerun()

    _search_and_pick(user)
