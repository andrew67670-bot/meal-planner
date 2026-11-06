# Skeleton and step-by-step comments created with help from Claude
# (Anthropic's AI assistant), claude.ai, 2026-11-05.
# The code under each step is written by me.
#
# Goal: print every recipe with its ingredients and what it would cost
# to shop for it, for a household of a given size.
# Run it with:  python show_recipes.py


# ---------------------------------------------------------------------------
# STEP 1: Imports and settings
# ---------------------------------------------------------------------------
# - Import sqlite3 (to talk to the database) and math (you'll need rounding up).
# - Make a variable for household size and set it to 4.
# CHECK: run the file. Nothing should print, but there should be no errors.
import sqlite3
import math

household_size = 4

# ---------------------------------------------------------------------------
# STEP 2: Connect to the database
# ---------------------------------------------------------------------------
# - Connect to meal_planner.db.
# - Set the connection's row_factory to sqlite3.Row so you can read columns
#   by name (row["title"]) instead of position (row[1]).
# CHECK: print the connection object. It should show a sqlite3.Connection.
conn = sqlite3.connect("meal_planner.db")
conn.row_factory = sqlite3.Row

# ---------------------------------------------------------------------------
# STEP 3: Get all recipes
# ---------------------------------------------------------------------------
# - Write a SELECT for id, title, servings, and prep_minutes from recipes.
# - Run it and loop over the results.
# CHECK: print each title. You should see four recipes.
#cursor = conn.execute(
#    "SELECT id, title, servings, prep_minutes FROM recipes"
#)
#for row in cursor.fetchall():
#    print(row["title"])

# ---------------------------------------------------------------------------
# STEP 4: Get the ingredients for one recipe
# ---------------------------------------------------------------------------
# - Inside the recipe loop, write a second query that JOINs recipe_ingredients
#   to ingredients (they share ingredient_id).
# - You want: ingredient id, name, base_unit, is_staple, qty_per_serving,
#   and original_text.
# - Filter to the current recipe's id.
# - IMPORTANT: pass the recipe id with a ? placeholder and a tuple of values.
#   Never build the SQL string with an f-string or +. (This is the same habit
#   CS50 teaches to prevent SQL injection.)
# CHECK: print each ingredient name under its recipe title.

cursor = conn.execute(
    "SELECT id, title, servings, prep_minutes FROM recipes"
)
for row in cursor.fetchall():
    print(row["title"])
    recipe_shop_cost = 0
    recipe_fair_share_cost = 0
    ingredient_cursor = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.base_unit, i.is_staple,
        ri.qty_per_serving, ri.original_text
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i 
        ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ?
        """,
        (row["id"],),
    )
    for ingredient in ingredient_cursor:
        print(ingredient["name"])

# ---------------------------------------------------------------------------
# STEP 5: Scale to the household
# ---------------------------------------------------------------------------
# - qty_per_serving is per ONE person. Multiply by household size to get the
#   total amount needed for the recipe.
# CHECK: Chicken Tacos for 4 should need 480 g of chicken breast.
cursor = conn.execute(
    "SELECT id, title, servings, prep_minutes FROM recipes"
)
for row in cursor.fetchall():
    print(row["title"])
    ingredient_cursor = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.base_unit, i.is_staple,
        (ri.qty_per_serving * ?) AS total_qty, ri.original_text
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i 
        ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ?
        """,
        (household_size, row["id"]),
    )
    for ingredient in ingredient_cursor:
        print(ingredient["name"], ingredient["total_qty"],ingredient["base_unit"])


# ---------------------------------------------------------------------------
# STEP 6: Find the price options for one ingredient
# ---------------------------------------------------------------------------
# - For each ingredient, query ingredient_packages for its package_size and
#   price_cents (filter by ingredient id, again with a ? placeholder).
# - Skip ingredients where is_staple = 1 (like olive oil). They aren't
#   counted in the shopping cost.
# CHECK: chicken breast should return two packages (900 g and 1800 g).

