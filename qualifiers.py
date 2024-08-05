import psycopg2
import json
import pdfkit
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

meet = input("Meet ID: ")
num_of_qualifiers = int(input("Number of Qualifiers per Event: "))

qualifiers = ""

cur.execute(f"SELECT DISTINCT event FROM entries WHERE meet = {meet}")
events = cur.fetchall()

for event in events:
    cur.execute(f"SELECT * FROM events WHERE code = '{event[0]}'")
    ev = cur.fetchone()
    if ev[5] == "M":
        g = "Men's"
    if ev[5] == "F":
        g = "Women's"
    qualifiers1 = f"{g} {ev[1]}\n====================\n"
    ecount = 0
    cur.execute(f"SELECT * FROM entries WHERE event = '{ev[0]}' AND meet = {meet} AND place BETWEEN 1 AND {num_of_qualifiers} ORDER BY place")
    q = cur.fetchall()
    for entry in q:
        ecount += 1
        cur.execute(f"SELECT * FROM swimmers WHERE id = {entry[1]}")
        sw = cur.fetchone()
        qualifiers1 += f"{sw[3]}, {sw[1]} {sw[2].strip()} - {entry[3]} - {entry[10]} - {entry[5]}\n"
    qualifiers1 += "\n"
    if ecount > 0:
        qualifiers += qualifiers1


print(qualifiers)

html = f"""
<html>
    <body style="text-align: center; margins: auto;">
        <h2>QUALIFIERS</h2>
        <h3>Top {num_of_qualifiers} from {meet}</h3>
        <pre style="font-size: small; text-align: left">{qualifiers}</pre>
        <p>GENERATED: {datetime.now().strftime("%m/%d/%Y %H:%M:%S")}</p>
        <p>sagh-st.org</p>
    </body>
</html>
"""

pdfkit.from_string(html, f"{meet[0]}-qualifiers.pdf")
"""
cur.execute(f"SELECT * FROM entries WHERE meet = {meet}")
entries = cur.fetchall()

for entry in entries:
    if entry[10] is None:
        continue
    else:
        if 0 < entry[10] <= num_of_qualifiers:
            qualifiers.append(list(entry))

qualifiers.sort(key=lambda x: x[1])

for s in qualifiers:
    cur.execute(f"SELECT * FROM swimmers WHERE id = {s[1]}")
    sw = cur.fetchone()
    print(f"{sw[3]}, {sw[1]} {sw[2].strip()} - {s[3]} - {s[10]} - {s[5]}")
"""