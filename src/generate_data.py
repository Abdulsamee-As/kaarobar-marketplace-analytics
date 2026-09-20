from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2026-06-30")
MIGRATION = pd.Timestamp("2025-01-01")
COURIER_SHIFT = pd.Timestamp("2025-07-01")
EXP_START, EXP_END = pd.Timestamp("2026-03-02"), pd.Timestamp("2026-04-26")
N_CUSTOMERS = 36_000

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SAMPLE_DIR = ROOT / "data" / "sample"

rng = np.random.default_rng(SEED)
N_DAYS = (END - START).days + 1


def off(date: str | pd.Timestamp) -> int:
    return (pd.Timestamp(date) - START).days


RAMADAN = [("2024-03-12", "2024-04-09"), ("2025-03-02", "2025-03-30"), ("2026-02-19", "2026-03-20")]
EID_FITR = ["2024-04-10", "2025-03-31", "2026-03-21"]
EID_ADHA = ["2024-06-17", "2025-06-07", "2026-05-27"]
MEGA_SALES = {
    "2024-08-14": ("Independence Day Sale", "AZADI14", 1.8),
    "2024-11-11": ("11.11 Mega Sale", "MEGA1111", 4.5),
    "2024-11-29": ("White Friday", "WHITEFRI", 3.2),
    "2024-12-12": ("12.12 Sale", "SALE1212", 2.6),
    "2025-08-14": ("Independence Day Sale", "AZADI14", 1.8),
    "2025-11-11": ("11.11 Mega Sale", "MEGA1111", 4.8),
    "2025-11-28": ("White Friday", "WHITEFRI", 3.4),
    "2025-12-12": ("12.12 Sale", "SALE1212", 2.8),
}
GROWTH = 0.032


def build_calendar() -> pd.DataFrame:
    days = pd.date_range(START, END, freq="D")
    n = len(days)
    months = np.arange(n) / 30.44
    seasonal = np.where(days.dayofweek >= 5, 1.08, 1.0).astype(float)
    phase = np.full(n, "normal", dtype=object)
    sale_code = np.full(n, "", dtype=object)
    congestion = np.zeros(n)

    for start, end in RAMADAN:
        s, e = off(start), off(end)
        seasonal[s:e - 9] *= 0.88
        phase[s:e - 9] = "ramadan"
        seasonal[e - 9:e + 1] *= 1.40
        phase[e - 9:e + 1] = "pre_eid"
    for d in EID_FITR + EID_ADHA:
        o = off(d)
        seasonal[o:o + 3] *= 0.55
        phase[o:o + 3] = "eid_holiday"
        congestion[max(o - 3, 0):o + 4] += 1.8
    for d in EID_ADHA:
        o = off(d)
        seasonal[o - 7:o] *= 1.10
    for d, (_, code, mult) in MEGA_SALES.items():
        o = off(d)
        seasonal[o] *= mult
        seasonal[o - 1] *= 1 + (mult - 1) * 0.3
        seasonal[o + 1] *= 1 + (mult - 1) * 0.3
        sale_code[o - 1:o + 2] = code
        phase[o] = "mega_sale"
        congestion[o:o + 8] += 2.2

    return pd.DataFrame({
        "date": days, "seasonal": seasonal, "weight": seasonal * np.exp(GROWTH * months),
        "phase": phase, "sale_code": sale_code, "congestion": congestion,
        "month_idx": months, "month": days.month,
    })


HOUR_NORMAL = np.array([1.2, .7, .4, .3, .3, .4, .7, 1.2, 2, 2.8, 3.4, 3.8,
                        4, 3.6, 3.3, 3.4, 3.8, 4.3, 4.8, 5.4, 6.2, 6.8, 6.4, 3.4])
HOUR_RAMADAN = np.array([4.5, 5, 4.2, 2.4, 1, .4, .3, .5, 1, 1.6, 2.2, 2.4,
                         2.4, 2.2, 2, 2, 2.1, 1.8, 1.2, 3.4, 6, 7.2, 7, 5.8])
HOUR_NORMAL = HOUR_NORMAL / HOUR_NORMAL.sum()
HOUR_RAMADAN = HOUR_RAMADAN / HOUR_RAMADAN.sum()

CITIES = [
    ("Karachi", "Sindh", 1, 0.24), ("Lahore", "Punjab", 1, 0.22),
    ("Islamabad", "Islamabad Capital Territory", 1, 0.09), ("Rawalpindi", "Punjab", 1, 0.07),
    ("Faisalabad", "Punjab", 2, 0.07), ("Multan", "Punjab", 2, 0.05),
    ("Peshawar", "Khyber Pakhtunkhwa", 2, 0.05), ("Hyderabad", "Sindh", 2, 0.04),
    ("Gujranwala", "Punjab", 2, 0.04), ("Sialkot", "Punjab", 2, 0.03),
    ("Quetta", "Balochistan", 3, 0.03), ("Bahawalpur", "Punjab", 3, 0.02),
    ("Sukkur", "Sindh", 3, 0.02), ("Abbottabad", "Khyber Pakhtunkhwa", 3, 0.02),
    ("Sargodha", "Punjab", 3, 0.02), ("Mardan", "Khyber Pakhtunkhwa", 3, 0.01),
]
CITY_NAMES = [c[0] for c in CITIES]
CITY_TIER = np.array([c[2] for c in CITIES])
CITY_VARIANTS = {
    "Karachi": ["karachi", "KARACHI", "Karachi ", "KHI", "Karachi, Sindh"],
    "Lahore": ["lahore", "LAHORE", " Lahore", "LHR", "Lahore Cantt"],
    "Islamabad": ["islamabad", "ISB", "Islamabad ", "Islamabad Capital Territory"],
    "Rawalpindi": ["rawalpindi", "Pindi", "RWP", "Rawalpindi Cantt"],
    "Faisalabad": ["faisalabad", "FSD", "Faisalabad "],
    "Multan": ["multan", "MULTAN"],
    "Peshawar": ["peshawar", "PESHAWAR", "Pesh"],
    "Hyderabad": ["hyderabad", "Hyderabad, Sindh", "HYD"],
    "Gujranwala": ["gujranwala", "GRW"],
    "Sialkot": ["sialkot", "SKT"],
    "Quetta": ["quetta", "QUETTA"],
    "Bahawalpur": ["bahawalpur", "BWP"],
    "Sukkur": ["sukkur"],
    "Abbottabad": ["abbottabad", "Abbotabad"],
    "Sargodha": ["sargodha"],
    "Mardan": ["mardan"],
}


