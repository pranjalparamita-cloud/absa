"""
nlp_engine.py — Aspect-based sentiment analysis (pure Python, offline, free).
--------------------------------------------------------------------------------
How it works:
1. Each review is split into sentences.
2. Each sentence is tagged with aspects via keyword matching
   (Quality, Price, Delivery, Packaging, Service, Features, Durability, Design).
3. Each sentence is scored with a negation/intensifier-aware word lexicon
   -> positive / neutral / negative.
4. Sentence scores are aggregated per aspect + overall, with a verdict.
Also includes price_trend(): deterministic 12-month price history per product.
"""
import hashlib
import random
import re
from datetime import datetime, timedelta

# ---------- aspect keyword map ----------
ASPECT_KEYWORDS = {
    "Quality": ["quality", "premium", "material", "materials", "build", "sturdy", "finish", "finishing",
                "fabric", "genuine", "original", "duplicate", "flaw", "flaws", "scratch", "scratches"],
    "Price": ["price", "cost", "expensive", "cheap", "value", "money", "affordable", "overpriced",
              "worth", "budget", "discount", "offer", "mrp", "rupee", "pricey", "deal"],
    "Delivery": ["delivery", "shipping", "arrived", "arrive", "late", "fast", "quick", "courier",
                 "dispatched", "shipment", "delivered", "delay", "delayed", "tracking", "shipped", "time"],
    "Packaging": ["pack", "packed", "packing", "packaging", "package", "box", "sealed", "seal",
                  "wrap", "wrapping", "unboxing", "cushion", "bubble"],
    "Service": ["service", "support", "return", "refund", "replacement", "warranty", "seller",
                "staff", "helpful", "response", "responsive", "unresponsive", "claim", "help"],
    "Features": ["feature", "features", "battery", "camera", "display", "screen", "performance",
                 "sound", "processor", "ram", "storage", "charging", "speaker", "bluetooth",
                 "picture", "photo", "interface", "connectivity", "lag", "heats", "mic"],
    "Durability": ["durable", "durability", "last", "lasts", "lasting", "broke", "broken", "damaged",
                   "damage", "crack", "cracked", "fragile", "scratch", "wear", "drop",
                   "working", "stopped", "survived", "strong", "years", "months"],
    "Design": ["design", "look", "looks", "style", "colour", "color", "beautiful", "elegant",
               "sleek", "modern", "attractive", "appearance", "comfort", "comfortable",
               "uncomfortable", "fit", "size", "small", "bulky", "dull", "outdated", "compliments"],
}

# ---------- sentiment lexicon ----------
POS_WORDS = {
    "good", "great", "excellent", "amazing", "awesome", "fantastic", "superb", "outstanding",
    "wonderful", "brilliant", "perfect", "love", "loved", "best", "better", "nice", "premium",
    "beautiful", "elegant", "sleek", "smooth", "fast", "quick", "impressive", "happy", "satisfied",
    "satisfactory", "recommend", "recommended", "worth", "affordable", "reasonable", "unbeatable",
    "sturdy", "strong", "durable", "genuine", "original", "flawless", "helpful", "polite",
    "seamless", "hassle", "intuitive", "rich", "buttery", "crystal", "clear", "deep", "solid",
    "comfortable", "attractive", "modern", "compliment", "compliments", "exceeded", "exceeds",
    "definitely", "genuinely", "totally", "highly", "super", "ultra", "incredible", "phenomenal",
    "stunning", "gorgeous", "classy", "neat", "safe", "protected", "cushioned", "sealed",
    "early", "time", "prompt", "reliable", "trustworthy", "authentic", "brand", "new", "fresh",
    "responsive", "smoothly", "quickly", "easily", "easy", "efficient", "powerful", "lasting",
    "long", "survived", "rough", "daily", "stars", "five", "turbo", "silent", "bright",
    "vivid", "crisp", "sharp", "loud", "balanced", "approved", "hour", "within",
}
NEG_WORDS = {
    "bad", "poor", "terrible", "awful", "horrible", "worst", "worse", "disappointing",
    "disappointed", "disappointment", "hate", "hated", "regret", "frustrating", "frustrated",
    "annoying", "useless", "waste", "pathetic", "nightmare", "cheap", "duplicate", "fake",
    "flaw", "flaws", "scratch", "scratches", "torn", "broken", "broke", "crack", "cracked",
    "damaged", "damage", "fragile", "stopped", "lag", "lags", "heats", "heating", "drains",
    "drain", "slow", "late", "delay", "delayed", "forever", "never", "rude",
    "rudely", "unresponsive", "unhelpful", "rejected", "cheated", "expensive", "overpriced",
    "high", "costly", "gimmicky", "gimmick", "tinny", "dropping", "drops", "dull", "outdated",
    "bulky", "different", "small", "uncomfortable", "loose", "risky", "rattling", "rescheduled",
    "twice", "month", "concern", "down", "denied", "reason", "phone", "picks",
    "low", "grade", "plasticky", "noisy", "blurry", "dark", "dim", "weak",
}
INTENSIFIERS = {"very", "really", "extremely", "super", "highly", "totally", "truly", "absolutely",
                "quite", "so", "too", "incredibly", "amazingly", "deeply"}
