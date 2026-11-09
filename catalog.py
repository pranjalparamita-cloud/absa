"""
catalog.py — Built-in 5,000-item product discovery catalog.
-----------------------------------------------------------
The catalog uses recognised consumer brands and product categories, while the
specific product-style listings and review samples are generated demonstration
data. They are intentionally labelled in the UI as demo data; they are NOT
represented as scraped or customer-authored reviews.

At first app launch, ensure_catalog_seed() creates:
  catalog_products  : 5,000 searchable products (500 in each of 10 categories)
  catalog_reviews   : 50,000 mixed positive / neutral / negative review samples
"""
import random
from datetime import date, timedelta

CATALOG_VERSION = "catalog-demo-v3"
REVIEWS_PER_PRODUCT = 10

# Broad, professional retail coverage. Brand/category combinations are used as
# familiar shopping cues; the resulting SKU/product-style entries are demos.
CATEGORY_SPECS = [
    ("Electronics",
     ["Samsung", "Sony", "LG", "Panasonic", "Philips", "JBL", "Bose", "Canon", "Nikon", "Xiaomi"],
     ["4K Smart TV", "Noise Cancelling Headphones", "Portable Bluetooth Speaker", "Soundbar",
      "Mirrorless Camera", "Smart Projector", "Wireless Earbuds", "Home Theatre System",
      "Digital Camera", "LED Monitor"]),
    ("Mobile Accessories",
     ["Anker", "Belkin", "Spigen", "UGREEN", "ESR", "OtterBox", "Baseus", "Portronics", "boAt", "Ambrane"],
     ["USB-C GaN Charger", "Magnetic Power Bank", "Protective Phone Case", "Tempered Glass Pack",
      "Fast Charging Cable", "Wireless Charging Stand", "Car Phone Mount", "Bluetooth Tracker",
      "Mobile Tripod", "Laptop Sleeve"]),
    ("Computers & Gaming",
     ["Dell", "HP", "Lenovo", "ASUS", "Acer", "MSI", "Logitech", "Razer", "Corsair", "SteelSeries"],
     ["Gaming Laptop", "Mechanical Keyboard", "Wireless Mouse", "27-inch Monitor", "Gaming Headset",
      "USB-C Dock", "External SSD", "Wi-Fi Router", "Webcam", "Gaming Controller"]),
    ("Home Appliances",
     ["Whirlpool", "Bosch", "Haier", "LG", "Samsung", "Philips", "Bajaj", "Kent", "Dyson", "Havells"],
     ["Air Fryer", "Water Purifier", "Robot Vacuum", "Microwave Oven", "Front Load Washer",
      "Air Purifier", "Mixer Grinder", "Coffee Maker", "Electric Kettle", "Ceiling Fan"]),
    ("Automotive Parts",
     ["Bosch", "Denso", "NGK", "Valeo", "MANN-FILTER", "SKF", "Monroe", "Gates", "Brembo", "Castrol"],
     ["Brake Pad Set", "Engine Air Filter", "Oil Filter", "Spark Plug Kit", "Wiper Blade Pair",
      "Drive Belt", "Wheel Bearing Kit", "Clutch Cable", "Fuel Pump Module", "Shock Absorber"]),
    ("Automotive Accessories",
     ["Michelin", "3M", "Garmin", "Pioneer", "JBL", "Philips", "Bosch", "Meguiar's", "Goodyear", "Turtle Wax"],
     ["Dash Camera", "Tyre Inflator", "Car Vacuum Cleaner", "Seat Cover Set", "Reverse Camera",
      "Car Stereo", "Phone Holder", "Car Care Kit", "LED Headlight Pair", "Roof Carrier"]),
    ("Home & Kitchen",
     ["Prestige", "Hawkins", "Philips", "Borosil", "Tefal", "IKEA", "Milton", "Pigeon", "Bajaj", "Kent"],
     ["Induction Cooktop", "Non-stick Cookware Set", "Storage Container Set", "Vacuum Flask",
      "Kitchen Scale", "Water Bottle Set", "Knife Set", "Clothes Drying Rack", "Table Lamp", "Food Chopper"]),
    ("Fashion & Beauty",
     ["Nike", "Adidas", "Puma", "Skechers", "Levi's", "Maybelline", "L'Oréal", "Nivea", "Dove", "Lakmé"],
     ["Running Shoes", "Everyday Backpack", "Sports T-Shirt", "Analog Watch", "Sunglasses",
      "Skin Care Set", "Hair Dryer", "Fragrance Gift Set", "Makeup Kit", "Travel Wallet"]),
    ("Sports & Outdoors",
     ["Decathlon", "Nike", "Adidas", "Puma", "Yonex", "Wilson", "Coleman", "Quechua", "Nivia", "Cosco"],
     ["Yoga Mat", "Badminton Racket", "Cricket Bat", "Camping Tent", "Trekking Backpack",
      "Fitness Tracker", "Resistance Band Set", "Football", "Cycling Helmet", "Waterproof Jacket"]),
    ("Books & Office",
     ["HP", "Canon", "Epson", "Brother", "Casio", "Faber-Castell", "Moleskine", "Parker", "Kangaro", "Classmate"],
     ["Wireless Printer", "Ink Cartridge Set", "Scientific Calculator", "Premium Notebook", "Ball Pen Set",
      "Desk Organiser", "Document Scanner", "Label Maker", "Stapler Set", "Office Chair"]),
]

