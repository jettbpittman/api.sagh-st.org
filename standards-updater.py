import psycopg2
import json

with open("creds.json", "r") as f:
    creds = json.load(f)

standards = ["USAS-BB", "USAS-A", "USAS-AA", "USAS-SS"]

events = [
    "F200F",
    "F200M",
    "F50F",
    "F100L",
    "F100F",
    "F500F",
    "F100B",
    "F100S",
    "M200F",
    "M200M",
    "M50F",
    "M100L",
    "M100F",
    "M500F",
    "M100B",
    "M100S",
]


def format_time(e):
    if len(e) <= 5:
        adjusted_t = f"0:{e}"
        return adjusted_t
    else:
        return e


con = psycopg2.connect(
            user=creds["database"]["username"],
            password=creds["database"]["password"],
            database=creds["database"]["database"],
            host=creds["database"]["host"],
            port="5432",
        )

cur = con.cursor()


for event in events:
    for standard in standards:
        code = f"{standard}-{event}"
        cur.execute(f"SELECT * FROM standards WHERE code = '{code}'")
        row = cur.fetchone()
        print(row)
        try:
            min_time = format_time(row[3])
        except:
            continue

        cur.execute(f"SELECT * FROM entries WHERE event = '{event}'")
        rows = cur.fetchall()

        for entry in rows:
            print(entry)
            t = format_time(entry[5])
            if t <= min_time:
                print(f"{t} <= {min_time}")
                e = cur.execute(
                    f"UPDATE entries SET standards = '{code}' WHERE id = '{entry[0]}'"
                )
                con.commit()
                print(f"Set {event} {entry[1]} ({entry[5]}) to {code}")
            else:
                continue