def dirty_city(city: str, p_variant: float = 0.09, p_blank: float = 0.008) -> str:
    r = rng.random()
    if r < p_blank:
        return ""
    if r < p_blank + p_variant:
        options = CITY_VARIANTS[city]
        return options[int(rng.integers(len(options)))]
    return city


CATEGORIES = {
    "Fashion": (0.24, 0.13, 0.55, ["Noor Threads", "Resham Loom", "Chaman Wear", "Saaya", "Zari Studio"], [
        ("Women's Unstitched Lawn", 2200, 7500, ["3-Piece Lawn Suit", "Printed Lawn 2-Piece", "Embroidered Lawn Suit"]),
        ("Men's Kurta", 1800, 5500, ["Cotton Kurta", "Kurta Shalwar Set", "Wash & Wear Suit"]),
        ("Kids Clothing", 900, 3200, ["Kids Kurta", "Kids Frock", "Kids T-Shirt Pack"])]),
    "Footwear": (0.08, 0.10, 0.58, ["Qadam", "Pairwise", "Stride Works"], [
        ("Men's Footwear", 2500, 9000, ["Peshawari Chappal", "Leather Loafers", "Running Shoes"]),
        ("Women's Footwear", 1800, 7000, ["Khussa", "Heeled Sandals", "Flat Slippers"])]),
    "Electronics": (0.10, 0.05, 0.82, ["Voltix", "Nexivo", "Sonora"], [
        ("Smartphones", 28000, 120000, ["Smartphone 128GB", "Smartphone 256GB"]),
        ("Audio", 2500, 18000, ["Wireless Earbuds", "Bluetooth Speaker", "Over-Ear Headphones"]),
        ("Home Appliances", 6000, 60000, ["Air Fryer 4L", "Room Heater", "Inverter Fan", "Steam Iron"])]),
    "Mobile Accessories": (0.14, 0.06, 0.45, ["ChargeUp", "Armor Case", "Voltix"], [
        ("Chargers & Cables", 500, 3500, ["Fast Charger 25W", "USB-C Cable", "Power Bank 10000mAh"]),
        ("Cases & Protection", 400, 2000, ["Phone Case", "Tempered Glass"])]),
    "Home & Kitchen": (0.16, 0.04, 0.60, ["Ghar Craft", "Handi Home", "Qila Cookware"], [
        ("Cookware", 1500, 12000, ["Non-Stick Pan Set", "Pressure Cooker", "Knife Set"]),
        ("Bedding", 2000, 14000, ["Bedsheet Set", "Winter Quilt", "Cushion Covers"]),
        ("Storage", 700, 4000, ["Storage Box Set", "Spice Rack"])]),
    "Beauty & Personal Care": (0.12, 0.03, 0.50, ["Gulaab Naturals", "Saaf Skin", "Itr House"], [
        ("Skincare", 600, 4500, ["Face Wash", "Sunblock SPF 50", "Vitamin C Serum"]),
        ("Haircare", 500, 3000, ["Herbal Shampoo", "Hair Oil"]),
        ("Fragrance", 1500, 9000, ["Attar", "Eau de Parfum"])]),
    "Grocery": (0.10, 0.01, 0.78, ["Kheti Fresh", "Chai Point", "Daal Mandi"], [
        ("Staples", 450, 3500, ["Basmati Rice 5kg", "Cooking Oil 5L", "Atta 10kg"]),
        ("Beverages", 300, 1800, ["Green Tea 50 Bags", "Tea 950g", "Juice Pack"])]),
    "Baby & Toys": (0.06, 0.04, 0.55, ["Nanha", "Khilona Lab"], [
        ("Baby Care", 800, 6000, ["Diapers Jumbo Pack", "Baby Wipes Pack", "Feeding Bottle Set"]),
        ("Toys", 900, 7000, ["Building Blocks", "RC Car", "Educational Puzzle"])]),
}
CAT_NAMES = list(CATEGORIES)
CAT_SHARE = np.array([CATEGORIES[c][0] for c in CAT_NAMES])
CAT_RETURN = np.array([CATEGORIES[c][1] for c in CAT_NAMES])
CAT_IDX = {c: i for i, c in enumerate(CAT_NAMES)}
CATEGORY_VARIANTS = {
    "Home & Kitchen": ["Home and Kitchen", "home & kitchen"],
    "Beauty & Personal Care": ["Beauty and Personal Care", "beauty & personal care"],
    "Mobile Accessories": ["Mobile accessories", "MOBILE ACCESSORIES"],
    "Fashion": ["fashion", "Fashion "],
    "Electronics": ["electronics", "Electronics "],
    "Footwear": ["footwear"], "Grocery": ["grocery"], "Baby & Toys": ["Baby and Toys"],
}


