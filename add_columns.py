import pymysql

print("Running database column migration...")
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="saibhargav123",
    database="food_rescue"
)

try:
    with connection.cursor() as cursor:
        # Add latitude
        try:
            cursor.execute("ALTER TABLE food_listings ADD COLUMN latitude DOUBLE DEFAULT 13.0827")
            print("[+] Added latitude column successfully!")
        except Exception as e:
            print("[-] latitude column update:", e)

        # Add longitude
        try:
            cursor.execute("ALTER TABLE food_listings ADD COLUMN longitude DOUBLE DEFAULT 80.2707")
            print("[+] Added longitude column successfully!")
        except Exception as e:
            print("[-] longitude column update:", e)

        # Add claimed_at
        try:
            cursor.execute("ALTER TABLE food_listings ADD COLUMN claimed_at DATETIME DEFAULT NULL")
            print("[+] Added claimed_at column successfully!")
        except Exception as e:
            print("[-] claimed_at column update:", e)
    connection.commit()
    print("Database migration completed!")
finally:
    connection.close()
