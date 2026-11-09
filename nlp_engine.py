"""
nlp_engine.py — Aspect-based sentiment analysis (pure Python, offline, free).
--------------------------------------------------------------------------------
How it works:
1. Each review is split into sentences.
2. Each sentence is scored with a negation/intensifier/hedge-aware lexicon.
   Sentences that carry no opinion word at all are skipped entirely, so
   descriptive text ("...for the electronics category") can never vote.
3. Opinion sentences are tagged with aspects via keyword matching
   (Quality, Price, Delivery, Packaging, Service, Features, Durability, Design).
4. Sentence scores are aggregated per aspect + overall, with a verdict.

Ambiguous words are handled with real context rules instead of blunt lists:
   "high"  -> negative only when the sentence is about price/cost
   "low"   -> negative only when the sentence is about quality/grade
              (a low price is a GOOD thing, so that is a positive signal)
   "small" -> negative only when the sentence is about fit/size
Words like "time", "month", "brand", "new", "working" are deliberately NOT in
the lexicon: they were dragging neutral sentences in both directions.

Also includes price_trend(): deterministic 12-month price history per product.
"""
import hashlib
import random
import re
from datetime import datetime, timedelta

# ---------- aspect keyword map ----------
ASPECT_KEYWORDS = {
    "Quality": ["quality", "premium", "material", "materials", "build", "sturdy", "finish", "finishing",
                "fabric", "genuine", "original", "duplicate", "flaw", "flaws", "scratch", "scratches",
                "plasticky", "well-made"],
    "Price": ["price", "cost", "costs", "expensive", "cheap", "cheaper", "value", "money", "affordable",
              "overpriced", "worth", "budget", "discount", "offer", "mrp", "rupee", "rupees", "pricey",
              "deal", "pricing"],
    "Delivery": ["delivery", "shipping", "arrived", "arrive", "courier", "dispatch", "dispatched",
                 "shipment", "delivered", "delay", "delayed", "tracking", "shipped", "rescheduled"],
    "Packaging": ["pack", "packed", "packing", "packaging", "package", "box", "sealed", "seal",
                  "wrap", "wrapping", "unboxing", "cushion", "bubble"],
    "Service": ["service", "support", "return", "refund", "replacement", "warranty", "seller",
                "staff", "helpful", "response", "responsive", "unresponsive", "claim", "help",
                "helpline", "customer care"],
    "Features": ["feature", "features", "battery", "camera", "display", "screen", "performance",
                 "sound", "processor", "ram", "storage", "charging", "speaker", "bluetooth",
                 "picture", "photo", "interface", "connectivity", "lag", "heats", "heating", "mic",
                 "app", "settings"],
    "Durability": ["durable", "durability", "last", "lasts", "lasting", "broke", "broken", "damaged",
                   "damage", "crack", "cracked", "fragile", "wear", "drop", "stopped", "survived",
                   "strong", "years", "months", "stopped working"],
    "Design": ["design", "look", "looks", "style", "colour", "color", "beautiful", "elegant",
               "sleek", "modern", "attractive", "appearance", "comfort", "comfortable",
               "uncomfortable", "fit", "fits", "size", "sizing", "bulky", "dull", "outdated",
               "compliment", "compliments", "finish"],
}

# ---------- sentiment lexicon ----------
POS_WORDS = {
    "good", "great", "excellent", "amazing", "awesome", "fantastic", "superb", "outstanding",
    "wonderful", "brilliant", "perfect", "love", "loved", "loves", "best", "better", "nice",
    "premium", "beautiful", "elegant", "sleek", "smooth", "smoothly", "fast", "quick", "quickly",
    "impressive", "impressed", "happy", "satisfied", "satisfying", "satisfactory", "recommend",
    "recommended", "worth", "affordable", "reasonable", "unbeatable", "sturdy", "strong", "durable",
    "genuine", "original", "flawless", "helpful", "polite", "seamless", "intuitive", "clear",
    "crisp", "sharp", "comfortable", "attractive", "modern", "compliment", "compliments",
    "exceeded", "exceeds", "incredible", "phenomenal", "stunning", "gorgeous", "classy", "neat",
    "reliable", "trustworthy", "authentic", "responsive", "easily", "easy", "efficient",
    "powerful", "lasting", "bright", "vivid", "loud", "balanced", "approved", "convenient",
    "safe", "protected", "cushioned", "prompt", "early", "superior", "value", "loving", "favourite",
    "favorite", "glad", "pleased", "pleasantly", "surprised", "conveniently", "handy", "practical",
}
NEG_WORDS = {
    "bad", "poor", "terrible", "awful", "horrible", "worst", "worse", "disappointing",
    "disappointed", "disappointment", "hate", "hated", "regret", "frustrating", "frustrated",
    "annoying", "useless", "waste", "pathetic", "nightmare", "cheap", "duplicate", "fake",
    "flaw", "flaws", "scratch", "scratches", "torn", "broken", "broke", "crack", "cracked",
    "damaged", "damage", "fragile", "stopped", "lag", "lags", "lagging", "heats", "heating",
    "drains", "drain", "slow", "late", "delay", "delayed", "rude", "rudely", "unresponsive",
    "unhelpful", "rejected", "cheated", "expensive", "overpriced", "costly", "gimmicky",
    "gimmick", "tinny", "dropping", "drops", "dull", "outdated", "bulky", "uncomfortable",
    "tight", "risky", "rattling", "rescheduled", "denied", "plasticky", "noisy", "blurry",
    "dark", "dim", "weak", "inconsistent", "defective", "faulty", "junk", "scam", "leaking",
    "loose", "mismatched", "incomplete",
}
# Words that carry no polarity on their own but DO tell us an opinion was expressed.
# They let a genuinely neutral sentence register as neutral instead of being skipped.
NEU_WORDS = {
    "fine", "okay", "ok", "average", "acceptable", "expected", "usable", "decent", "adequate",
    "standard", "ordinary", "fair", "moderate", "passable", "works", "working",
}
INTENSIFIERS = {"very", "really", "extremely", "super", "highly", "totally", "truly", "absolutely",
                "quite", "so", "too", "incredibly", "amazingly", "deeply", "completely", "utterly"}