def phase_category_multiplier(phase: str, month: int) -> np.ndarray:
    m = np.ones(len(CAT_NAMES))
    if phase == "pre_eid":
        m[CAT_IDX["Fashion"]] *= 2.3
        m[CAT_IDX["Footwear"]] *= 1.9
        m[CAT_IDX["Beauty & Personal Care"]] *= 1.3
    elif phase == "ramadan":
        m[CAT_IDX["Grocery"]] *= 1.6
    elif phase == "mega_sale":
        m[CAT_IDX["Electronics"]] *= 2.2
        m[CAT_IDX["Mobile Accessories"]] *= 1.5
        m[CAT_IDX["Home & Kitchen"]] *= 1.2
    if month in (11, 12, 1):
        m[CAT_IDX["Home & Kitchen"]] *= 1.2
    return m


def price_point(low: float, high: float) -> int:
    raw = np.exp(rng.uniform(np.log(low), np.log(high)))
    step = 100 if raw > 2000 else 50
    return int(max(step, round(raw / step) * step) - 1)


SELLER_PREFIX = ["Al-Noor", "Madina", "Crescent", "Indus", "Ravi", "Chenab", "Margalla", "Saddar",
                 "Anarkali", "Liberty", "Clifton", "Gulberg", "Johar", "Hayat", "Barkat", "Rehmat",
                 "Mehran", "Kohinoor", "Sitara", "Bolan"]
SELLER_SUFFIX = ["Traders", "Collection", "Mart", "Store", "Emporium", "Enterprises", "Outlet"]
SELLER_CITY_P = np.array([.3, .3, .08, .05, .08, .04, .04, .03, .03, .03, .01, .005, .005, .005, .005, 0])
SELLER_CITY_P = SELLER_CITY_P / SELLER_CITY_P.sum()


def make_catalog():
    sellers, products = [], []
    seller_cat, seller_id = [], 0
    for cat in CAT_NAMES:
        n_sellers = max(6, int(140 * CATEGORIES[cat][0]))
        for _ in range(n_sellers):
            seller_id += 1
            name = f"{SELLER_PREFIX[int(rng.integers(len(SELLER_PREFIX)))]} {SELLER_SUFFIX[int(rng.integers(len(SELLER_SUFFIX)))]}"
            city = CITY_NAMES[int(rng.choice(len(CITIES), p=SELLER_CITY_P))]
            joined = START - pd.Timedelta(days=int(rng.integers(0, 900))) + pd.Timedelta(days=int(rng.integers(0, 500)))
            sellers.append({
                "seller_id": f"S{seller_id:04d}",
                "seller_name": name,
                "seller_city": city,
                "joined_date": joined.strftime("%Y-%m-%d"),
                "seller_type": "Official Store" if rng.random() < 0.18 else "Marketplace Seller",
            })
            seller_cat.append(cat)
    seller_cat = np.array(seller_cat)
    risky_pool = np.where(np.isin(seller_cat, ["Fashion", "Electronics", "Footwear"]))[0]
    bad_sellers = set(rng.choice(risky_pool, size=5, replace=False).tolist())

    product_id = 0
    cat_products, cat_pop = {}, {}
    for cat in CAT_NAMES:
        share, _, cost_ratio, brands, subs = CATEGORIES[cat]
        n_products = int(640 * share)
        cat_sellers = np.where(seller_cat == cat)[0]
        idxs = []
        for _ in range(n_products):
            sub, low, high, templates = subs[int(rng.integers(len(subs)))]
            brand = brands[int(rng.integers(len(brands)))]
            price = price_point(low, high)
            s_idx = int(rng.choice(cat_sellers))
            category_label = cat
            if rng.random() < 0.04:
                variants = CATEGORY_VARIANTS[cat]
                category_label = variants[int(rng.integers(len(variants)))]
            products.append({
                "product_id": f"P{product_id + 1:05d}",
                "product_name": f"{brand} {templates[int(rng.integers(len(templates)))]}",
                "category": category_label,
                "subcategory": sub,
                "brand": brand,
                "seller_id": f"S{s_idx + 1:04d}",
                "list_price": price,
                "unit_cost": int(round(price * cost_ratio * rng.uniform(0.9, 1.1))),
                "_cat": CAT_IDX[cat],
                "_bad_seller": s_idx in bad_sellers,
            })
            idxs.append(product_id)
            product_id += 1
        ranks = rng.permutation(len(idxs)) + 1
        pop = 1 / ranks ** 0.9
        cat_products[CAT_IDX[cat]] = np.array(idxs)
        cat_pop[CAT_IDX[cat]] = pop / pop.sum()
    return pd.DataFrame(sellers), pd.DataFrame(products), cat_products, cat_pop


FIRST = ["ali", "ahmed", "hassan", "usman", "bilal", "hamza", "saad", "zain", "omar", "faisal",
         "ayesha", "fatima", "zainab", "maryam", "hira", "sana", "amna", "iqra", "mahnoor", "khadija",
         "abdullah", "ibrahim", "haris", "danish", "noor", "sara", "rabia", "areeba", "asad", "taimoor"]
