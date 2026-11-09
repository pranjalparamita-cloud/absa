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

CATALOG_VERSION = "catalog-demo-v1"
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

EDITIONS = ["Essential", "Plus", "Pro", "Smart", "Signature", "Ultra", "Everyday", "Advance", "Prime", "Select"]
COLORS = ["Graphite", "Midnight", "Silver", "Blue", "Black", "White", "Sand", "Rose", "Green", "Titanium"]
REVIEWERS = ["Aarav", "Ananya", "Rohan", "Meera", "Ishaan", "Kavya", "Arjun", "Diya", "Vihaan", "Saanvi",
             "Rahul", "Priya", "Neha", "Aditya", "Sneha", "Karan", "Riya", "Vikram", "Aisha", "Nikhil"]

POSITIVE = [
    "The build quality feels premium and sturdy. Performance has been smooth and I am very satisfied.",
    "Delivery was quick and the packaging kept everything safe. Great value for money.",
    "The design looks sleek and the useful features work very well. Definitely recommend it.",
    "Setup was easy, quality is excellent, and it has been reliable during daily use.",
    "This is a well-made product with strong performance. It exceeded my expectations for the price.",
]
NEUTRAL = [
    "It does the job as expected. The design is fine, although the price feels a little high.",
    "Packaging was acceptable and delivery was on time. Nothing exceptional, but it is usable.",
    "The features work reasonably well after setup. Quality is average for this price range.",
]
NEGATIVE = [
    "Build quality feels poor and the price is expensive. I expected better performance.",
    "Delivery was delayed and the packaging arrived damaged. The overall experience was disappointing.",
    "Performance is inconsistent and support was unhelpful. It stopped working sooner than expected.",
]


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
            rows.append((product_id, sku, title, brand, category, product_type, REVIEWS_PER_PRODUCT))
            product_id += 1
    return rows


def _review_rows(products):
    """Create 5 positive, 3 neutral and 2 negative review samples per item."""
    rows = []
    review_id = 1
    base = date(2025, 1, 5)
    for product in products:
        product_id, _, _, brand, category, product_type, _ = product
        rng = random.Random(product_id * 7919)
        entries = [("positive", 5, text) for text in POSITIVE]
        entries += [("neutral", 3, text) for text in NEUTRAL]
        entries += [("negative", rating, text) for rating, text in zip((2, 1), NEGATIVE[:2])]
        rng.shuffle(entries)
        for position, (seed_sentiment, rating, text) in enumerate(entries):
            reviewer = REVIEWERS[(product_id * 3 + position * 7) % len(REVIEWERS)]
            # Category/type context helps the review feed feel specific while
            # retaining clear aspect and sentiment language for the NLP demo.
            detail = f" {product_type} review for the {category.lower()} category."
            review_date = (base + timedelta(days=(product_id * 11 + position * 37) % 620)).isoformat()
            rows.append((review_id, product_id, reviewer, rating, text + detail, review_date, seed_sentiment))
            review_id += 1
    return rows


def ensure_catalog_seed(conn):
    """Create/rebuild the catalog only when its version or size is outdated."""
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    version_row = cur.execute("SELECT value FROM catalog_meta WHERE key='catalog_version'").fetchone()
    count = cur.execute("SELECT COUNT(*) FROM catalog_products").fetchone()[0]
    if version_row and version_row[0] == CATALOG_VERSION and count == 5000:
        return

    cur.execute("DELETE FROM catalog_reviews")
    cur.execute("DELETE FROM catalog_products")
    products = _product_rows()
    cur.executemany(
        """INSERT INTO catalog_products
           (id, sku, title, brand, category, product_type, review_count)
           VALUES (?,?,?,?,?,?,?)""", products)
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
        sql = f"""SELECT id, sku, title, brand, category, product_type, review_count
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
        sql = f"""SELECT id, sku, title, brand, category, product_type, review_count
                   FROM catalog_products {where} ORDER BY id LIMIT ? OFFSET ?"""
        params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    columns = ["id", "sku", "title", "brand", "category", "product_type", "review_count"]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def get_catalog_product(product_id):
    conn = _conn()
    row = conn.execute(
        "SELECT id, sku, title, brand, category, product_type, review_count FROM catalog_products WHERE id=?",
        (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(("id", "sku", "title", "brand", "category", "product_type", "review_count"), row))


def get_catalog_reviews(product_id):
    conn = _conn()
    rows = conn.execute(
        """SELECT reviewer AS author, rating, review_text AS text, review_date AS date, seed_sentiment
           FROM catalog_reviews WHERE product_id=? ORDER BY id""", (product_id,)).fetchall()
    conn.close()
    return [dict(zip(("author", "rating", "text", "date", "seed_sentiment"), row)) for row in rows]
