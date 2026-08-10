import pymysql

print("Running database migration for PHASE 2: BEHAVIOR MONITORING & ANOMALY DETECTION...")
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="saibhargav123",
    database="food_rescue"
)

try:
    with connection.cursor() as cursor:
        # Add trust_score and last_known_location to users
        columns_to_add = [
            ("trust_score", "INT NOT NULL DEFAULT 100"),
            ("last_known_location", "VARCHAR(255) DEFAULT NULL")
        ]
        
        for col_name, col_def in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                print(f"[+] Added '{col_name}' column to 'users' table successfully!")
            except Exception as e:
                print(f"[-] '{col_name}' column update: {e}")

        # Create player_behavior_logs table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_behavior_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    player_id INT NOT NULL,
                    action_type VARCHAR(100) NOT NULL,
                    timestamp DATETIME NOT NULL,
                    location VARCHAR(255) DEFAULT NULL,
                    suspicion_score FLOAT NOT NULL DEFAULT 0.0,
                    metadata JSON DEFAULT NULL,
                    FOREIGN KEY (player_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            print("[+] Created 'player_behavior_logs' table successfully!")
        except Exception as e:
            print("[-] 'player_behavior_logs' table creation failure:", e)

    connection.commit()
    print("Database migration completed!")
finally:
    connection.close()
