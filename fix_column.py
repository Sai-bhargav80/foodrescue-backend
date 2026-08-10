from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SHOW COLUMNS FROM food_listings LIKE 'imageUrl'"))
    row = result.fetchone()
    print(f"Column: {row[0]}, Type: {row[1]}, Null: {row[2]}")
    print("SUCCESS - column is now:", row[1])
