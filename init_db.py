# Created with help from Claude (Anthropic's AI assistant), claude.ai, 2026-11-05.
# Purpose: database seed data / database setup / table check script.
import os
import sqlite3

DB = "meal_planner.db"

# During development, start fresh each time
if os.path.exists(DB):
    os.remove(DB)

with open("schema.sql") as f:
    schema = f.read()

conn = sqlite3.connect(DB)
conn.executescript(schema)
conn.commit()
conn.close()

print("Database created.")