# Realistic Indian retail price per product type. A soundbar and a phone holder
# cannot share the same band, so pricing is keyed to the product, not the category.
TYPE_PRICE = {
    "4K Smart TV": (18999, 129999), "Noise Cancelling Headphones": (2999, 34999),
    "Portable Bluetooth Speaker": (1499, 24999), "Soundbar": (4999, 59999),
    "Mirrorless Camera": (39999, 189999), "Smart Projector": (12999, 89999),
    "Wireless Earbuds": (1499, 24999), "Home Theatre System": (8999, 89999),
    "Digital Camera": (9999, 79999), "LED Monitor": (6999, 54999),
    "USB-C GaN Charger": (899, 4499), "Magnetic Power Bank": (999, 4999),
    "Protective Phone Case": (299, 1999), "Tempered Glass Pack": (199, 1299),
    "Fast Charging Cable": (199, 1499), "Wireless Charging Stand": (899, 3999),
    "Car Phone Mount": (399, 2499), "Bluetooth Tracker": (999, 3999),
    "Mobile Tripod": (499, 2999), "Laptop Sleeve": (499, 2999),
    "Gaming Laptop": (44999, 249999), "Mechanical Keyboard": (1999, 14999),
    "Wireless Mouse": (499, 7999), "27-inch Monitor": (9999, 44999),
    "Gaming Headset": (1499, 19999), "USB-C Dock": (1999, 19999),
    "External SSD": (2999, 24999), "Wi-Fi Router": (999, 14999),
    "Webcam": (1299, 12999), "Gaming Controller": (1499, 9999),
    "Air Fryer": (2999, 18999), "Water Purifier": (6999, 32999),
    "Robot Vacuum": (9999, 64999), "Microwave Oven": (4999, 29999),
    "Front Load Washer": (18999, 64999), "Air Purifier": (5999, 39999),
    "Mixer Grinder": (1899, 9999), "Coffee Maker": (1999, 24999),
    "Electric Kettle": (699, 4999), "Ceiling Fan": (999, 7999),
    "Brake Pad Set": (899, 7999), "Engine Air Filter": (499, 3999),
    "Oil Filter": (299, 2499), "Spark Plug Kit": (399, 3999),
    "Wiper Blade Pair": (399, 2999), "Drive Belt": (599, 4999),
    "Wheel Bearing Kit": (899, 6999), "Clutch Cable": (399, 2999),
    "Fuel Pump Module": (1999, 14999), "Shock Absorber": (1499, 12999),
    "Dash Camera": (1999, 18999), "Tyre Inflator": (899, 4999),
    "Car Vacuum Cleaner": (999, 6999), "Seat Cover Set": (1499, 12999),
    "Reverse Camera": (1299, 9999), "Car Stereo": (2999, 29999),
    "Phone Holder": (299, 1999), "Car Care Kit": (699, 4999),
    "LED Headlight Pair": (999, 8999), "Roof Carrier": (2999, 18999),
    "Induction Cooktop": (1499, 9999), "Non-stick Cookware Set": (999, 9999),
    "Storage Container Set": (399, 3999), "Vacuum Flask": (399, 2999),
    "Kitchen Scale": (399, 2499), "Water Bottle Set": (299, 2499),
    "Knife Set": (599, 6999), "Clothes Drying Rack": (699, 4999),
    "Table Lamp": (399, 3999), "Food Chopper": (299, 2499),
    "Running Shoes": (1499, 14999), "Everyday Backpack": (699, 7999),
    "Sports T-Shirt": (399, 3999), "Analog Watch": (999, 24999),
    "Sunglasses": (499, 9999), "Skin Care Set": (399, 4999),
    "Hair Dryer": (599, 7999), "Fragrance Gift Set": (799, 8999),
    "Makeup Kit": (499, 6999), "Travel Wallet": (299, 2999),
    "Yoga Mat": (399, 3999), "Badminton Racket": (699, 9999),
    "Cricket Bat": (899, 14999), "Camping Tent": (1499, 19999),
    "Trekking Backpack": (999, 14999), "Fitness Tracker": (1299, 19999),
    "Resistance Band Set": (299, 1999), "Football": (399, 3999),
    "Cycling Helmet": (899, 9999), "Waterproof Jacket": (999, 12999),
    "Wireless Printer": (5999, 34999), "Ink Cartridge Set": (499, 4999),
    "Scientific Calculator": (399, 3999), "Premium Notebook": (99, 999),
    "Ball Pen Set": (99, 999), "Desk Organiser": (299, 2999),
    "Document Scanner": (2999, 24999), "Label Maker": (1499, 9999),
    "Stapler Set": (199, 1999), "Office Chair": (2999, 29999),
}

