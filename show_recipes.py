# Created with help from Claude (Anthropic's AI assistant), claude.ai, and
# Microsoft Copilot, 2026-11-05.
# The code under each step is written by me, but used both co-pilot and Claude to help me think through the steps, cleanup and debug code.
# Step by step shown in show_recipes_worksheet.py, which is a script to show recipes and their costs for a given household size. 
# Goal: print every recipe with its ingredients and what it would cost
# to shop for it, for a household of a given size.
# Run it with:  python show_recipes.py
import sqlite3
import math

conn = sqlite3.connect("meal_planner.db")
conn.row_factory = sqlite3.Row

household_size = 4  # Change this to the desired household size
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
            f'  {ingredient["name"]}: amount needed: {ingredient["total_qty"]:g} {ingredient["base_unit"]}, '
            f'shop ${best_package["shop_cost"] / 100:.2f}, '
            f'fair share ${best_package["fair_share_cost"] / 100:.2f}'
        )

    print(
        f'  Recipe totals: shop ${recipe_shop_cost / 100:.2f}, '
        f'fair share ${recipe_fair_share_cost / 100:.2f}\n'
    )
conn.close()