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

cur = con.cursor()


def sort_by_time(s):
    t = s[5]
    x = re.search("[0-9]+:[0-9]+\.[0-9]+", str(t))
    if not x:
        return "0:" + t
    else:
        return t


cur.execute("SELECT * FROM swimmers WHERE active = true AND manager = false ORDER BY last_name, first_name")
swimmers = cur.fetchall()

cur.execute("SELECT * FROM meets WHERE most_recent = 1")
MEET = cur.fetchone()
print(f"{MEET[1]} - {MEET[4]}")

cur.execute("SELECT * FROM events")
events = cur.fetchall()

out = ""
num = 0

for swimmer in swimmers:
    out1 = ""
    num1 = 0
    out1 += f"{swimmer[3]}, {swimmer[1]} {swimmer[2]}\n"
    for event in events:
        cur.execute(f"SELECT * FROM entries WHERE swimmer = {swimmer[0]} AND event = '{event[0]}' AND ignored = false")
        entries = cur.fetchall()
        if not entries:
            continue
        entries.sort(key=sort_by_time)
        entry = entries[0]
        if entry[2] == MEET[0]:
            out1 += f"{event[0]} - {entry[5]}\n"
            num += 1
            num1 += 1
    if num1 > 0:
        out += out1 + "\n"

print(out + f"TOTAL PRs - {num}")

html = f"""
<html>
    <body style="text-align: center; margins: auto;">
        <h2>Personal Bests</h2>
        <h3>PRs from {MEET[1]}</h3>
        <pre style="font-size: small; text-align: left">{out + f"TOTAL PRs - {num}"}</pre>
        <p>GENERATED: {datetime.now().strftime("%m/%d/%Y %H:%M:%S")}</p>
        <p>ghmvswim.org</p>
    </body>
</html>
"""

pdfkit.from_string(html, f"{MEET[0]}-prs.pdf")