cursor = conn.execute(
    "SELECT id, title, servings, prep_minutes FROM recipes"
)
for row in cursor.fetchall():
    print(row["title"])
    ingredient_cursor = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.base_unit, i.is_staple,
        (ri.qty_per_serving * ?) AS total_qty, ri.original_text
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i 
        ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ? AND i.is_staple = 0
        ORDER BY i.name
        """,
        (household_size, row["id"]),
    )

    for ingredient in ingredient_cursor:
        packages = []
        
        package_cursor = conn.execute(
            """
            SELECT package_size, price_cents
            FROM ingredient_packages
            WHERE ingredient_id = ?
            ORDER BY package_size
            """,
            (ingredient["ingredient_id"],),
        )

        for package in package_cursor:
            packages.append({"size": package["package_size"], "price": package["price_cents"]})
            print(
                f'  {package["package_size"]} {ingredient["base_unit"]} '
                f'— {package["price_cents"]} cents'
            )

# ---------------------------------------------------------------------------
# STEP 7: Compute two kinds of cost
# ---------------------------------------------------------------------------
# For each ingredient, work out BOTH:
#
#   a) Shop cost: you can't buy part of a package. For each package option,
#      how many packages do you need to cover the total amount? (Round up
#      with math.ceil.) Multiply by the price. Keep the CHEAPEST option.
#
#   b) Fair-share cost: only the fraction of a package you actually use.
#      (amount needed / package_size) * price_cents. Use the same package
#      you chose in (a).
#
# - Money is stored in cents (integers). Keep it in cents while calculating.
# - Add each ingredient's costs into two running totals for the recipe.
# CHECK: Chicken Tacos for 4 should come out to about:
#        shop cost = 2165 cents, fair-share cost = about 1202 cents.
#        The gap between them is leftover food you paid for but didn't use.
#        That gap is the problem your whole project is trying to shrink.
cursor = conn.execute(
    "SELECT id, title, servings, prep_minutes FROM recipes"
)
for row in cursor.fetchall():
    recipe_shop_cost = 0
    recipe_fair_share_cost = 0
    print(row["title"])
    ingredient_cursor = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.base_unit, i.is_staple,
        (ri.qty_per_serving * ?) AS total_qty, ri.original_text
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i 
        ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ? AND i.is_staple = 0
        ORDER BY i.name
        """,
        (household_size, row["id"]),
    )

    for ingredient in ingredient_cursor:
        packages = []
        package_cursor = conn.execute(
            """
            SELECT package_size, price_cents
            FROM ingredient_packages
            WHERE ingredient_id = ?
            ORDER BY package_size
            """,
            (ingredient["ingredient_id"],),
        )

        for package in package_cursor:
            package_count = math.ceil(
                ingredient["total_qty"] / package["package_size"]
            )
            packages.append(
                {
                    "size": package["package_size"],
                    "price": package["price_cents"],
                    "shop_cost": package_count * package["price_cents"],
                    "fair_share_cost": (
                        ingredient["total_qty"] / package["package_size"]
                    )
                    * package["price_cents"],
                }
            )

        if not packages:
            raise ValueError(
                f'No package prices found for ingredient "{ingredient["name"]}" '
                f'in recipe "{row["title"]}".'
            )

        best_package = min(packages, key=lambda option: option["shop_cost"])
        recipe_shop_cost += best_package["shop_cost"]
        recipe_fair_share_cost += best_package["fair_share_cost"]
        print(
            f'  {ingredient["name"]}: amount needed: {ingredient["total_qty"]} {ingredient["base_unit"]}, '
            f'shop ${best_package["shop_cost"] / 100:.2f}, '
            f'fair share ${best_package["fair_share_cost"] / 100:.2f}'
        )

    print(
        f'  Recipe totals: shop ${recipe_shop_cost / 100:.2f}, '
        f'fair share ${recipe_fair_share_cost / 100:.2f}\n'
    )
    print()