NEGATIONS = {"not", "no", "never", "neither", "nor", "none", "hardly", "barely", "without", "isnt",
             "isn't", "wasnt", "wasn't", "dont", "don't", "doesnt", "doesn't", "cant", "can't",
             "wont", "won't", "couldnt", "couldn't"}

_ASPECT_PATTERNS = {a: re.compile(r"\b(" + "|".join(sorted(set(k.strip() for k in kws if k.strip()),
                        key=len, reverse=True)) + r")\b", re.IGNORECASE)
                    for a, kws in ASPECT_KEYWORDS.items()}


# ---------- core analysis ----------

def sentence_sentiment(sentence: str) -> str:
    """Score one sentence -> 'positive' | 'neutral' | 'negative'."""
    words = re.findall(r"[a-zA-Z']+", sentence.lower())
    score = 0.0
    for i, w in enumerate(words):
        if w in POS_WORDS:
            val = 1.0
        elif w in NEG_WORDS:
            val = -1.0
        else:
            continue
        window = words[max(0, i - 3):i]          # look back 3 words
        if any(n in NEGATIONS for n in window):  # "not good" -> flip
            val = -val
        if any(t in INTENSIFIERS for t in window):  # "very good" -> boost
            val *= 1.5
        score += val
    if score > 0.25:
        return "positive"
    if score < -0.25:
        return "negative"
    return "neutral"


def analyze_reviews(reviews):
    """Analyze a list of reviews -> overall counts, per-aspect counts, verdict."""
    aspects = list(ASPECT_KEYWORDS.keys())
    aspect_data = {a: {"positive": 0, "neutral": 0, "negative": 0, "examples": []} for a in aspects}
    overall = {"positive": 0, "neutral": 0, "negative": 0}
    rows = []
    for rev in reviews:
        text = rev["text"]
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        found_aspects = set()
        scores = {"positive": 0, "neutral": 0, "negative": 0}
        for sent in sentences:
            s = sentence_sentiment(sent)
            matched = [a for a in aspects if _ASPECT_PATTERNS[a].search(sent)]
            if not matched:
                matched = ["Quality"] if any(w in sent.lower() for w in ("product", "item", "purchase")) else []
            for a in matched:
                aspect_data[a][s] += 1
                found_aspects.add(a)
                if len(aspect_data[a]["examples"]) < 3:
                    aspect_data[a]["examples"].append((s, sent))
            scores[s] += 1
        diff = scores["positive"] - scores["negative"]
        if diff >= 2:
            label = "positive"
        elif diff <= -2:
            label = "negative"
        elif scores["neutral"] > 0 or diff == 0:
            label = "neutral"  # mixed / balanced reviews read as neutral
        elif diff == 1:
            label = "positive"
        else:
            label = "negative"
        overall[label] += 1
        rows.append({**rev, "sentiment": label, "aspects": sorted(found_aspects) or ["General"]})

    total = max(1, len(reviews))
    pos_pct = overall["positive"] / total * 100
    if pos_pct >= 60:
        verdict = "Highly Positive"
    elif pos_pct >= 45:
        verdict = "Mostly Positive"
    elif pos_pct >= 35:
        verdict = "Mixed"
    elif pos_pct >= 25:
        verdict = "Mostly Negative"
    else:
        verdict = "Highly Negative"
    return {"overall": overall, "total": len(reviews), "pos_pct": pos_pct,
            "verdict": verdict, "aspects": aspect_data, "rows": rows}


def price_trend(product, months=12):
    """Deterministic 12-month price history (random walk + sale events)."""
    seed = int(hashlib.md5((product["id"] + "price").encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    labels = []
    today = datetime.now()
    for i in range(months - 1, -1, -1):
        d = today - timedelta(days=30 * i)
        labels.append(d.strftime("%b %y"))
    base = product["price"]
    prices, p = [], base * 1.12
    for i in range(months):
        drift = (base - p) * 0.25
        p = max(base * 0.82, p + drift + rng.uniform(-base * 0.05, base * 0.045))
        if i in (3, 8):
            p *= rng.uniform(0.90, 0.95)  # sale events
        prices.append(round(p))
    prices[-1] = base
    return labels, prices