LAST = ["khan", "ahmed", "ali", "malik", "sheikh", "qureshi", "butt", "chaudhry", "raza", "siddiqui",
        "hussain", "iqbal", "akhtar", "javed", "shah", "mirza", "abbasi", "baig", "rana", "awan"]
CHANNELS = ["Organic Search", "Paid Social", "App Store", "Direct", "Referral", "Influencer"]
CHANNEL_P_NORMAL = [0.22, 0.24, 0.20, 0.13, 0.11, 0.10]
CHANNEL_P_SALE = [0.14, 0.40, 0.16, 0.07, 0.05, 0.18]
CHANNEL_VARIANTS = {"Paid Social": ["paid social", "Facebook Ads", "Instagram Ads"],
                    "Organic Search": ["organic", "Google Organic"], "App Store": ["app_store"]}
DEVICES = ["Android", "iOS", "Desktop"]
DEVICE_P = {1: [0.55, 0.20, 0.25], 2: [0.68, 0.10, 0.22], 3: [0.80, 0.05, 0.15]}


def make_customers(cal: pd.DataFrame) -> pd.DataFrame:
    w = cal.weight.to_numpy().copy()
    w[cal.phase.eq("mega_sale").to_numpy()] *= 1.6
    day = np.sort(rng.choice(len(cal), size=N_CUSTOMERS, p=w / w.sum()))
    months = cal.month_idx.to_numpy()[day]
    on_sale = cal.sale_code.to_numpy()[day] != ""

    base = np.array([c[3] for c in CITIES])
    growth = np.select([CITY_TIER == 1, CITY_TIER == 2], [0.0, 0.35], 0.9)
    city = np.empty(N_CUSTOMERS, dtype=int)
    month_int = np.floor(months).astype(int)
    for m in np.unique(month_int):
        sel = month_int == m
        wts = base * (1 + growth * m / 30)
        city[sel] = rng.choice(len(CITIES), size=int(sel.sum()), p=wts / wts.sum())
    tier = CITY_TIER[city]

    channel = np.where(on_sale,
                       rng.choice(len(CHANNELS), size=N_CUSTOMERS, p=CHANNEL_P_SALE),
                       rng.choice(len(CHANNELS), size=N_CUSTOMERS, p=CHANNEL_P_NORMAL))
    device = np.array([rng.choice(3, p=DEVICE_P[t]) for t in tier])

    p_repeat = rng.beta(6, 3, size=N_CUSTOMERS)
    p_repeat *= np.where(on_sale, 0.68, 1.0)
    p_repeat *= np.select([channel == CHANNELS.index("Referral"), channel == CHANNELS.index("Paid Social"),
                           channel == CHANNELS.index("Influencer")], [1.15, 0.88, 0.90], 1.0)
    p_repeat = np.clip(p_repeat, 0.05, 0.93)

    return pd.DataFrame({
        "idx": np.arange(N_CUSTOMERS),
        "customer_id": [f"C{i + 1:06d}" for i in range(N_CUSTOMERS)],
        "email": [f"{FIRST[int(rng.integers(len(FIRST)))]}.{LAST[int(rng.integers(len(LAST)))]}{i + 1}@example.com"
                  for i in range(N_CUSTOMERS)],
        "signup_day": day, "city_idx": city, "tier": tier, "channel_idx": channel, "device_idx": device,
        "on_sale": on_sale, "p_repeat": p_repeat,
        "gap_mean": np.exp(rng.normal(np.log(45), 0.5, size=N_CUSTOMERS)),
        "cod_base": np.select([tier == 1, tier == 2], [0.64, 0.74], 0.84),
    })


COURIERS = ["SwiftShip", "PakRider", "CityExpress", "RapidRoute"]
COURIER_P = {1: np.array([.38, .27, .25, .10]), 2: np.array([.28, .34, .16, .22]), 3: np.array([.20, .36, .10, .34])}
COURIER_BASE = np.array([1.2, 1.9, 1.5, 2.6])
COURIER_T3_EXTRA = np.array([0.0, 0.0, 2.2, 0.6])
COURIER_RTO_ADD = np.array([0.0, 0.01, 0.02, 0.045])
PROMISED_DAYS = {1: 3, 2: 4, 3: 6}
TIER_ADD = {1: 0.0, 2: 0.8, 3: 1.6}
SHIPPING_FEE = {1: 150, 2: 180, 3: 220}
RETURN_REASONS = ["Size or fit issue", "Defective or damaged", "Not as described", "Changed mind", "Arrived too late"]


def return_reason(cat_idx: int, bad_seller: bool, late: bool) -> str:
    cat = CAT_NAMES[cat_idx]
    if cat in ("Fashion", "Footwear"):
        w = np.array([.55, .05, .15, .15, .10])
    elif cat in ("Electronics", "Mobile Accessories"):
        w = np.array([0, .50, .20, .20, .10])
    else:
        w = np.array([0, .35, .20, .30, .15])
    if bad_seller:
        w = w + np.array([0, 0, 1.2, 0, 0])
    if late:
        w = w + np.array([0, 0, 0, 0, .35])
    return RETURN_REASONS[int(rng.choice(5, p=w / w.sum()))]


