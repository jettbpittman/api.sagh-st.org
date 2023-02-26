import sqlite3

standards = [
    "USAS-BB",
    "USAS-A",
    "USAS-AA",
    "USAS-SS"
]

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
    "M100S"
]


def format_time(e):
    if len(e) <= 5:
        adjusted_t = f"0:{e}"
        return adjusted_t
    else:
        return e


for event in events:
    for standard in standards:

        con = sqlite3.connect("db.sqlite3")

        code = f"{standard}-{event}"

        s = con.execute("SELECT * FROM standards WHERE code = ?", [code])
        row = s.fetchone()
        print(row)
        try:
            min_time = format_time(row[3])
        except:
            continue

        times = con.execute(
            "SELECT * FROM entries WHERE event = ?", [event]
        )
        rows = times.fetchall()

        for entry in rows:
            print(entry)
            t = format_time(entry[5])
            if t <= min_time:
                print(f"{t} <= {min_time}")
                e = con.execute("UPDATE entries SET standards = ? WHERE id = ?", [code, entry[0]])
                con.commit()
                print(f"Set {event} {entry[1]} ({entry[5]}) to {code}")
            else:
                continue