HEDGES = {"little", "slightly", "somewhat", "bit", "fairly", "rather", "relatively", "mildly"}
# Contrast markers: "X but Y" — the clause after the conjunction is the real opinion.
CONTRAST = {"but", "although", "though", "however", "yet", "except"}
NEGATIONS = {"not", "no", "never", "neither", "nor", "none", "hardly", "barely", "without", "isnt",
             "isn't", "wasnt", "wasn't", "dont", "don't", "doesnt", "doesn't", "cant", "can't",
             "wont", "won't", "couldnt", "couldn't", "didnt", "didn't"}

# ---------- context rules for ambiguous words ----------
_PRICE_CTX = re.compile(
    r"\b(price|prices|priced|pricing|cost|costs|value|money|rupee|rupees|mrp|budget|deal|offer|"
    r"discount|expensive|cheap|affordable|worth|sale)\b", re.I)
_QUALITY_CTX = re.compile(
    r"\b(quality|grade|build|material|materials|finish|finishing|construction|made)\b", re.I)
_FIT_CTX = re.compile(r"\b(fit|fits|fitting|size|sizing|comfort|comfortable|wear)\b", re.I)

# Idioms whose polarity a word-by-word lexicon gets backwards.
# "I expected better" contains the positive word "better" but is a complaint.
NEG_PHRASES = [
    (re.compile(r"\bexpect(?:ed|ing)? (?:a bit |a little )?better\b", re.I), "disappointing"),
    (re.compile(r"\bexpect(?:ed|ing)? more\b", re.I), "disappointing"),
    (re.compile(r"\bcould be (?:much )?better\b", re.I), "disappointing"),
    (re.compile(r"\bcould be improved\b", re.I), "disappointing"),
    (re.compile(r"\bnot (?:really )?worth\b", re.I), "overpriced"),
    (re.compile(r"\bwaste of money\b", re.I), "overpriced"),
    (re.compile(r"\bno complaints?\b", re.I), "perfect"),
]


def _apply_phrases(sentence: str) -> str:
    """Rewrite known idioms into a single unambiguous word before scoring."""
    for pattern, replacement in NEG_PHRASES:
        sentence = pattern.sub(replacement, sentence)
    return sentence


def _contextual_polarity(word: str, sentence: str):
    """Return a polarity for an ambiguous word, or None to ignore it.

    'high' / 'low' / 'small' were previously hard-coded as negative, which made
    'The build quality is high' score NEGATIVE. They only mean something bad in
    a specific context, so that context is checked here.
    """
    low = sentence.lower()
    if word in ("high", "steep"):
        if _PRICE_CTX.search(low):
            return -1.0          # high price / steep price
        if _QUALITY_CTX.search(low):
            return 1.0           # high quality is good news
        return None
    if word == "low":
        if _QUALITY_CTX.search(low):
            return -1.0          # low quality / low grade
        if _PRICE_CTX.search(low):
            return 1.0           # a low price is good news
        return None
    if word in ("small", "smaller", "tight", "loose"):
        return -1.0 if _FIT_CTX.search(low) else None
    if word in ("big", "larger", "bulky"):
        return -1.0 if _FIT_CTX.search(low) else None
    return None


CONTEXT_WORDS = ("high", "steep", "low", "small", "smaller", "tight", "loose", "big", "larger", "bulky")