class Simulator:
    def __init__(self, cal, customers, products, cat_products, cat_pop):
        self.cal = cal
        self.phase = cal.phase.to_numpy()
        self.sale_code = cal.sale_code.to_numpy()
        self.congestion = cal.congestion.to_numpy()
        self.month_idx = cal.month_idx.to_numpy()
        self.month = cal.month.to_numpy()
        self.seasonal = cal.seasonal.to_numpy()
        self.cust = customers
        self.price = products.list_price.to_numpy()
        self.pcat = products._cat.to_numpy()
        self.pbad = products._bad_seller.to_numpy()
        self.cat_products, self.cat_pop = cat_products, cat_pop
        self.shift_day = off(COURIER_SHIFT)
        self.orders, self.items, self.returns = [], [], []

    def make_order(self, ci: int, d: int, is_first: bool, customer_id: str) -> dict:
        c = self.cust
        tier = int(c.tier.iat[ci])
        ph = self.phase[d]
        hours = HOUR_RAMADAN if ph in ("ramadan", "pre_eid") else HOUR_NORMAL
        ts = d * 86400 + int(rng.choice(24, p=hours)) * 3600 + int(rng.integers(3600))

        sale = self.sale_code[d]
        if sale and rng.random() < 0.70:
            code, disc = sale, rng.uniform(0.20, 0.35)
        elif is_first and rng.random() < 0.35:
            code, disc = "WELCOME15", 0.15
        elif ph in ("ramadan", "pre_eid") and rng.random() < 0.25:
            code, disc = "RAMZAN10", 0.10
        elif rng.random() < 0.05:
            code, disc = "FREESHIP", 0.0
        else:
            code, disc = "", 0.0

        cat_w = CAT_SHARE * phase_category_multiplier(ph, int(self.month[d]))
        n_items = int(rng.choice(4, p=[.62, .24, .09, .05])) + 1
        cats = rng.choice(len(CAT_NAMES), size=n_items, p=cat_w / cat_w.sum())
        lines, gmv = [], 0
        for cat in cats:
            p_idx = int(rng.choice(self.cat_products[cat], p=self.cat_pop[cat]))
            qty = int(rng.choice([1, 2, 3], p=[.6, .3, .1])) if CAT_NAMES[cat] in ("Grocery", "Beauty & Personal Care") else 1
            unit = int(round(self.price[p_idx] * (1 - disc)))
            lines.append((p_idx, qty, unit, int(round(disc * 100))))
            gmv += unit * qty

        mi = self.month_idx[d]
        p_cod = c.cod_base.iat[ci] - 0.20 * mi / 30 + (0.07 if is_first else 0) + (0.05 if gmv > 20000 else 0)
        if rng.random() < np.clip(p_cod, 0.15, 0.95):
            pay = "cod"
        elif rng.random() < 0.35 + 0.30 * mi / 30:
            pay = "jazzcash" if rng.random() < 0.55 else "easypaisa"
        else:
            pay = "card"
        cod = pay == "cod"

        p = COURIER_P[tier].copy()
        if d >= self.shift_day:
            move = min(0.12, p[0] - 0.02)
            p[0] -= move
            p[3] += move
        k = int(rng.choice(4, p=p))
        promised = PROMISED_DAYS[tier]
        raw_days = (COURIER_BASE[k] + TIER_ADD[tier] + (COURIER_T3_EXTRA[k] if tier == 3 else 0)
                    + self.congestion[d] + rng.gamma(2.0, 0.45))
        days = max(1, int(round(raw_days)))
        late = days > promised

        p_cancel = 0.025 + (0.025 if cod else 0) + (0.02 if promised >= 5 else 0)
        delivered_ts = None
        had_return = False
        if rng.random() < p_cancel:
            status = "cancelled"
        else:
            if cod:
                p_rto = (0.06 + (0.09 if is_first else 0) + (0.06 if gmv > 15000 else 0)
                         + (0.04 if tier == 3 else 0) + (0.08 if late else 0) + COURIER_RTO_ADD[k])
            else:
                p_rto = 0.01 + (0.025 if late else 0)
            deliver_day = d + days
            if rng.random() < p_rto:
                status = "rto"
            elif deliver_day >= N_DAYS:
                status = "in_transit"
            else:
                status = "delivered"
                delivered_ts = deliver_day * 86400 + int(rng.integers(10, 20)) * 3600 + int(rng.integers(3600))

        key = len(self.orders)
        for line_no, (p_idx, qty, unit, disc_pct) in enumerate(lines):
            self.items.append((key, line_no, p_idx, qty, unit, disc_pct))
            if status == "delivered":
                p_ret = CAT_RETURN[self.pcat[p_idx]] + (0.04 if late else 0) + (0.12 if self.pbad[p_idx] else 0)
                if rng.random() < p_ret:
                    req_day = d + days + int(rng.integers(1, 8))
                    if req_day < N_DAYS:
                        had_return = True
                        self.returns.append((key, line_no, return_reason(self.pcat[p_idx], self.pbad[p_idx], late),
                                             req_day, unit * qty))

        fee = 0 if (gmv >= 2500 or code == "FREESHIP") else SHIPPING_FEE[tier]
        order = {"key": key, "cust_idx": ci, "customer_id": customer_id, "ts": ts, "day": d,
                 "city_idx": int(c.city_idx.iat[ci]), "pay": pay, "promo": code, "courier": COURIERS[k],
                 "promised_day": d + promised, "delivered_ts": delivered_ts, "status": status,
                 "fee": fee, "late": late, "had_return": had_return}
        self.orders.append(order)
        return order


