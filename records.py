import psycopg2
import json
import pdfkit
import re
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


def sortByTime(e):
    if len(e["time"]) <= 5:
        adjusted_t = f"0:{e['time']}"
        return adjusted_t
    else:
        return e["time"]


cur = con.cursor()

cur.execute("SELECT * FROM events ORDER BY relay, stroke, distance")
events = cur.fetchall()
ec = len(events)
ce = 1

body = ""

for event in events:
    print(f"{ce}/{ec}")
    code = event[0]
    entries = []
    body += f"\n{event[5]} {event[1]}\n=================="
    cur.execute(f"SELECT * FROM entries WHERE event = '{code}' AND ignored = false")
    swims = cur.fetchall()
    counter = 1
    for swim in swims:
        cur.execute(f"SELECT last_name, first_name, middle_name FROM swimmers WHERE id = {swim[1]}")
        swimmer = cur.fetchone()
        if swim[8]:
            cur.execute(f"SELECT swimmer_1, swimmer_2, swimmer_3, swimmer_4 FROM relays WHERE entry = {swim[0]}")
            relay = cur.fetchone()
            try:
                counter = 0
                board_name = ""
                while counter < 4:
                    cur.execute(f"SELECT last_name, first_name, middle_name FROM swimmers WHERE id = {relay[counter]}")
                    name = cur.fetchone()
                    board_name += f"\n{counter + 1}) {name[0]}, {name[1]} {name[2]}"
                    counter += 1
                board_name = board_name.strip()
            except TypeError:
                board_name = f"{swimmer[0]}, {swimmer[1]} {swimmer[2]}"
        else:
            board_name = f"{swimmer[0]}, {swimmer[1]} {swimmer[2]}"
        entries.append({"name": board_name, "time": swim[5]})
    entries.sort(key=sortByTime)
    try:
        body += f"\n{entries[0]['name']}\n{entries[0]['time']}"
        counter += 1
    except IndexError:
        pass
    ce += 1

with open("records.txt", "w") as f:
    f.write(body)
