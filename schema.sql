-- Created with help from Claude (Anthropic's AI assistant), claude.ai, 2026-11-04 to 2026-11-05.
-- Purpose: database schema design for the meal planner. 
--Meal Planner schema (SQLite)
-- Conventions:
--   * Money is stored as INTEGER cents (no float rounding bugs)
--   * All ingredient quantities are in the ingredient's base unit (g, ml, or each),
--     converted once at import time so the optimizer only sees clean numbers
--   * Run PRAGMA foreign_keys = ON; on every connection (SQLite ignores FKs otherwise)
 
PRAGMA foreign_keys = ON;
 
-- ---------------------------------------------------------------------------
-- USERS AND PREFERENCES
-- ---------------------------------------------------------------------------
 
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE,
    hash        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
 
-- Standing defaults, prefilled each week so planning becomes "confirm and go"
CREATE TABLE user_preferences (
    user_id                  INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    household_size           INTEGER NOT NULL DEFAULT 2 CHECK (household_size > 0),
    weekly_budget_cents      INTEGER NOT NULL DEFAULT 0 CHECK (weekly_budget_cents >= 0),
    takeout_allowance_cents  INTEGER NOT NULL DEFAULT 2500 CHECK (takeout_allowance_cents >= 0),
    max_prep_minutes         INTEGER NOT NULL DEFAULT 60 CHECK (max_prep_minutes >= 0),
    max_flex_nights          INTEGER NOT NULL DEFAULT 1 CHECK (max_flex_nights >= 0),
    variety_weight           REAL NOT NULL DEFAULT 0 CHECK (variety_weight >= 0),  -- lambda: 0 = pure cost
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);
 
-- Ingredients a family should never see (hard filter before the solver runs)
CREATE TABLE user_excluded_ingredients (
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, ingredient_id)
);
 
-- Preferred cuisines, styles (bbq, grilled...) and proteins the family is OK with.
-- One table covers all three because they all live in `tags`.
CREATE TABLE user_preferred_tags (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, tag_id)
);
 
-- ---------------------------------------------------------------------------
-- INGREDIENTS AND PRICING
-- ---------------------------------------------------------------------------
 
CREATE TABLE ingredients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    spoonacular_id    INTEGER UNIQUE,                      -- NULL for hand-seeded items
    name              TEXT NOT NULL UNIQUE,
    base_unit         TEXT NOT NULL CHECK (base_unit IN ('g', 'ml', 'each')),
    is_staple         INTEGER NOT NULL DEFAULT 0 CHECK (is_staple IN (0, 1)),   -- salt, oil, water: excluded from cart
    is_perishable     INTEGER NOT NULL DEFAULT 0 CHECK (is_perishable IN (0, 1)),
    shelf_life_days   INTEGER CHECK (shelf_life_days IS NULL OR shelf_life_days > 0),
    carryover_credit  REAL NOT NULL DEFAULT 0 CHECK (carryover_credit BETWEEN 0 AND 1)
        -- share of leftover value credited back in the objective:
        -- 0 for perishables, ~0.5-0.8 for shelf-stable goods
);
 
-- An ingredient can be sold in several package sizes; the solver picks counts of each
CREATE TABLE ingredient_packages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id       INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    package_size        REAL NOT NULL CHECK (package_size > 0),   -- in the ingredient's base_unit
    price_cents         INTEGER NOT NULL CHECK (price_cents >= 0),
    purchase_url        TEXT,                                     -- Amazon search link for the "buy this" button
    price_updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (ingredient_id, package_size)
);
 
-- ---------------------------------------------------------------------------
-- RECIPES AND TAGS
-- ---------------------------------------------------------------------------
 
CREATE TABLE recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL CHECK (source IN ('spoonacular', 'flex')),
    spoonacular_id  INTEGER UNIQUE,                    -- NULL for flex meals
    title           TEXT NOT NULL,
    servings        INTEGER NOT NULL CHECK (servings > 0),
    prep_minutes    INTEGER NOT NULL CHECK (prep_minutes >= 0),   -- 0 for flex meals
    image_url       TEXT,
    source_url      TEXT,
    instructions    TEXT,
    cached_at       TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (source = 'flex' OR spoonacular_id IS NOT NULL)
);
 
-- type lets one table hold cuisines, derived proteins, and derived styles
CREATE TABLE tags (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    type  TEXT NOT NULL CHECK (type IN ('cuisine', 'protein', 'style')),
    name  TEXT NOT NULL,
    UNIQUE (type, name)
);
 
CREATE TABLE recipe_tags (
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (recipe_id, tag_id)
);
 
