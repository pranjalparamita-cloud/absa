"""
products.py — Product catalog (Amazon / Flipkart / Myntra) + search.
------------------------------------------------------------------
- PRODUCTS: 36 products with name, brand, platform, category,
  price, rating, image URL and description.
- search_products(): KEY-WISE PREFIX search — names starting with the
  typed letters rank first ("r" -> "re" -> "redmi"), then partial matches.
"""


def U(pid: str) -> str:
    """Build an Unsplash image URL from a photo id."""
    return f"https://images.unsplash.com/{pid}?w=600&q=80&auto=format&fit=crop"


IMAGES = {
    "camera": U("photo-1526170375885-4d8ecf77b99f"),
    "camera2": U("photo-1516035069371-29a1b244cc32"),
    "headphones": U("photo-1505740420928-5e560c06d30e"),
    "earbuds": U("photo-1590658268037-6bf12165a8df"),
    "phone": U("photo-1511707171634-5f897ff02aa9"),
    "phone2": U("photo-1598327105666-5b89351aff97"),
    "phone3": U("photo-1580910051074-3eb694886505"),
    "laptop": U("photo-1496181133206-80ce9b88a853"),
    "laptop2": U("photo-1525547719571-a2d4ac8945e2"),
    "watch": U("photo-1523275335684-37898b6baf30"),
    "smartwatch": U("photo-1579586337278-3befd40fd17a"),
    "smartwatch2": U("photo-1546868871-7041f2a55e12"),
    "shoes": U("photo-1542291026-7eec264c27ff"),
    "shoes2": U("photo-1549298916-b41d501d3772"),
    "shoes3": U("photo-1595950653106-6c9ebd614d3a"),
    "tshirt": U("photo-1521572163474-6864f9cf17ab"),
    "shirt": U("photo-1596755094514-f87e34085b2c"),
    "jacket": U("photo-1551028719-00167b16eac5"),
    "dress": U("photo-1595777457583-95e059d581b8"),
    "blazer": U("photo-1594938298603-c8148c4dae35"),
    "speaker": U("photo-1608043152269-423dbba4e7e1"),
    "keyboard": U("photo-1587829741301-dc798b83add3"),
    "mouse": U("photo-1527864550417-7fd91fc51a46"),
    "tv": U("photo-1593359677879-a4bb92f829d1"),
    "kitchen": U("photo-1585515320310-259b8a75a69b"),
    "mixer": U("photo-1570222094114-d054a817e56b"),
    "cosmetics": U("photo-1586495777744-4413f21062fa"),
    "perfume": U("photo-1541643600914-78b084683601"),
    "backpack": U("photo-1553062407-98eeb64c6a62"),
    "handbag": U("photo-1584917865442-de89df76afd3"),
    "sunglasses": U("photo-1572635196237-14b3f281503f"),
    "lamp": U("photo-1507473885765-e6ed057f782c"),
    "sofa": U("photo-1555041469-a586c61ea9bc"),
    "tablet": U("photo-1544244015-0df4b3ffc6b0"),
    "shoes_run": U("photo-1539185441755-769473a23570"),
}