def simulate(cal, customers, dup_of, products, cat_products, cat_pop):
    sim = Simulator(cal, customers, products, cat_products, cat_pop)
    seasonal = cal.seasonal.to_numpy()
    first_day = np.full(len(customers), -1)
    last_day = np.full(len(customers), -1)
    dup_signup = {orig: (dup_id, day) for dup_id, (orig, day) in dup_of.items()}

    def id_for(ci, d):
        if ci in dup_signup:
            dup_id, dday = dup_signup[ci]
            if d >= dday and rng.random() < 0.45:
                return dup_id
        return customers.customer_id.iat[ci]

    for ci in range(len(customers)):
        if rng.random() < 0.13:
            continue
        d = int(customers.signup_day.iat[ci]) + (0 if rng.random() < 0.62 else int(rng.exponential(6)))
        is_first = True
        while d < N_DAYS:
            if not is_first:
                for _ in range(8):
                    if rng.random() < min(1.0, seasonal[d] / 1.15):
                        break
                    d += int(rng.integers(1, 4))
                    if d >= N_DAYS:
                        break
                if d >= N_DAYS:
                    break
            o = sim.make_order(ci, d, is_first, id_for(ci, d))
            if first_day[ci] < 0:
                first_day[ci] = d
            last_day[ci] = d
            keep = customers.p_repeat.iat[ci]
            keep *= 0.55 if o["late"] and o["status"] == "delivered" else 1.0
            keep *= 0.40 if o["status"] == "rto" else 1.0
            keep *= 0.70 if o["had_return"] else 1.0
            keep *= 0.85 if o["status"] == "cancelled" else 1.0
            if rng.random() > keep:
                break
            is_first = False
            d += max(1, int(rng.exponential(customers.gap_mean.iat[ci])))

    p_rep = customers.p_repeat.to_numpy()
    for date, (_, _, mult) in MEGA_SALES.items():
        d = off(date)
        eligible = np.where((first_day >= 0) & (first_day < d) & (d <= last_day + 40))[0]
        chosen = eligible[rng.random(len(eligible)) < 0.10 * (mult / 4.5) * (0.5 + p_rep[eligible])]
        for ci in chosen:
            sim.make_order(int(ci), d, False, id_for(int(ci), d))
    for _, end in RAMADAN:
        e = off(end)
        start = e - 9
        eligible = np.where((first_day >= 0) & (first_day < start) & (start <= last_day + 40))[0]
        chosen = eligible[rng.random(len(eligible)) < 0.14]
        for ci in chosen:
            d = int(rng.integers(start, e + 1))
            sim.make_order(int(ci), d, False, id_for(int(ci), d))
    return sim


def fmt_ts(sec: np.ndarray, legacy: np.ndarray) -> list[str]:
    ts = pd.to_datetime(START) + pd.to_timedelta(sec, unit="s")
    iso = ts.strftime("%Y-%m-%d %H:%M:%S")
    old = ts.strftime("%d/%m/%Y %H:%M")
    return np.where(legacy, old, iso).tolist()


