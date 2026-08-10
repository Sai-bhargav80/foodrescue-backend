import pymysql
c = pymysql.connect(host='localhost', user='root', password='saibhargav123', database='food_rescue')
cur = c.cursor()
cur.execute("SELECT id, email, role, password FROM users WHERE role='ADMIN'")
rows = cur.fetchall()
for row in rows:
    print(row)
if not rows:
    print("No ADMIN users found!")
    cur.execute("SELECT id, email, role FROM users LIMIT 10")
    for r in cur.fetchall():
        print("  ", r)
c.close()
