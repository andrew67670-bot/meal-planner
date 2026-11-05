# Created with help from Claude (Anthropic's AI assistant), claude.ai, 2026-11-05.
# Purpose: database seed data / database setup / table check script.import sqlite3

conn = sqlite3.connect("meal_planner.db")
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
).fetchall()

for (name,) in tables:
    print(name)

conn.close()