-- Per-SERVING quantities, so any household size scales cleanly
CREATE TABLE recipe_ingredients (
    recipe_id         INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id     INTEGER NOT NULL REFERENCES ingredients(id),
    qty_per_serving   REAL NOT NULL CHECK (qty_per_serving > 0),   -- in ingredient's base_unit
    original_text     TEXT,                                        -- e.g. "2 cups diced yellow onion", for display
    PRIMARY KEY (recipe_id, ingredient_id)
);
 
-- ---------------------------------------------------------------------------
-- FEEDBACK (keep / dislike)
-- ---------------------------------------------------------------------------
 
CREATE TABLE recipe_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    rating      TEXT NOT NULL CHECK (rating IN ('like', 'dislike')),
    scope       TEXT NOT NULL CHECK (scope IN ('never', 'week')),   -- "never again" vs "not this week"
    plan_id     INTEGER REFERENCES meal_plans(id) ON DELETE CASCADE, -- required when scope = 'week'
    reason      TEXT CHECK (reason IN ('too_long', 'protein', 'never_again', 'other')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (scope = 'never' OR plan_id IS NOT NULL)
);
 
-- ---------------------------------------------------------------------------
-- MEAL PLANS
-- ---------------------------------------------------------------------------
 
-- Snapshots the inputs used, so an old plan stays reproducible after preferences change
CREATE TABLE meal_plans (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start               TEXT NOT NULL,                  -- ISO date of the first day
    household_size           INTEGER NOT NULL CHECK (household_size > 0),
    total_budget_cents       INTEGER NOT NULL CHECK (total_budget_cents >= 0),
    takeout_allowance_cents  INTEGER NOT NULL CHECK (takeout_allowance_cents >= 0),
    grocery_budget_cents     INTEGER NOT NULL CHECK (grocery_budget_cents >= 0),
        -- = total_budget - takeout_allowance * number of takeout days (reserved model)
    variety_weight           REAL NOT NULL DEFAULT 0,
    solver                   TEXT NOT NULL DEFAULT 'ilp' CHECK (solver IN ('greedy', 'ilp')),
    grocery_cost_cents       INTEGER,                        -- filled in after solving
    over_budget              INTEGER NOT NULL DEFAULT 0 CHECK (over_budget IN (0, 1)),  -- infeasible-budget fallback
    status                   TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed')),
    created_at               TEXT NOT NULL DEFAULT (datetime('now'))
);
 
-- One row per night. Day type drives everything:
--   cook    -> recipe from the full pool
--   flex    -> recipe from the hand-seeded flex list (recipes.source = 'flex')
--   takeout -> no recipe, holds reserved money
CREATE TABLE plan_days (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id               INTEGER NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    day_date              TEXT NOT NULL,                     -- ISO date
    day_type              TEXT NOT NULL CHECK (day_type IN ('cook', 'flex', 'takeout')),
    recipe_id             INTEGER REFERENCES recipes(id),
    takeout_budget_cents  INTEGER NOT NULL DEFAULT 0 CHECK (takeout_budget_cents >= 0),
    is_locked             INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),  -- user pressed "Keep"
    max_prep_minutes      INTEGER,                           -- optional per-night override (stretch goal)
    UNIQUE (plan_id, day_date),
    CHECK (day_type = 'takeout' OR recipe_id IS NOT NULL OR is_locked = 0),
    CHECK (day_type != 'takeout' OR recipe_id IS NULL)
);
 
-- Solver output: the shopping list, with leftovers so waste is visible
CREATE TABLE plan_shopping_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id           INTEGER NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    ingredient_id     INTEGER NOT NULL REFERENCES ingredients(id),
    package_id        INTEGER NOT NULL REFERENCES ingredient_packages(id),
    packages_bought   INTEGER NOT NULL CHECK (packages_bought > 0),
    qty_needed        REAL NOT NULL,                         -- base units used across the plan
    qty_leftover      REAL NOT NULL CHECK (qty_leftover >= 0),
    cost_cents        INTEGER NOT NULL,
    is_checked        INTEGER NOT NULL DEFAULT 0 CHECK (is_checked IN (0, 1)),  -- shopping-list checkbox
    UNIQUE (plan_id, package_id)
);
 
-- ---------------------------------------------------------------------------
-- REVIEWS (after a family has actually cooked a recipe)
-- recipe_feedback above is the quick swap-time reaction while planning.
-- recipe_reviews is the considered rating after dinner. One row per user and
-- recipe, updated in place, so the planner always sees the latest opinion.
-- ---------------------------------------------------------------------------
 