EDITIONS = ["Essential", "Plus", "Pro", "Smart", "Signature", "Ultra", "Everyday", "Advance", "Prime", "Select"]
EDITION_MULTIPLIER = {"Essential": 0.85, "Plus": 1.0, "Pro": 1.25, "Smart": 1.1, "Signature": 1.45,
                      "Ultra": 1.6, "Everyday": 0.8, "Advance": 1.15, "Prime": 1.3, "Select": 1.05}
COLORS = ["Graphite", "Midnight", "Silver", "Blue", "Black", "White", "Sand", "Rose", "Green", "Titanium"]
REVIEWERS = ["Aarav", "Ananya", "Rohan", "Meera", "Ishaan", "Kavya", "Arjun", "Diya", "Vihaan", "Saanvi",
             "Rahul", "Priya", "Neha", "Aditya", "Sneha", "Karan", "Riya", "Vikram", "Aisha", "Nikhil"]

# ---------------------------------------------------------------------------
# Review wording.
#
# Every line below is written so a lexicon-based scorer can actually read it:
# one clear polarity, no ambiguous words doing the work. They are shuffled and
# matched into per-product mixes so the dashboard is not identical on every
# single product.
# ---------------------------------------------------------------------------
POSITIVE = [
    "The build quality feels premium and sturdy. Performance has been smooth and I am very satisfied.",
    "Delivery was quick and the packaging kept everything safe. Great value for money.",
    "The design looks sleek and the useful features work very well. Definitely recommend it.",
    "Setup was easy, quality is excellent, and it has been reliable during daily use.",
    "This is a well-made product with strong performance. It exceeded my expectations for the price.",
    "Battery life is impressive and charging is fast. Very happy with this purchase.",
    "The finish is flawless and it feels genuine, not like a duplicate. Worth every rupee.",
    "Support was helpful and the replacement arrived quickly. Excellent service overall.",
    "Excellent sound and a bright, crisp display. The picture quality is superb.",
    "Comfortable to use for hours. The size is perfect and the material feels premium.",
    "Arrived early and well cushioned. No scratches at all and everything works perfectly.",
    "Durable after months of daily use. Still strong and reliable with no wear.",
]

NEUTRAL = [
    "It does the job as expected. The design is fine, although the price is a bit high.",
    "Packaging was acceptable and delivery was on time. Nothing exceptional, but it is usable.",
    "The features work reasonably well after setup. Quality is average for this price range.",
    "It is an okay product. Performance is standard and nothing stands out.",
    "Delivery took the usual time. The box was sealed and the product is decent.",
    "Works fine for basic use. The finish is ordinary and the price is fair.",
    "The design is standard and the size is average. It is a fair deal at this price.",
    "Setup was normal. It performs as advertised, though the build feels ordinary.",
]

NEGATIVE = [
    "Build quality feels poor and the price is expensive. I expected better performance.",
    "Delivery was delayed and the packaging arrived damaged. The overall experience was disappointing.",
    "Performance is inconsistent and support was unhelpful. It stopped working sooner than expected.",
    "It arrived scratched and the box was torn. Very disappointing for the price.",
    "The material looks duplicate and low grade. Terrible finish and cheap plastic.",
    "The battery drains fast and the device heats up. Poor performance overall.",
    "The size runs small and the fit is uncomfortable. I regret buying this.",
    "The seller was rude and refused the refund. Waste of money.",
]

