from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN mpin VARCHAR(10) NULL"))
        print("Added mpin")
    except Exception as e:
        pass

    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN securityAnswer VARCHAR(255) NULL"))
        print("Added securityAnswer")
    except Exception as e:
        pass

    conn.commit()
    print("Migration complete!")