def build_orders_table(sim, customers):
    o = pd.DataFrame(sim.orders).sort_values(["ts", "key"]).reset_index(drop=True)
    o["order_id"] = [f"ORD{i + 1:07d}" for i in range(len(o))]
    legacy = (START + pd.to_timedelta(o.ts, unit="s")) < MIGRATION
    legacy = legacy.to_numpy()

    order_dt = fmt_ts(o.ts.to_numpy(), legacy)
    delivered = np.array([""] * len(o), dtype=object)
    has_del = o.delivered_ts.notna().to_numpy()
    delivered[has_del] = fmt_ts(o.delivered_ts[has_del].astype("int64").to_numpy(), legacy[has_del])
    promised = START + pd.to_timedelta(o.promised_day, unit="D")
    promised_str = np.where(legacy, promised.dt.strftime("%d/%m/%Y"), promised.dt.strftime("%Y-%m-%d"))

    def pay_label(pay, is_legacy):
        if is_legacy:
            return {"cod": "COD" if rng.random() < 0.75 else "Cash on Delivery", "card": "CC"}.get(pay, "WALLET")
        if pay == "cod":
            return "COD " if rng.random() < 0.02 else "cash_on_delivery"
        if pay == "card":
            return "Card" if rng.random() < 0.03 else "card"
        return pay

    def status_label(status, is_legacy):
        if is_legacy:
            return {"delivered": "DLVD", "cancelled": "CNCL", "rto": "RTO", "in_transit": "SHPD"}[status]
        if status == "delivered":
            return "Delivered" if rng.random() < 0.05 else "delivered"
        if status == "cancelled":
            return "canceled" if rng.random() < 0.20 else "cancelled"
        return {"rto": "returned_to_origin", "in_transit": "shipped"}[status]

    out = pd.DataFrame({
        "order_id": o.order_id,
        "customer_id": o.customer_id,
        "order_datetime": order_dt,
        "shipping_city": [dirty_city(CITY_NAMES[i]) for i in o.city_idx],
        "payment_method": [pay_label(p, lg) for p, lg in zip(o.pay, legacy)],
        "promo_code": [(code if code else ("NONE" if lg else "")) for code, lg in zip(o.promo, legacy)],
        "courier": o.courier,
        "promised_delivery_date": promised_str,
        "delivered_at": delivered,
        "order_status": [status_label(s, lg) for s, lg in zip(o.status, legacy)],
        "shipping_fee": [(f"Rs. {f}" if lg else str(f)) for f, lg in zip(o.fee, legacy)],
    })

    delivered_rows = np.where(has_del)[0]
    missing = rng.choice(delivered_rows, size=int(0.008 * len(delivered_rows)), replace=False)
    out.loc[missing, "delivered_at"] = ""
    before = rng.choice(np.setdiff1d(delivered_rows, missing), size=int(0.001 * len(delivered_rows)), replace=False)
    early_sec = o.ts.to_numpy()[before] - 86400
    out.loc[before, "delivered_at"] = fmt_ts(early_sec, legacy[before])
    key_to_order = dict(zip(o.key, o.order_id))
    return out, o, key_to_order


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    cal = build_calendar()
    sellers, products, cat_products, cat_pop = make_catalog()
    customers = make_customers(cal)

    dup_rows, dup_of = [], {}
    dup_idx = rng.choice(len(customers), size=int(0.015 * len(customers)), replace=False)
    for n, ci in enumerate(sorted(dup_idx)):
        dup_id = f"C{N_CUSTOMERS + n + 1:06d}"
        day = int(min(N_DAYS - 1, customers.signup_day.iat[ci] + rng.integers(1, 21)))
        email = customers.email.iat[ci]
        email = email.capitalize() if rng.random() < 0.5 else email.upper()
        if rng.random() < 0.5:
            email = f" {email} "
        dup_of[dup_id] = (int(ci), day)
        dup_rows.append((dup_id, email, day, int(ci)))

    sim = simulate(cal, customers, dup_of, products, cat_products, cat_pop)
    orders_out, orders_int, key_to_order = build_orders_table(sim, customers)

    def signup_str(day):
        return (START + pd.Timedelta(days=int(day))).strftime("%Y-%m-%d")

    def channel_label(idx):
        ch = CHANNELS[idx]
        if ch in CHANNEL_VARIANTS and rng.random() < 0.08:
            v = CHANNEL_VARIANTS[ch]
            return v[int(rng.integers(len(v)))]
        return ch

    cust_rows = [{
        "customer_id": r.customer_id, "email": r.email,
        "signup_date": "" if rng.random() < 0.003 else signup_str(r.signup_day),
        "city": dirty_city(CITY_NAMES[r.city_idx]),
        "acquisition_channel": channel_label(r.channel_idx),
        "device_type": DEVICES[r.device_idx],
    } for r in customers.itertuples()]
    for dup_id, email, day, ci in dup_rows:
        r = customers.iloc[ci]
        cust_rows.append({"customer_id": dup_id, "email": email, "signup_date": signup_str(day),
                          "city": dirty_city(CITY_NAMES[r.city_idx], p_variant=0.5),
                          "acquisition_channel": CHANNELS[r.channel_idx], "device_type": DEVICES[r.device_idx]})
    for t in range(1, 4):
        cust_rows.append({"customer_id": f"TEST{t:03d}", "email": f"qa+{t}@kaarobar.test",
                          "signup_date": "2025-01-15", "city": "Test City",
                          "acquisition_channel": "Internal", "device_type": "Desktop"})
    customers_out = pd.DataFrame(cust_rows)

    items = pd.DataFrame(sim.items, columns=["key", "line_no", "p_idx", "quantity", "unit_price", "discount_pct"])
    items["order_id"] = items.key.map(key_to_order)
    items = items.sort_values(["order_id", "line_no"]).reset_index(drop=True)
    items["order_item_id"] = [f"OI{i + 1:07d}" for i in range(len(items))]
    items["product_id"] = products.product_id.to_numpy()[items.p_idx]
    item_id_lookup = dict(zip(zip(items.key, items.line_no), items.order_item_id))

    test_orders, test_items = [], []
    for n in range(45):
        d = int(rng.integers(off("2025-02-01"), N_DAYS - 5))
        ts = START + pd.Timedelta(days=d, hours=int(rng.integers(10, 18)))
        oid = f"ORD9{n + 1:06d}"
        test_orders.append({"order_id": oid, "customer_id": f"TEST{n % 3 + 1:03d}",
                            "order_datetime": ts.strftime("%Y-%m-%d %H:%M:%S"), "shipping_city": "Test City",
                            "payment_method": "card", "promo_code": "", "courier": "SwiftShip",
                            "promised_delivery_date": (ts + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
                            "delivered_at": (ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                            "order_status": "delivered", "shipping_fee": "0"})
        test_items.append({"order_item_id": f"OI9{n + 1:06d}", "order_id": oid,
                           "product_id": products.product_id.iat[int(rng.integers(len(products)))],
                           "quantity": 1, "unit_price": 1, "discount_pct": 0})

    items_out = items[["order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_pct"]].copy()
    n_items = len(items_out)
    err = rng.choice(n_items, size=int(0.0025 * n_items), replace=False)
    items_out.loc[err, "unit_price"] = items_out.loc[err, "unit_price"] * np.where(rng.random(len(err)) < 0.8, 10, 100)
    bad_qty = rng.choice(np.setdiff1d(np.arange(n_items), err), size=int(0.001 * n_items), replace=False)
    items_out.loc[bad_qty, "quantity"] = rng.choice([0, -1], size=len(bad_qty))
    items_out = pd.concat([items_out, pd.DataFrame(test_items)], ignore_index=True)

    orders_out = pd.concat([orders_out, pd.DataFrame(test_orders)], ignore_index=True)
    dups = orders_out.sample(frac=0.004, random_state=SEED)
    orders_out = pd.concat([orders_out, dups], ignore_index=True).sort_values("order_id", kind="stable")

    ret = pd.DataFrame(sim.returns, columns=["key", "line_no", "reason", "req_day", "refund"])
    ret["order_item_id"] = [item_id_lookup[(k, ln)] for k, ln in zip(ret.key, ret.line_no)]
    ret["order_id"] = ret.key.map(key_to_order)
    ret = ret.sort_values(["req_day", "order_item_id"]).reset_index(drop=True)
    ret["return_id"] = [f"RT{i + 1:06d}" for i in range(len(ret))]
    ret["return_requested_date"] = (START + pd.to_timedelta(ret.req_day, unit="D")).dt.strftime("%Y-%m-%d")
    orphans = rng.choice(len(ret), size=max(1, int(0.002 * len(ret))), replace=False)
    ret.loc[orphans, "order_item_id"] = [f"OI8{int(x):06d}" for x in rng.integers(0, 999999, size=len(orphans))]
    returns_out = ret[["return_id", "order_item_id", "order_id", "reason", "return_requested_date", "refund"]].rename(
        columns={"reason": "return_reason", "refund": "refund_amount"})

    sessions = []
    signup_days = np.sort(np.concatenate([customers.signup_day.to_numpy()]))
    cust_ids_sorted = customers.sort_values("signup_day").customer_id.to_numpy()
    seasonal = cal.seasonal.to_numpy()
    base_conv = {"Android": 0.56, "iOS": 0.63, "Desktop": 0.66}
    lift = {"Android": 0.055, "iOS": 0.045, "Desktop": 0.0}
    sources = ["App", "Organic Search", "Paid Social", "Direct", "Referral"]
    for d in range(off(EXP_START), off(EXP_END) + 1):
        n = int(round(1650 * seasonal[d]))
        dev = rng.choice(DEVICES, size=n, p=[.62, .14, .24])
        src = rng.choice(sources, size=n, p=[.34, .22, .20, .14, .10])
        grp = np.where(rng.random(n) < 0.5, "treatment", "control")
        known = np.searchsorted(signup_days, d, side="right")
        cust = np.where(rng.random(n) < 0.78, cust_ids_sorted[rng.integers(0, known, size=n)], "")
        hours = HOUR_RAMADAN if cal.phase.iat[d] in ("ramadan", "pre_eid") else HOUR_NORMAL
        ts = d * 86400 + rng.choice(24, size=n, p=hours) * 3600 + rng.integers(0, 3600, size=n)
        p = np.array([base_conv[x] for x in dev]) + np.where(grp == "treatment", [lift[x] for x in dev], 0)
        p += np.select([src == "Paid Social", src == "Referral"], [-0.06, 0.03], 0)
        done = rng.random(n) < p
        value = np.where(done, np.round(np.exp(rng.normal(np.log(4200), 0.7, size=n))), np.nan)
        dur = np.round(np.exp(rng.normal(np.log(170), 0.6, size=n))).astype(int)
        for i in range(n):
            sessions.append((ts[i], cust[i], dev[i], src[i], grp[i], dur[i], int(done[i]), value[i]))
        n_bots = int(round(0.013 * n))
        for _ in range(n_bots):
            sessions.append((d * 86400 + int(rng.integers(0, 86400)), "", "Desktop", "Direct",
                             "treatment" if rng.random() < 0.72 else "control",
                             int(rng.integers(0, 3)), 0, np.nan))
    s = pd.DataFrame(sessions, columns=["ts", "customer_id", "device_type", "traffic_source",
                                        "experiment_group", "session_duration_sec", "completed_order", "order_value"])
    s = s.sort_values("ts", kind="stable").reset_index(drop=True)
    s.insert(0, "session_id", [f"CS{i + 1:07d}" for i in range(len(s))])
    s["session_start"] = (START + pd.to_timedelta(s.ts, unit="s")).dt.strftime("%Y-%m-%d %H:%M:%S")
    variants = rng.random(len(s))
    s.loc[variants < 0.015, "experiment_group"] = s.loc[variants < 0.015, "experiment_group"].str.capitalize()
    s.loc[(variants >= 0.015) & (variants < 0.025), "experiment_group"] = (
        s.loc[(variants >= 0.015) & (variants < 0.025), "experiment_group"].str.upper() + " ")
    s["order_value"] = s.order_value.map(lambda v: "" if pd.isna(v) else str(int(v)))
    sessions_out = s[["session_id", "customer_id", "session_start", "device_type", "traffic_source",
                      "experiment_group", "session_duration_sec", "completed_order", "order_value"]]
    sessions_out = pd.concat([sessions_out, sessions_out.sample(frac=0.005, random_state=SEED)],
                             ignore_index=True).sort_values("session_id", kind="stable")

    products_out = products.drop(columns=["_cat", "_bad_seller"])

    tables = {"customers": customers_out, "sellers": sellers, "products": products_out,
              "orders": orders_out, "order_items": items_out, "returns": returns_out,
              "checkout_sessions": sessions_out}
    for name, df in tables.items():
        df.to_csv(RAW_DIR / f"{name}.csv", index=False)
        df.head(1000).to_csv(SAMPLE_DIR / f"{name}.csv", index=False)
        print(f"{name:18s} {len(df):>8,} rows")


if __name__ == "__main__":
    main()
