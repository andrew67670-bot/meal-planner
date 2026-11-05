import sqlite3

conn = sqlite3.connect("meal_planner.db")
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
).fetchall()

for (name,) in tables:
    print(name)

conn.close()