# (positive, neutral, negative) per product. Products are distributed across
# these patterns deterministically, so the catalog contains strong products,
# average products and genuinely weak products instead of 5,000 identical ones.
MIX_PATTERNS = [
    (7, 2, 1), (7, 3, 0), (6, 3, 1), (6, 2, 2), (5, 3, 2), (5, 4, 1),
    (4, 4, 2), (4, 3, 3), (3, 4, 3), (3, 3, 4), (2, 4, 4), (1, 4, 5),
]
POS_RATINGS = [5, 5, 4, 5, 4, 5, 4]
NEU_RATINGS = [3, 3, 4, 2]
NEG_RATINGS = [1, 2, 1, 2, 1]


def _product_rows():
    """Generate exactly 5,000 deterministic, searchable product-style rows."""
    rows = []
    product_id = 1
    for category_index, (category, brands, types) in enumerate(CATEGORY_SPECS, start=1):
        for offset in range(500):
            brand = brands[offset % len(brands)]
            product_type = types[(offset // len(brands) + offset) % len(types)]
            edition = EDITIONS[(offset // 7 + category_index) % len(EDITIONS)]
            colour = COLORS[(offset * 3 + category_index) % len(COLORS)]
            model = f"{chr(65 + (offset % 26))}{(offset // 26) + 10}{category_index}{offset % 10}"
            title = f"{brand} {product_type} {edition} {model} — {colour}"
            sku = f"AL-{category_index:02d}-{offset + 1:03d}"
            # Deterministic price inside this product type's band, scaled by edition.
            type_low, type_high = TYPE_PRICE.get(product_type, (499, 24999))
            price_rng = random.Random(product_id * 104729 + category_index)
            spread = price_rng.random() ** 1.7          # most products sit low in the band
            price = type_low + (type_high - type_low) * spread
            price = round(price * EDITION_MULTIPLIER[edition] / 10) * 10 + 9
            rows.append((product_id, sku, title, brand, category, product_type,
                         REVIEWS_PER_PRODUCT, price))
            product_id += 1
    return rows


def _review_rows(products):
    """Build a varied, deterministic sentiment mix for each product."""
    rows = []
    review_id = 1
    base = date(2025, 1, 5)
    for product in products:
        product_id, _, _, brand, category, product_type, _, _ = product
        rng = random.Random(product_id * 7919)

        pos_count, neu_count, neg_count = MIX_PATTERNS[product_id % len(MIX_PATTERNS)]

        pos_texts = rng.sample(POSITIVE, min(pos_count, len(POSITIVE)))
        neu_texts = rng.sample(NEUTRAL, min(neu_count, len(NEUTRAL)))
        neg_texts = rng.sample(NEGATIVE, min(neg_count, len(NEGATIVE)))

        entries = []
        for i, text in enumerate(pos_texts):
            entries.append(("positive", float(POS_RATINGS[i % len(POS_RATINGS)]), text))
        for i, text in enumerate(neu_texts):
            entries.append(("neutral", float(NEU_RATINGS[i % len(NEU_RATINGS)]), text))
        for i, text in enumerate(neg_texts):
            entries.append(("negative", float(NEG_RATINGS[i % len(NEG_RATINGS)]), text))

        rng.shuffle(entries)

        for position, (seed_sentiment, rating, text) in enumerate(entries):
            reviewer = REVIEWERS[(product_id * 3 + position * 7) % len(REVIEWERS)]
            # A closing tag line with zero opinion words, so it adds realism
            # without ever voting on the score.
            detail = f" — catalog item in the {category} category."
            review_date = (base + timedelta(days=(product_id * 11 + position * 37) % 620)).isoformat()
            rows.append((review_id, product_id, reviewer, rating, text + detail, review_date, seed_sentiment))
            review_id += 1
    return rows


def ensure_catalog_seed(conn):
    """Create/rebuild the catalog only when its version or size is outdated."""
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    # Migration for databases created before the price column existed.
    try:
        cur.execute("ALTER TABLE catalog_products ADD COLUMN price REAL DEFAULT 0")
    except Exception:
        pass
    version_row = cur.execute("SELECT value FROM catalog_meta WHERE key='catalog_version'").fetchone()
    count = cur.execute("SELECT COUNT(*) FROM catalog_products").fetchone()[0]
    if version_row and version_row[0] == CATALOG_VERSION and count == 5000:
        return

    cur.execute("DELETE FROM catalog_reviews")
    cur.execute("DELETE FROM catalog_products")
    products = _product_rows()
    cur.executemany(
        """INSERT INTO catalog_products
           (id, sku, title, brand, category, product_type, review_count, price)
           VALUES (?,?,?,?,?,?,?,?)""", products)
    cur.executemany(
        """INSERT INTO catalog_reviews
           (id, product_id, reviewer, rating, review_text, review_date, seed_sentiment)
           VALUES (?,?,?,?,?,?,?)""", _review_rows(products))
    cur.execute("INSERT OR REPLACE INTO catalog_meta (key, value) VALUES ('catalog_version', ?)",
                (CATALOG_VERSION,))
    conn.commit()


def _conn():
    # Local import avoids a database <-> catalog import cycle during init_db().
    from database import get_conn
    return get_conn()


def catalog_summary():
    conn = _conn()
    cur = conn.cursor()
    products = cur.execute("SELECT COUNT(*) FROM catalog_products").fetchone()[0]
    reviews = cur.execute("SELECT COUNT(*) FROM catalog_reviews").fetchone()[0]
    categories = cur.execute("SELECT COUNT(DISTINCT category) FROM catalog_products").fetchone()[0]
    conn.close()
    return {"products": products, "reviews": reviews, "categories": categories}


def catalog_categories():
    conn = _conn()
    rows = conn.execute("SELECT DISTINCT category FROM catalog_products ORDER BY category").fetchall()
    conn.close()
    return [row[0] for row in rows]


def catalog_match_count(query="", category="All categories"):
    """Count the products matching the current browse/search controls."""
    query = (query or "").strip().lower()
    conn = _conn()
    where, params = [], []
    if query:
        for term in [term for term in query.split() if term]:
            like = f"%{term}%"
            where.append("(LOWER(title) LIKE ? OR LOWER(brand) LIKE ? OR LOWER(category) LIKE ? OR LOWER(sku) LIKE ?)")
            params.extend([like, like, like, like])
    if category != "All categories":
        where.append("category=?")
        params.append(category)
    suffix = f" WHERE {' AND '.join(where)}" if where else ""
    count = conn.execute(f"SELECT COUNT(*) FROM catalog_products{suffix}", params).fetchone()[0]
    conn.close()
    return count


def search_catalog(query="", category="All categories", limit=24, offset=0):
    """Prefix-first search for title, brand, category, product type or SKU."""
    query = (query or "").strip().lower()
    conn = _conn()
    conn.row_factory = None
    if query:
        terms = [term for term in query.split() if term]
        where = []
        params = []
        for term in terms:
            like = f"%{term}%"
            where.append("(LOWER(title) LIKE ? OR LOWER(brand) LIKE ? OR LOWER(category) LIKE ? OR LOWER(sku) LIKE ?)")
            params.extend([like, like, like, like])
        if category != "All categories":
            where.append("category=?")
            params.append(category)
        prefix = f"{query}%"
        sql = f"""SELECT id, sku, title, brand, category, product_type, review_count, price
                   FROM catalog_products WHERE {' AND '.join(where)}
                   ORDER BY CASE WHEN LOWER(title) LIKE ? THEN 0
                                 WHEN LOWER(brand) LIKE ? THEN 1 ELSE 2 END,
                            title LIMIT ? OFFSET ?"""
        params.extend([prefix, prefix, limit, offset])
    else:
        params = []
        where = ""
        if category != "All categories":
            where = "WHERE category=?"
            params.append(category)
        sql = f"""SELECT id, sku, title, brand, category, product_type, review_count, price
                   FROM catalog_products {where} ORDER BY id LIMIT ? OFFSET ?"""
        params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    columns = ["id", "sku", "title", "brand", "category", "product_type", "review_count", "price"]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


_PRODUCT_COLUMNS = ("id", "sku", "title", "brand", "category", "product_type", "review_count", "price")


def get_catalog_product(product_id):
    conn = _conn()
    row = conn.execute(
        "SELECT id, sku, title, brand, category, product_type, review_count, price "
        "FROM catalog_products WHERE id=?",
        (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(_PRODUCT_COLUMNS, row))


def get_catalog_reviews(product_id):
    conn = _conn()
    rows = conn.execute(
        """SELECT reviewer AS author, rating, review_text AS text, review_date AS date, seed_sentiment
           FROM catalog_reviews WHERE product_id=? ORDER BY id""", (product_id,)).fetchall()
    conn.close()
    return [dict(zip(("author", "rating", "text", "date", "seed_sentiment"), row)) for row in rows]
