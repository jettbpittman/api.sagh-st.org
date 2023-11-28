import psycopg2
import json
from datetime import datetime

date = datetime.now()

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

cur.execute("SELECT * FROM swimmers WHERE active = true AND manager = false ORDER BY last_name, first_name")
swimmers = cur.fetchall()

cur.execute("SELECT * FROM meets WHERE most_recent = 1")
MEET = cur.fetchone()
print(f"{MEET[1]} - {MEET[4]}")

cur.execute("SELECT * FROM events")
events = cur.fetchall()

for swimmer in swimmers:
    print(f"{swimmer[3]}, {swimmer[1]} {swimmer[2]}")
    for event in events:
        cur.execute(f"SELECT * FROM entries WHERE swimmer = {swimmer[0]} AND event = '{event[0]}' AND ignored = false ORDER BY time")
        entry = cur.fetchone()
        if not entry:
            continue
        if entry[2] == MEET[0]:
            print(f"PR - {event[0]} - {entry[5]}")