import psycopg2
import json
import sys
from datetime import datetime

date = datetime.now()

if date.month > 8:
    SEASON = str(date.year + 1)
    TISCA_YR = str(date.year)[-2:]
else:
    SEASON = str(date.year)
    TISCA_YR = str(date.year)[-2:]

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


if 12 > date.month >= 9:
    tisca = True
    standards = [["TISCA", f"T{TISCA_YR}"]]
else:
    standards = [["USA Swimming", "BB"], ["USA Swimming", "A"], ["USA Swimming", "AA"], ["USA Swimming", "SS"]]


cuts = {}

for standard in standards:
    cur.execute(f"SELECT * FROM standards WHERE"
                f" authority = '{standard[0]}' AND short_name = '{standard[1]}' AND year >= {int(SEASON)}")
    stan = cur.fetchall()
    for st in stan:
        try:
            cuts[st[5]][st[8]] = st[3]
        except KeyError:
            cuts[str(st[5])] = {}
            cuts[st[5]][st[8]] = st[3]
print(cuts)


def assemble_code(c, l):
    code = ""
    if c[0] == "T":
        code += f"TISCA-{c[-2] + c[-1]}-"
    else:
        code += f"USAS-{c}-"
    code += l
    return code


def format_time(e):
    if len(e) <= 5:
        adjusted_t = f"0:{e}"
        return adjusted_t
    else:
        return e


stan_len = len(cuts["F50F"])

ent = cur.execute(f"SELECT * FROM entries WHERE standards is null and meet in (select id from meets where season = {SEASON})")
entries = cur.fetchall()

for entry in entries:
    try:
        print(cuts[entry[3]])
    except KeyError:
        continue
    print(reversed(cuts[entry[3]]))
    for t in cuts[entry[3]]:
        if format_time(entry[5]) <= format_time(cuts[entry[3]][t]):
            print(f"{format_time(entry[5])} <= {format_time(cuts[entry[3]][t])}")
            cur.execute(
                f"UPDATE entries SET standards = '{assemble_code(t, entry[3])}' WHERE id = '{entry[0]}'"
            )
            con.commit()
        else:
            continue