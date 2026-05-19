import sqlite3
conn = sqlite3.connect('dairy_farm.db')

# Fix sample cows (ids 46-55) to user_id = 0
conn.execute("UPDATE cows SET user_id = 0 WHERE id IN (46,47,48,49,50,51,52,53,54,55)")
conn.execute("UPDATE milk_records SET user_id = 0 WHERE cow_id IN (46,47,48,49,50,51,52,53,54,55)")
conn.execute("UPDATE health_records SET user_id = 0 WHERE cow_id IN (46,47,48,49,50,51,52,53,54,55)")
conn.execute("UPDATE alerts SET user_id = 0 WHERE cow_id IN (46,47,48,49,50,51,52,53,54,55)")
conn.commit()

# Verify
rows = conn.execute("SELECT id, user_id, name, tag_number FROM cows").fetchall()
for r in rows:
    print(r)
conn.close()
print('Done!')