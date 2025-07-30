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

c = cur.execute("""SELECT * FROM swimmers WHERE active = true""")
swimmers = cur.fetchall()

count = dict()
tiscas = {}

out = ""

for swimmer in swimmers:
    events = []
    best_times = {}
    name = f"{swimmer[3]}, {swimmer[1]} {swimmer[2]}"
    cur.execute(f"SELECT * FROM entries WHERE swimmer = {swimmer[0]} AND ignored = false ORDER BY time")
    l = cur.fetchall()
    for entry in l:
        if str(entry[7]).startswith("TISCA-24"):
            if entry[3] in events:
                if best_times[entry[3]] > entry[5]:
                    best_times[entry[3]] = entry[5]
                else:
                    continue
            else:
                events.append(entry[3])
                best_times[entry[3]] = entry[5]
            cur.execute(f"SELECT name, startdate, host FROM meets WHERE id = {entry[2]}")
            m = cur.fetchone()
            try:
                tiscas[name].append({"event": entry[3], "time": entry[5], "meet": m[0], "year": m[1][:-4], "host": m[2]})
            except KeyError:
                tiscas[name] = [{"event": entry[3], "time": entry[5], "meet": m[0], "year": m[1][:-4], "host": m[2]}]

myKeys = list(tiscas.keys())
myKeys.sort()
sorted_tiscas = {i: tiscas[i] for i in myKeys}


output = f""

for i in sorted_tiscas:
    output += i + "\n===========\n"
    for e in tiscas[i]:
        output += f"{e['event']}  -  {e['time']}  -  {e['year']} {e['host']} {e['meet']}\n"
    output += "\n"

html = f"""
<html>
    <body style="text-align: center; margins: auto;">
        <h2>TISCA Qualifiers (as of {date.day} {date.strftime('%B')[0:3].upper()} {date.year})</h2>
        <pre style="font-size: small; text-align: left">{output}</pre>
        <p>GENERATED: {datetime.now().strftime("%m/%d/%Y %H:%M:%S")}</p>
        <p>ghmvswim.org</p>
    </body>
</html>
"""

pdfkit.from_string(html, f"tisca_qualifiers.pdf")