# ---------------------------------------------------------------------------
# STEP 8: Print it nicely
# ---------------------------------------------------------------------------
# For each recipe print:
#   - the title, prep time, and household size
#   - each ingredient: the original_text and the total amount needed
#   - the two totals, converted from cents to dollars (cents / 100)
# - Format money with an f-string like {value:.2f}.
# - Add blank lines or dashes between recipes so it's readable.
cursor = conn.execute(
    "SELECT id, title, servings, prep_minutes FROM recipes"
)
for row in cursor.fetchall():
    recipe_shop_cost = 0
    recipe_fair_share_cost = 0
    print(row["title"],row["prep_minutes"],"minutes, household size",household_size)
    ingredient_cursor = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.base_unit, i.is_staple,
        (ri.qty_per_serving * ?) AS total_qty, ri.original_text, ri.original_text
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i 
        ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ? AND i.is_staple = 0
        ORDER BY i.name
        """,
        (household_size, row["id"]),
    )

    for ingredient in ingredient_cursor:
        packages = []
        package_cursor = conn.execute(
            """
            SELECT package_size, price_cents
            FROM ingredient_packages
            WHERE ingredient_id = ?
            ORDER BY package_size
            """,
            (ingredient["ingredient_id"],),
        )

        for package in package_cursor:
            package_count = math.ceil(
                ingredient["total_qty"] / package["package_size"]
            )
            packages.append(
                {
                    "size": package["package_size"],
                    "price": package["price_cents"],
                    "shop_cost": package_count * package["price_cents"],
                    "fair_share_cost": (
                        ingredient["total_qty"] / package["package_size"]
                    )
                    * package["price_cents"],
                }
            )

        if not packages:
            raise ValueError(
                f'No package prices found for ingredient "{ingredient["name"]}" '
                f'in recipe "{row["title"]}".'
            )

        best_package = min(packages, key=lambda option: option["shop_cost"])
        recipe_shop_cost += best_package["shop_cost"]
        recipe_fair_share_cost += best_package["fair_share_cost"]
        print(
            f'  {ingredient["original_text"]}: amount needed: {ingredient["total_qty"]:g} {ingredient["base_unit"]}, '
            f'shop ${best_package["shop_cost"] / 100:.2f}, '
            f'fair share ${best_package["fair_share_cost"] / 100:.2f}'
        )

    print(
        f'  Recipe totals: shop ${recipe_shop_cost / 100:.2f}, '
        f'fair share ${recipe_fair_share_cost / 100:.2f}\n'
    )

# ---------------------------------------------------------------------------
# STEP 9: Clean up
# ---------------------------------------------------------------------------
# - Close the database connection at the end.
# CHECK: run the whole file, then change the household size to 2 and run it
#        again. The amounts and costs should change. Do the totals make sense?
household_size = 2
cursor = conn.execute(
    "SELECT id, title, servings, prep_minutes FROM recipes"
)
for row in cursor.fetchall():
    recipe_shop_cost = 0
    recipe_fair_share_cost = 0
    print(row["title"],row["prep_minutes"],"minutes, household size",household_size)
    ingredient_cursor = conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, i.base_unit, i.is_staple,
        (ri.qty_per_serving * ?) AS total_qty, ri.original_text, ri.original_text
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i 
        ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ? AND i.is_staple = 0
        ORDER BY i.name
        """,
        (household_size, row["id"]),
    )

    for ingredient in ingredient_cursor:
        packages = []
        package_cursor = conn.execute(
            """
            SELECT package_size, price_cents
            FROM ingredient_packages
            WHERE ingredient_id = ?
            ORDER BY package_size
            """,
            (ingredient["ingredient_id"],),
        )

        for package in package_cursor:
            package_count = math.ceil(
                ingredient["total_qty"] / package["package_size"]
            )
            packages.append(
                {
                    "size": package["package_size"],
                    "price": package["price_cents"],
                    "shop_cost": package_count * package["price_cents"],
                    "fair_share_cost": (
                        ingredient["total_qty"] / package["package_size"]
                    )
                    * package["price_cents"],
                }
            )

        if not packages:
            raise ValueError(
                f'No package prices found for ingredient "{ingredient["name"]}" '
                f'in recipe "{row["title"]}".'
            )

        best_package = min(packages, key=lambda option: option["shop_cost"])
        recipe_shop_cost += best_package["shop_cost"]
        recipe_fair_share_cost += best_package["fair_share_cost"]
        print(
            f'  {ingredient["original_text"]}: amount needed: {ingredient["total_qty"]:g} {ingredient["base_unit"]}, '
            f'shop ${best_package["shop_cost"] / 100:.2f}, '
            f'fair share ${best_package["fair_share_cost"] / 100:.2f}'
        )

    print(
        f'  Recipe totals: shop ${recipe_shop_cost / 100:.2f}, '
        f'fair share ${recipe_fair_share_cost / 100:.2f}\n'
    )