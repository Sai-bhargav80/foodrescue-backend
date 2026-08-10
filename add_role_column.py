import pymysql

print("Running database column migration for USER ROLE...")
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="saibhargav123",
    database="food_rescue"
)

try:
    with connection.cursor() as cursor:
        # Add role column to users table
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'USER'")
            print("[+] Added 'role' column to 'users' table successfully!")
        except Exception as e:
            print("[-] 'role' column update:", e)

        # Seed admin user
        try:
            cursor.execute("""
                INSERT INTO users (email, password, fullName, phoneNumber, points, level, rescuesCount, donationsCount, totalCarbonSaved, provider, role)
                VALUES ('admin@foodrescue.com', 'Admin@1234', 'System Administrator', '9999999999', 999, 10, 0, 0, 0.0, 'local', 'ADMIN')
                ON DUPLICATE KEY UPDATE role='ADMIN'
            """)
            print("[+] Seeded admin@foodrescue.com as ADMIN successfully!")
        except Exception as e:
            print("[-] Admin seed failure:", e)

    connection.commit()
    print("Database migration completed!")
finally:
    connection.close()
