import pymysql

print("Running database column migration for USER MODERATION...")
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="saibhargav123",
    database="food_rescue"
)

try:
    with connection.cursor() as cursor:
        # Add columns to users table
        columns_to_add = [
            ("status", "VARCHAR(50) NOT NULL DEFAULT 'Active'"),
            ("banReason", "TEXT DEFAULT NULL"),
            ("banExpires", "DATETIME DEFAULT NULL"),
            ("warningCount", "INT NOT NULL DEFAULT 0"),
            ("isBanned", "TINYINT(1) NOT NULL DEFAULT 0")
        ]
        
        for col_name, col_def in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                print(f"[+] Added '{col_name}' column to 'users' table successfully!")
            except Exception as e:
                print(f"[-] '{col_name}' column update: {e}")

        # Create audit_logs table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_id INT NOT NULL,
                    action VARCHAR(255) NOT NULL,
                    target_id VARCHAR(255) DEFAULT NULL,
                    reason TEXT DEFAULT NULL,
                    timestamp DATETIME NOT NULL,
                    details TEXT DEFAULT NULL,
                    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            print("[+] Created 'audit_logs' table successfully!")
        except Exception as e:
            print("[-] 'audit_logs' table creation failure:", e)

    connection.commit()
    print("Database migration completed!")
finally:
    connection.close()