# id, name, brand, platform, category, price, mrp, rating, img, desc
PRODUCTS = [
    dict(id="p101", name="Sony Cam 200D Digital Camera", brand="Sony", platform="Amazon", category="Electronics", price=42990, mrp=49990, rating=4.3, img=IMAGES["camera"], desc="20.1MP sensor, 35x optical zoom, 4K video, Wi-Fi sharing."),
    dict(id="p102", name="Redmi Note 13 Pro 5G (8GB, 256GB)", brand="Redmi", platform="Amazon", category="Electronics", price=24999, mrp=30999, rating=4.4, img=IMAGES["phone"], desc="200MP OIS camera, 120Hz AMOLED, 67W turbo charging."),
    dict(id="p103", name="Realme Narzo 70 Turbo 5G", brand="Realme", platform="Flipkart", category="Electronics", price=16999, mrp=19999, rating=4.2, img=IMAGES["phone2"], desc="Dimensity 7300, 120Hz display, 5000mAh battery."),
    dict(id="p104", name="Reebok Running Shoes - Zig Dynamic", brand="Reebok", platform="Myntra", category="Fashion", price=3499, mrp=6999, rating=4.1, img=IMAGES["shoes_run"], desc="Lightweight mesh running shoes with cushioned sole."),
    dict(id="p105", name="Sony WH-1000XM5 Noise Cancelling Headphones", brand="Sony", platform="Amazon", category="Electronics", price=26990, mrp=34990, rating=4.7, img=IMAGES["headphones"], desc="Industry-leading ANC, 30-hr battery, crystal-clear calls."),
    dict(id="p106", name="Samsung Galaxy S24 5G (8GB, 128GB)", brand="Samsung", platform="Amazon", category="Electronics", price=62999, mrp=79999, rating=4.6, img=IMAGES["phone3"], desc="Galaxy AI, 50MP OIS camera, 120Hz AMOLED 2X."),
    dict(id="p107", name="Apple MacBook Air M3 (13-inch, 8GB, 256GB)", brand="Apple", platform="Amazon", category="Electronics", price=104900, mrp=114900, rating=4.8, img=IMAGES["laptop"], desc="M3 chip, 18-hr battery, fanless silent design."),
    dict(id="p108", name="Nike Air Zoom Pegasus 40", brand="Nike", platform="Myntra", category="Fashion", price=8995, mrp=11995, rating=4.4, img=IMAGES["shoes"], desc="Responsive Zoom Air cushioning for daily runs."),
    dict(id="p109", name="Adidas Ultraboost Light Shoes", brand="Adidas", platform="Myntra", category="Fashion", price=12999, mrp=17999, rating=4.5, img=IMAGES["shoes2"], desc="BOOST midsole, Primeknit upper, all-day comfort."),
    dict(id="p110", name="boAt Airdopes 141 TWS Earbuds", brand="boAt", platform="Flipkart", category="Electronics", price=1299, mrp=4499, rating=4.0, img=IMAGES["earbuds"], desc="42H playtime, ENx mic, ASAP charge, IPX4."),
    dict(id="p111", name="HP Pavilion 15 Laptop (i5 13th Gen, 16GB)", brand="HP", platform="Amazon", category="Electronics", price=68990, mrp=79990, rating=4.3, img=IMAGES["laptop2"], desc="15.6\" FHD, backlit keyboard, fast-charge battery."),
    dict(id="p112", name="Dell Inspiron 3530 (i7, 16GB, 512GB SSD)", brand="Dell", platform="Flipkart", category="Electronics", price=74990, mrp=85990, rating=4.2, img=IMAGES["laptop"], desc="120Hz display, fingerprint reader, spill-resistant keys."),
    dict(id="p113", name="Levi's Slim Fit Denim Jacket", brand="Levi's", platform="Myntra", category="Fashion", price=2799, mrp=4999, rating=4.3, img=IMAGES["jacket"], desc="Classic trucker jacket in washed indigo denim."),
    dict(id="p114", name="Roadster Analog Leather Watch", brand="Roadster", platform="Myntra", category="Fashion", price=1499, mrp=3999, rating=4.0, img=IMAGES["watch"], desc="Minimal dial, genuine leather strap, 2-yr warranty."),
    dict(id="p115", name="Fossil Gen 6 Wellness Smartwatch", brand="Fossil", platform="Amazon", category="Electronics", price=14995, mrp=22995, rating=4.1, img=IMAGES["smartwatch"], desc="Wear OS, SpO2, heart-rate + sleep tracking."),
    dict(id="p116", name="Canon EOS 1500D DSLR Camera", brand="Canon", platform="Amazon", category="Electronics", price=41999, mrp=47999, rating=4.5, img=IMAGES["camera2"], desc="24.1MP APS-C sensor with EF-S 18-55mm lens kit."),
    dict(id="p117", name="JBL Flip 6 Bluetooth Speaker", brand="JBL", platform="Flipkart", category="Electronics", price=8999, mrp=12999, rating=4.6, img=IMAGES["speaker"], desc="Deep bass, IP67 waterproof, 12H playtime."),
    dict(id="p118", name="OnePlus 12R 5G (8GB, 128GB)", brand="OnePlus", platform="Amazon", category="Electronics", price=39999, mrp=45999, rating=4.5, img=IMAGES["phone"], desc="Snapdragon 8 Gen 2, 100W charging, Aqua Touch display."),
    dict(id="p119", name="iQOO Neo 9 Pro 5G", brand="iQOO", platform="Amazon", category="Electronics", price=35999, mrp=42999, rating=4.4, img=IMAGES["phone2"], desc="Flagship gaming phone, 144Hz LTPO AMOLED."),
    dict(id="p120", name="Vivo V30 5G (8GB, 128GB)", brand="Vivo", platform="Flipkart", category="Electronics", price=30999, mrp=35999, rating=4.2, img=IMAGES["phone3"], desc="Slim 3D-curved design, 50MP selfie camera."),
    dict(id="p121", name="Oppo Reno 11 5G", brand="Oppo", platform="Flipkart", category="Electronics", price=29999, mrp=34999, rating=4.1, img=IMAGES["phone"], desc="Portrait expert camera, 67W SUPERVOOC charging."),
    dict(id="p122", name="Noise ColorFit Pro 5 Smartwatch", brand="Noise", platform="Flipkart", category="Electronics", price=2999, mrp=7999, rating=4.0, img=IMAGES["smartwatch2"], desc="1.85\" AMOLED, BT calling, 100+ watch faces."),
    dict(id="p123", name="Philips Air Fryer HD9252 (4.1L)", brand="Philips", platform="Amazon", category="Home", price=7995, mrp=12995, rating=4.4, img=IMAGES["kitchen"], desc="Rapid Air tech, 90% less oil, 7 presets."),
    dict(id="p124", name="Prestige Iris 750W Mixer Grinder", brand="Prestige", platform="Flipkart", category="Home", price=3299, mrp=5999, rating=4.1, img=IMAGES["mixer"], desc="4 stainless jars, overload protection, 5-yr motor warranty."),
    dict(id="p125", name="Lakme Absolute Matte Lipstick Set of 4", brand="Lakme", platform="Myntra", category="Beauty", price=899, mrp=1596, rating=4.2, img=IMAGES["cosmetics"], desc="Long-stay matte shades, vitamin E enriched."),
    dict(id="p126", name="Maybelline Fit Me Foundation (Natural)", brand="Maybelline", platform="Amazon", category="Beauty", price=499, mrp=649, rating=4.3, img=IMAGES["cosmetics"], desc="12H oil-control matte finish for normal-oily skin."),
    dict(id="p127", name="Raymond Slim Fit Formal Shirt", brand="Raymond", platform="Myntra", category="Fashion", price=1399, mrp=2499, rating=4.2, img=IMAGES["shirt"], desc="Wrinkle-resistant cotton-blend office shirt."),
    dict(id="p128", name="Allen Solly Casual Blazer", brand="Allen Solly", platform="Myntra", category="Fashion", price=3999, mrp=7999, rating=4.3, img=IMAGES["blazer"], desc="Single-breasted blazer, premium poly-viscose."),
    dict(id="p129", name="Puma RS-X Reinvention Sneakers", brand="Puma", platform="Myntra", category="Fashion", price=5499, mrp=9999, rating=4.4, img=IMAGES["shoes3"], desc="Retro chunky silhouette, RS cushioning tech."),
    dict(id="p130", name="H&M Pure Cotton T-Shirt (Pack of 2)", brand="H&M", platform="Myntra", category="Fashion", price=999, mrp=1499, rating=4.1, img=IMAGES["tshirt"], desc="Breathable regular-fit tees in solid colours."),
    dict(id="p131", name="Zara Floral Summer Dress", brand="Zara", platform="Myntra", category="Fashion", price=2290, mrp=3590, rating=4.3, img=IMAGES["dress"], desc="Breezy A-line midi dress with smocked waist."),
    dict(id="p132", name="Logitech MX Master 3S Mouse", brand="Logitech", platform="Amazon", category="Electronics", price=8950, mrp=10995, rating=4.7, img=IMAGES["mouse"], desc="8K DPI track-on-glass, quiet clicks, MagSpeed wheel."),
    dict(id="p133", name="Zebronics Zeb-Max Mechanical Keyboard", brand="Zebronics", platform="Flipkart", category="Electronics", price=2499, mrp=4999, rating=4.0, img=IMAGES["keyboard"], desc="Hot-swappable blue switches, RGB, braided cable."),
    dict(id="p134", name="Mi 108cm (43\") 4K Smart TV X Series", brand="Mi", platform="Flipkart", category="Electronics", price=24999, mrp=42999, rating=4.3, img=IMAGES["tv"], desc="Dolby Vision + Atmos, PatchWall, 30W speakers."),
    dict(id="p135", name="Wildcraft 45L Travel Backpack", brand="Wildcraft", platform="Amazon", category="Fashion", price=2199, mrp=4299, rating=4.2, img=IMAGES["backpack"], desc="Water-repellent, laptop sleeve, rain cover included."),
    dict(id="p136", name="Apple iPad 10th Gen (64GB, Wi-Fi)", brand="Apple", platform="Amazon", category="Electronics", price=32900, mrp=39900, rating=4.6, img=IMAGES["tablet"], desc="10.9\" Liquid Retina, A14 chip, Touch ID."),
]