_ASPECT_PATTERNS = {a: re.compile(r"\b(" + "|".join(sorted(set(k.strip() for k in kws if k.strip()),
                        key=len, reverse=True)) + r")\b", re.IGNORECASE)
                    for a, kws in ASPECT_KEYWORDS.items()}


# ---------- core analysis ----------

def score_sentence(sentence: str):
    """Score one sentence -> (score, hits).

    `hits` lists every lexicon word that fired. An empty `hits` means the
    sentence expressed no opinion at all and must not vote on anything.
    """
    # Only the clause after a contrast marker carries the real opinion:
    # "The design is fine, although the price is high" -> score the price clause.
    parts = re.split(r"\b(?:but|although|though|however|yet|except)\b", sentence.lower())
    if len(parts) > 1 and any(re.search(r"[a-z]", p) for p in parts[1:]):
        sentence = parts[-1]

    sentence = _apply_phrases(sentence)
    words = re.findall(r"[a-zA-Z']+", sentence.lower())
    score = 0.0
    hits = []
    for i, w in enumerate(words):
        if w in POS_WORDS:
            val = 1.0
        elif w in NEG_WORDS:
            val = -1.0
        elif w in CONTEXT_WORDS:
            val = _contextual_polarity(w, sentence)
        elif w in NEU_WORDS:
            val = 0.0
        else:
            continue
        if val is None:          # ambiguous word with no supporting context
            continue
        hits.append(w)
        if val == 0.0:           # neutral marker: registers an opinion, scores nothing
            continue
        window = words[max(0, i - 3):i]           # look back 3 words
        if any(n in NEGATIONS for n in window):   # "not good" -> flip
            val = -val
        elif any(t in INTENSIFIERS for t in window):   # "very good" -> boost
            val *= 1.5
        elif any(h in HEDGES for h in window):         # "a little high" -> dampen
            val *= 0.25
        score += val
    return score, hits


def sentence_sentiment(sentence: str) -> str:
    """Score one sentence -> 'positive' | 'neutral' | 'negative'."""
    score, _ = score_sentence(sentence)
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
        pos = neu = neg = 0
        opinion_sentences = 0

        for sent in sentences:
            score, hits = score_sentence(sent)
            if not hits:
                # No opinion word in this sentence: it cannot vote. This is what
                # stopped descriptive filler lines from flipping whole reviews.
                continue
            opinion_sentences += 1
            label = ("positive" if score > 0.25 else "negative" if score < -0.25 else "neutral")
            if label == "positive":
                pos += 1
            elif label == "negative":
                neg += 1
            else:
                neu += 1

            matched = [a for a in aspects if _ASPECT_PATTERNS[a].search(sent)]
            if not matched:
                matched = ["Quality"] if any(w in sent.lower() for w in ("product", "item", "purchase")) else []
            for a in matched:
                aspect_data[a][label] += 1
                found_aspects.add(a)
                if len(aspect_data[a]["examples"]) < 3:
                    aspect_data[a]["examples"].append((label, sent))

        # Review-level label: whichever kind of opinion sentence dominates.
        if pos > neg:
            label = "positive"
        elif neg > pos:
            label = "negative"
        else:
            label = "neutral"   # balanced or purely neutral-language reviews read as neutral

        overall[label] += 1
        rows.append({**rev, "sentiment": label, "aspects": sorted(found_aspects) or ["General"]})

    total = max(1, len(reviews))
    pos_pct = overall["positive"] / total * 100
    if pos_pct >= 60:
        verdict = "Highly Positive"
    elif pos_pct >= 46:
        verdict = "Mostly Positive"
    elif pos_pct >= 36:
        verdict = "Mixed"
    elif pos_pct >= 25:
        verdict = "Mostly Negative"
    else:
        verdict = "Highly Negative"
    return {"overall": overall, "total": len(reviews), "pos_pct": pos_pct,
            "verdict": verdict, "aspects": aspect_data, "rows": rows}


def price_trend(product, months=12):
    """Deterministic 12-month price history (random walk + sale events)."""
    pid = product.get("id", product.get("sku", "catalog"))
    base = float(product.get("price") or 0) or 1000.0
    seed = int(hashlib.md5((str(pid) + "price").encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    labels = []
    today = datetime.now()
    for i in range(months - 1, -1, -1):
        d = today - timedelta(days=30 * i)
        labels.append(d.strftime("%b %y"))
    prices, p = [], base * 1.12
    for i in range(months):
        drift = (base - p) * 0.25
        p = max(base * 0.82, p + drift + rng.uniform(-base * 0.05, base * 0.045))
        if i in (3, 8):
            p *= rng.uniform(0.90, 0.95)  # sale events
        prices.append(round(p))
    prices[-1] = round(base)
    return labels, prices
