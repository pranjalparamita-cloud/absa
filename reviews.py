"""
reviews.py — Realistic review corpus generator.
----------------------------------------------
get_product_reviews(product) builds a deterministic set of ~60 reviews
per product (seeded by product id, so results are stable across runs).
Each review mixes 1-3 aspect-specific sentences + a closing filler line,
with overall positivity derived from the product's rating.
"""
import hashlib
import random
from datetime import datetime, timedelta

REVIEWERS = ["Aarav Sharma", "Priya Verma", "Rahul Singh", "Sneha Iyer", "Arjun Mehta",
             "Kavya Nair", "Vikram Rao", "Ananya Das", "Rohan Gupta", "Ishita Bose",
             "Karan Patel", "Divya Menon", "Aditya Kumar", "Neha Joshi", "Sahil Khan"]

ASPECT_SENTENCES = {
    "Quality": {
        "pos": ["Build quality feels truly premium and sturdy.",
                "The material quality exceeded my expectations.",
                "Feels genuine and well finished, no flaws at all.",
                "Top-notch quality, totally worth the money."],
        "neg": ["Build quality feels cheap and plasticky.",
                "The material looks duplicate and low grade.",
                "Very poor finishing, found scratches on arrival.",
                "Quality is disappointing for this price."],
    },
    "Price": {
        "pos": ["Price is very reasonable for what you get.",
                "Great value for money, got it on a nice discount.",
                "Totally worth every rupee, highly affordable deal.",
                "Best in this budget segment, unbeatable offer."],
        "neg": ["Too expensive for the features offered.",
                "Not value for money at all, overpriced product.",
                "Price is high compared to competing brands.",
                "Felt cheated, MRP discount looks fake."],
    },
    "Delivery": {
        "pos": ["Delivery was super fast, arrived two days early.",
                "Quick shipping and live tracking worked perfectly.",
                "Ordered Monday, delivered by Wednesday. Impressive!",
                "Courier partner was polite and delivery was on time."],
        "neg": ["Delivery was delayed by more than a week.",
                "Shipping took forever and tracking never updated.",
                "Courier behaved rudely and rescheduled twice.",
                "Arrived late and the outer box was torn."],
    },
    "Packaging": {
        "pos": ["Packaging was excellent, fully sealed and cushioned.",
                "Neat and eco-friendly box, product was well protected.",
                "Double-layer packing kept everything safe.",
                "Premium unboxing experience, sealed pack."],
        "neg": ["Packaging was terrible, loose box with no cushion.",
                "Seal was broken when it arrived, looks used.",
                "Poor wrapping, item was rattling inside the box.",
                "No bubble wrap at all, risky packaging."],
    },
    "Service": {
        "pos": ["Customer service was very helpful with my queries.",
                "Return and replacement process was smooth and quick.",
                "Seller responded within an hour, great support.",
                "Warranty claim was approved without any hassle."],
        "neg": ["Customer service never picks up the phone.",
                "Return request was rejected without any reason.",
                "Seller is unresponsive and support is pathetic.",
                "Warranty process is a nightmare, no help received."],
    },
    "Features": {
        "pos": ["Features are amazing, battery backup lasts all day.",
                "Camera and display quality are outstanding.",
                "Performance is buttery smooth, no lag whatsoever.",
                "Sound output is rich and the interface is intuitive."],
        "neg": ["Battery drains too quickly, features feel gimmicky.",
                "Camera quality is poor in low light.",
                "Performance lags and the device heats up fast.",
                "Sound is tinny and connectivity keeps dropping."],
    },
    "Durability": {
        "pos": ["Seems very durable, survived a drop already.",
                "Using it daily for months, still looks brand new.",
                "Strong build, should easily last for years.",
                "No wear or scratches even after rough use."],
        "neg": ["Stopped working within a month, not durable.",
                "Got cracked with normal everyday use.",
                "Very fragile product, already showing damage.",
                "Broke down twice, durability is a big concern."],
    },
    "Design": {
        "pos": ["Design looks sleek and beautiful in person.",
                "Love the colour and premium elegant style.",
                "Perfect fit and super comfortable to use daily.",
                "Modern attractive look, got many compliments."],
        "neg": ["Design looks dull and outdated in real life.",
                "Colour is different from the photos shown.",
                "Fit is uncomfortable and size runs small.",
                "Looks bulky and cheap, not attractive at all."],
    },
}

FILLERS_POS = ["Overall I am quite happy with the purchase.",
               "Would definitely recommend it to others.",
               "Exceeded my expectations in most areas.",
               "Genuinely satisfied, five stars from me."]
FILLERS_NEG = ["Overall a frustrating experience for me.",
               "I would not recommend this to anyone.",
               "Expected much better at this price point.",
               "Regret buying this, quite disappointed."]
FILLERS_NEU = ["It is an okay product, does the job.",
               "Average experience, nothing special.",
               "Decent for the price, with some compromises.",
               "Neither great nor terrible, manages fine."]


def get_product_reviews(product, n=60):
    """Build a deterministic per-product review set."""
    seed = int(hashlib.md5(product["id"].encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    positivity = min(0.9, max(0.32, (product["rating"] - 3.0) / 2.0))
    aspects = list(ASPECT_SENTENCES.keys())
    reviews = []
    base_date = datetime.now()
    for _ in range(n):
        r = rng.random()
        sentiment_bias = "pos" if r < positivity else ("neg" if r < positivity + (1 - positivity) * 0.72 else "neu")
        n_aspects = rng.choice([1, 2, 2, 3])
        chosen = rng.sample(aspects, n_aspects)
        parts = []
        for a in chosen:
            pool = ASPECT_SENTENCES[a]["pos"] if sentiment_bias == "pos" else (
                ASPECT_SENTENCES[a]["neg"] if sentiment_bias == "neg"
                else (ASPECT_SENTENCES[a]["pos"] if rng.random() < 0.5 else ASPECT_SENTENCES[a]["neg"]))
            parts.append(rng.choice(pool))
        parts.append(rng.choice(FILLERS_POS if sentiment_bias == "pos" else (FILLERS_NEG if sentiment_bias == "neg" else FILLERS_NEU)))
        text = " ".join(parts)
        rating = rng.choices([5, 4, 3, 2, 1],
                             weights=[38, 30, 12, 8, 12] if sentiment_bias == "pos" else (
                                 [6, 10, 18, 30, 36] if sentiment_bias == "neg" else [10, 25, 40, 15, 10]))[0]
        reviews.append({
            "author": rng.choice(REVIEWERS),
            "rating": rating,
            "text": text,
            "date": (base_date - timedelta(days=rng.randint(0, 360))).strftime("%d %b %Y"),
            "verified": rng.random() < 0.85,
        })
    return reviews
