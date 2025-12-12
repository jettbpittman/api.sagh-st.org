import json
import psycopg2
from datetime import datetime


with open("creds.json", "r") as f:
    creds = json.load(f)

con = psycopg2.connect(
            user=creds["database"]["username"],
            password=creds["database"]["password"],
            database=creds["database"]["database"],
            host=creds["database"]["host"],
            port="5432",
        )

cur = con.cursor()

cur.execute("SELECT * FROM swimmers")

swimmers = cur.fetchall()

today = datetime.today()

for swimmer in swimmers:
    print(swimmer)
    if swimmer[11] is None:
        continue
    try:
        birthday = datetime.strptime(swimmer[11], '%Y-%m-%d')
    except ValueError:
        break
    age_dt = today - birthday
    age = int(age_dt.days / 365)
    print(age)
    if age != swimmer[4]:
        print("changing age...")
        cur.execute("UPDATE swimmers SET age = %s WHERE id = %s", (age, swimmer[0]))
        con.commit()