CREATE TABLE recipe_reviews (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id         INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    plan_day_id       INTEGER REFERENCES plan_days(id) ON DELETE SET NULL,  -- the night it was cooked
    stars             INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    comment           TEXT,
    repeat_frequency  TEXT NOT NULL CHECK (repeat_frequency IN
                        ('never', 'rarely', 'monthly', 'every_other_week', 'weekly')),
        -- "Would you eat this again, and how often?"
        -- The planner turns this into a cooldown before the recipe can return:
        --   never -> excluded for good    rarely -> 90 days     monthly -> 28 days
        --   every_other_week -> 14 days   weekly -> 7 days
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, recipe_id)
);
 
-- Average rating per recipe across all families (optional objective bonus later)
CREATE VIEW recipe_rating_stats AS
SELECT recipe_id,
       COUNT(*)                AS review_count,
       ROUND(AVG(stars), 2)    AS avg_stars
FROM recipe_reviews
GROUP BY recipe_id;
 
-- ---------------------------------------------------------------------------
-- INDEXES (the optimizer's candidate-pool query touches these constantly)
-- ---------------------------------------------------------------------------
 
CREATE INDEX idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id);
CREATE INDEX idx_recipe_tags_tag               ON recipe_tags(tag_id);
CREATE INDEX idx_recipes_prep                  ON recipes(prep_minutes);
CREATE INDEX idx_packages_ingredient           ON ingredient_packages(ingredient_id);
CREATE INDEX idx_feedback_user                 ON recipe_feedback(user_id, scope);
CREATE INDEX idx_plan_days_plan                ON plan_days(plan_id);
CREATE INDEX idx_reviews_user                  ON recipe_reviews(user_id, repeat_frequency);
CREATE INDEX idx_reviews_recipe                ON recipe_reviews(recipe_id);
 
-- ---------------------------------------------------------------------------
-- REFERENCE QUERY: candidate recipe pool for one user (run before the solver)
-- Hard filters: prep time, excluded ingredients, "never" dislikes, this plan's
-- weekly dislikes, and preferred protein/cuisine tags.
-- :user_id, :plan_id, :max_prep, :today are bound parameters.
-- ---------------------------------------------------------------------------
--
-- SELECT r.id
-- FROM recipes r
-- WHERE r.prep_minutes <= :max_prep
--   AND NOT EXISTS (                                   -- no excluded ingredients
--         SELECT 1 FROM recipe_ingredients ri
--         JOIN user_excluded_ingredients ue ON ue.ingredient_id = ri.ingredient_id
--         WHERE ri.recipe_id = r.id AND ue.user_id = :user_id)
--   AND NOT EXISTS (                                   -- no disliked recipes
--         SELECT 1 FROM recipe_feedback f
--         WHERE f.recipe_id = r.id AND f.user_id = :user_id AND f.rating = 'dislike'
--           AND (f.scope = 'never' OR f.plan_id = :plan_id))
--   AND NOT EXISTS (                                   -- reviewed "never again"
--         SELECT 1 FROM recipe_reviews rv
--         WHERE rv.recipe_id = r.id AND rv.user_id = :user_id AND rv.repeat_frequency = 'never')
--   AND NOT EXISTS (                                   -- still inside its repeat cooldown
--         SELECT 1 FROM recipe_reviews rv
--         JOIN plan_days pd ON pd.recipe_id = rv.recipe_id
--         JOIN meal_plans mp ON mp.id = pd.plan_id AND mp.user_id = rv.user_id AND mp.status = 'confirmed'
--         WHERE rv.recipe_id = r.id AND rv.user_id = :user_id
--           AND pd.day_date > date(:today, '-' || CASE rv.repeat_frequency
--                 WHEN 'rarely' THEN 90 WHEN 'monthly' THEN 28
--                 WHEN 'every_other_week' THEN 14 ELSE 7 END || ' days'))
--   AND EXISTS (                                       -- protein the family is OK with
--         SELECT 1 FROM recipe_tags rt
--         JOIN tags t ON t.id = rt.tag_id AND t.type = 'protein'
--         JOIN user_preferred_tags up ON up.tag_id = t.id AND up.user_id = :user_id
--         WHERE rt.recipe_id = r.id)
--   AND EXISTS (                                       -- matches a selected cuisine/style
--         SELECT 1 FROM recipe_tags rt
--         JOIN tags t ON t.id = rt.tag_id AND t.type IN ('cuisine', 'style')
--         JOIN user_preferred_tags up ON up.tag_id = t.id AND up.user_id = :user_id
--         WHERE rt.recipe_id = r.id);
 