CATEGORIES = ["All"] + sorted({p["category"] for p in PRODUCTS})
PLATFORMS = sorted({p["platform"] for p in PRODUCTS})


def get_product(pid):
    for p in PRODUCTS:
        if p["id"] == pid:
            return p
    return None


def search_products(query, platforms, category, sort_by):
    """Key-wise prefix search: 'r' -> names starting with R first,
    then names merely containing the query. Re-runs as the user types."""
    q = (query or "").strip().lower()
    results = PRODUCTS
    if q:
        starts = [p for p in results if p["name"].lower().startswith(q) or p["brand"].lower().startswith(q)]
        contains = [p for p in results
                    if (q in p["name"].lower() or q in p["brand"].lower()) and p not in starts]
        results = starts + contains
    if platforms:
        results = [p for p in results if p["platform"] in platforms]
    if category and category != "All":
        results = [p for p in results if p["category"] == category]
    if sort_by == "Price: Low to High":
        results = sorted(results, key=lambda p: p["price"])
    elif sort_by == "Price: High to Low":
        results = sorted(results, key=lambda p: p["price"], reverse=True)
    elif sort_by == "Rating: High to Low":
        results = sorted(results, key=lambda p: p["rating"], reverse=True)
    return results


def stars_html(rating: float) -> str:
    """Render a 5-star string, e.g. 4.3 -> '★★★★☆'."""
    full = int(round(rating))
    return "★" * full + "☆" * (5 - full)
