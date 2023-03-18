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
    birthday = datetime.strptime(swimmer['dob'], '%Y-%m-%d')
    age_dt = today - birthday
    age = int(age_dt.days / 365)
    print(age)
    if age != swimmer['age']:
        print("changing age...")
        cur.execute("UPDATE swimmers SET age = %s WHERE id = %s", (age, swimmer['id']))
        con.commit()
