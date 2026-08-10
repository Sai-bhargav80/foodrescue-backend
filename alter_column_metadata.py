import pymysql

connection = pymysql.connect(
    host="localhost",
    user="root",
    password="saibhargav123",
    database="food_rescue"
)

try:
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE player_behavior_logs CHANGE COLUMN metadata extra_metadata JSON DEFAULT NULL;")
        print("[+] Renamed column metadata to extra_metadata in player_behavior_logs successfully!")
    connection.commit()
finally:
    connection.close()
