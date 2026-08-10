import models
from database import engine

print("Resetting database...")
# This will drop all tables and recreate them based on current models.py
# WARNING: All existing data will be lost!
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)
print("Database reset successfully! All tables recreated with correct columns.")
