"""
ui_helpers.py — Reusable UI building blocks (HTML snippets).
------------------------------------------------------------
avatar_html()     user profile picture (or initial-letter fallback)
sent_badge()      coloured Positive/Neutral/Negative pill
item_card_html()  legacy compact item tile
catalog_card_html() searchable built-in catalog tile
header()          gradient page title + subtitle + divider
"""
import html
import streamlit as st

from product_visuals import catalog_image_html


def avatar_html(user, size="md"):
    cls = "avatar" if size == "md" else "avatar-sm"
    pic = (user or {}).get("profile_pic", "")
    name = (user or {}).get("username", "?")
    if pic:
        return f'<img class="{cls}" src="data:image/png;base64,{pic}"/>'
    return f'<div class="{cls} avatar-fallback">{name[:1].upper()}</div>'


def sent_badge(s):
    return f'<span class="sent-{s[:3]}">{s.capitalize()}</span>'


def stars_text(rating) -> str:
    """Render a 5-star string, e.g. 4.3 -> '★★★★☆' ('' if no rating)."""
    if rating is None:
        return ""
    try:
        full = int(round(float(rating)))
    except (TypeError, ValueError):
        return ""
    full = max(0, min(5, full))
    return "★" * full + "☆" * (5 - full)


def item_card_html(name, n_reviews, avg_rating=None):
    stars = stars_text(avg_rating) if avg_rating is not None else ""
    rating_line = (f'<div class="stars">{stars} '
                   f'<span style="color:#6d6890;">{avg_rating:.1f} / 5</span></div>'
                   if avg_rating is not None else '<div class="small-note">no ratings</div>')
    return f"""
    <div class="glass-soft" style="padding:14px; height:100%;">
      <span class="badge" style="background:#7c3aed;">{n_reviews} review{'s' if n_reviews != 1 else ''}</span>
      <div class="item-name">{name}</div>
      {rating_line}
    </div>"""


def catalog_card_html(product):
    """Professional compact catalog tile for product-search suggestions."""
    title = html.escape(str(product["title"]))
    brand = html.escape(str(product["brand"]))
    category = html.escape(str(product["category"]))
    sku = html.escape(str(product["sku"]))
    count = int(product.get("review_count", 0))
    image = catalog_image_html(product, "front", "catalog-thumb")
    return f"""
    <div class="catalog-card">
      <div class="catalog-card-top"><span class="catalog-category">{category}</span>
        <span class="catalog-sku">{sku}</span></div>
      {image}
      <div class="catalog-title">{title}</div>
      <div class="catalog-meta"><b>{brand}</b> &nbsp;•&nbsp; {count} mixed review samples</div>
    </div>"""


def header(title, subtitle):
    st.markdown(f'<div class="gradient-title">{title}</div><div class="subtitle">{subtitle}</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)
