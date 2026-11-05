# Created with help from Claude (Anthropic's AI assistant), claude.ai, 2026-11-05.
# Purpose: database seed data / database setup / table check script.
import sqlite3
from urllib.parse import quote_plus

conn = sqlite3.connect("meal_planner.db")
conn.execute("PRAGMA foreign_keys = ON")

# name, base_unit, is_staple, is_perishable, shelf_life_days, carryover_credit
INGREDIENTS = [
    ("chicken breast",   "g",    0, 1, 3,    0.0),
    ("ground beef",      "g",    0, 1, 2,    0.0),
    ("flour tortillas",  "each", 0, 1, 14,   0.0),
    ("shredded cheese",  "g",    0, 1, 14,   0.0),
    ("eggs",             "each", 0, 1, 21,   0.0),
    ("yellow onion",     "each", 0, 1, 21,   0.0),
    ("black beans",      "g",    0, 0, None, 0.7),
    ("spaghetti",        "g",    0, 0, None, 0.7),
    ("marinara sauce",   "g",    0, 0, None, 0.6),
    ("white rice",       "g",    0, 0, None, 0.8),
    ("frozen peas",      "g",    0, 0, None, 0.5),
    ("salsa",            "g",    0, 0, None, 0.5),
    ("soy sauce",        "ml",   0, 0, None, 0.8),
    ("olive oil",        "ml",   1, 0, None, 0.0),
]

# ingredient, package_size (in base unit), price in cents
PACKAGES = [
    ("chicken breast",  900, 1099), ("chicken breast", 1800, 1999),
    ("ground beef",     450, 599),  ("ground beef",    900, 1099),
    ("flour tortillas", 10, 349),   ("flour tortillas", 20, 599),
    ("shredded cheese", 227, 299),  ("shredded cheese", 454, 499),
    ("eggs",            12, 399),   ("eggs",            18, 549),
    ("yellow onion",    1, 89),     ("yellow onion",    5, 349),
    ("black beans",     425, 129),
    ("spaghetti",       454, 149),
    ("marinara sauce",  680, 249),
    ("white rice",      907, 279),  ("white rice",     2268, 549),
    ("frozen peas",     340, 189),
    ("salsa",           454, 329),
    ("soy sauce",       296, 249),
    ("olive oil",       500, 899),
]

# spoonacular_id values are placeholders until real Spoonacular recipes are imported
RECIPES = [
    (900001, "Chicken Tacos", 4, 25, ["Mexican", "chicken"], [
        ("chicken breast", 120, "1 lb chicken breast, cooked and shredded"),
        ("flour tortillas", 2, "8 small flour tortillas"),
        ("shredded cheese", 25, "1 cup shredded cheese"),
        ("salsa", 40, "1 cup salsa"),
        ("yellow onion", 0.25, "1 small onion, diced"),
    ]),
    (900002, "Spaghetti with Meat Sauce", 4, 30, ["Italian", "beef"], [
        ("spaghetti", 90, "12 oz spaghetti"),
        ("ground beef", 100, "1 lb ground beef"),
        ("marinara sauce", 110, "1 jar marinara sauce"),
        ("yellow onion", 0.25, "1 onion, diced"),
    ]),
    (900003, "Chicken Fried Rice", 4, 25, ["Asian", "chicken"], [
        ("chicken breast", 100, "1 lb chicken breast, diced"),
        ("white rice", 75, "1.5 cups uncooked white rice"),
        ("eggs", 0.5, "2 eggs"),
        ("frozen peas", 40, "1 cup frozen peas"),
        ("soy sauce", 15, "4 tbsp soy sauce"),
        ("yellow onion", 0.2, "1 onion, diced"),
        ("olive oil", 5, "1 tbsp olive oil"),
    ]),
    (900004, "Black Bean Quesadillas", 4, 20, ["Mexican", "vegetarian"], [
        ("flour tortillas", 2, "8 flour tortillas"),
        ("black beans", 100, "1 can black beans, drained"),
        ("shredded cheese", 40, "1.5 cups shredded cheese"),
        ("salsa", 30, "salsa for serving"),
    ]),
]

TAGS = [("cuisine", "Mexican"), ("cuisine", "Italian"), ("cuisine", "Asian"),
        ("protein", "chicken"), ("protein", "beef"), ("protein", "vegetarian")]

with conn:
    for ing in INGREDIENTS:
        conn.execute(
            "INSERT INTO ingredients (name, base_unit, is_staple, is_perishable, "
            "shelf_life_days, carryover_credit) VALUES (?, ?, ?, ?, ?, ?)", ing)

    for name, size, cents in PACKAGES:
        url = "https://www.amazon.com/s?k=" + quote_plus(name)
        conn.execute(
            "INSERT INTO ingredient_packages (ingredient_id, package_size, price_cents, purchase_url) "
            "VALUES ((SELECT id FROM ingredients WHERE name = ?), ?, ?, ?)",
            (name, size, cents, url))

    for ttype, tname in TAGS:
        conn.execute("INSERT INTO tags (type, name) VALUES (?, ?)", (ttype, tname))

    for sid, title, servings, prep, tags, ings in RECIPES:
        cur = conn.execute(
            "INSERT INTO recipes (source, spoonacular_id, title, servings, prep_minutes) "
            "VALUES ('spoonacular', ?, ?, ?, ?)", (sid, title, servings, prep))
        rid = cur.lastrowid
        for tname in tags:
            conn.execute(
                "INSERT INTO recipe_tags (recipe_id, tag_id) "
                "VALUES (?, (SELECT id FROM tags WHERE name = ?))", (rid, tname))
        for iname, qty, text in ings:
            conn.execute(
                "INSERT INTO recipe_ingredients (recipe_id, ingredient_id, qty_per_serving, original_text) "
                "VALUES (?, (SELECT id FROM ingredients WHERE name = ?), ?, ?)",
                (rid, iname, qty, text))

for table in ("ingredients", "ingredient_packages", "tags", "recipes", "recipe_tags", "recipe_ingredients"):
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {n} rows")
conn.close()