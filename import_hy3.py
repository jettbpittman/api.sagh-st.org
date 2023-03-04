import json
import sqlite3
import pprint
import datetime
import random
import time

FILE = "285a2020"
MEET = 20239628042240
TEAM = "SAGH"

with open(f"{FILE}.json", "r") as f:
    mm_json = json.load(f)


def format_time(time):
    t = str(time).split(".")
    s = t[0]
    ms = t[1]
    if int(s) >= 60:
        m, s = divmod(int(s), 60)
        if len(ms) == 1:
            ms = ms.ljust(2, "0")
        if len(str(s)) == 1:
            s = str(s).rjust(2, "0")
        return f"{m}:{s}.{ms}"
    else:
        return f"{s}.{ms}"


def generate_id(id_type: int, year: int = 0, join_date: int = None) -> int:
    """

    :param year: integer - Graduation Year
    :param id_type: integer - 1: Swimmer, 2: Meet, 3: Entry, 4: Team
    :param join_date: integer - UNIX timestamp for when the swimmer joined the team
    :return:
    """
    if join_date:
        ts = join_date
        # Set epoch to 1 September, 2014 00:00:00+0000
        ts = ts - 1409547600
    else:
        ts = int(datetime.datetime.utcnow().timestamp())
        # Set epoch to 1 September, 2014 00:00:00+0000
        ts = ts - 1409547600
    return (
        (int(ts) << 16)
        + (year << 20)
        + (id_type << 24)
        + (random.randint(1, 1000) << 32)
    )


def assemble_event_code(e):
    code = ""
    if e["gender"] == "Gender.FEMALE":
        code += "F"
    if e["gender"] == "Gender.MALE":
        code += "M"
    if e["relay"]:
        dist = int(e["distance"] / 4)
        code += str(dist)
    else:
        code += str(e["distance"])
    if e["stroke"] == "Stroke.FREESTYLE":
        code += "F"
    if e["stroke"] == "Stroke.BACKSTROKE":
        code += "B"
    if e["stroke"] == "Stroke.BREASTSTROKE":
        code += "S"
    if e["stroke"] == "Stroke.BUTTERFLY":
        code += "L"
    if e["stroke"] == "Stroke.MEDELY":
        code += "M"
    return code


events = mm_json["events"]
m = []

for event in events:
    ev = events[event]
    event_code = assemble_event_code(ev)
    for entry in ev["entries"]:
        try:
            if entry["swimmers"][0]["team_code"] == TEAM:
                if entry["relay"]:
                    if event_code[-1] == "M":
                        event_code = event_code[:-1] + "B"
                    swimmer = entry["swimmers"][0]
                    ptime = None
                    ftime = None
                    if entry["prelim_splits"]:
                        splits = list(entry["prelim_splits"].values())
                        splits.sort()
                        print(splits)
                        if ev["distance"] == 200:
                            ptime = splits[0]
                            psplits = []
                        if ev["distance"] == 400:
                            ptime = splits[1]
                            psplits = [splits[0], splits[1]]
                        if ev["distance"] == 800:
                            ptime = splits[3]
                            psplits = [splits[0], splits[1], splits[2], splits[3]]
                    if entry["finals_splits"]:
                        splits = list(entry["finals_splits"].values())
                        splits.sort()
                        print(splits)
                        if ev["distance"] == 200:
                            ftime = splits[0]
                            fsplits = []
                        if ev["distance"] == 400:
                            ftime = splits[1]
                            fsplits = [splits[0], splits[1]]
                        if ev["distance"] == 800:
                            ftime = splits[3]
                            fsplits = [splits[0], splits[1], splits[2], splits[3]]
                    if ptime:
                        m.append(
                            {
                                "name": f"{swimmer['last_name']}, {swimmer['first_name']}",
                                "usa_swimming_id": swimmer["usa_swimming_id"],
                                "event": event_code,
                                "seed": "RELAY_LEADOFF",
                                "time": format_time(ptime),
                                "splits": psplits,
                            }
                        )
                    if ftime:
                        m.append(
                            {
                                "name": f"{swimmer['last_name']}, {swimmer['first_name']}",
                                "usa_swimming_id": swimmer["usa_swimming_id"],
                                "event": event_code,
                                "seed": "RELAY_LEADOFF",
                                "time": format_time(ftime),
                                "splits": fsplits,
                            }
                        )
                else:
                    swimmer = entry["swimmers"][0]
                    if entry["prelim_time"]:
                        splits = list(entry["prelim_splits"].values())
                        splits.sort()
                        m.append(
                            {
                                "name": f"{swimmer['last_name']}, {swimmer['first_name']}",
                                "usa_swimming_id": swimmer["usa_swimming_id"],
                                "event": event_code,
                                "seed": format_time(entry["seed_time"]),
                                "time": format_time(entry["prelim_time"]),
                                "splits": splits,
                            }
                        )
                    if entry["finals_time"]:
                        if entry["prelim_time"]:
                            seed = entry["prelim_time"]
                        else:
                            seed = entry["seed_time"]
                        splits = list(entry["finals_splits"].values())
                        splits.sort()
                        m.append(
                            {
                                "name": f"{swimmer['last_name']}, {swimmer['first_name']}",
                                "usa_swimming_id": swimmer["usa_swimming_id"],
                                "event": event_code,
                                "seed": format_time(seed),
                                "time": format_time(entry["finals_time"]),
                                "splits": splits,
                            }
                        )
            else:
                continue
        except IndexError:
            continue

for result in m:
    con = sqlite3.connect("db.sqlite3")
    c = con.execute(
        f"SELECT id FROM swimmers WHERE usas_id = '{result['usa_swimming_id']}'"
    )
    r = c.fetchone()
    c.close()
    if r:
        id = str(r[0])
    else:
        name = result["name"].split(",")
        l_name = name[0].strip()
        f_name = name[1].strip()
        c = con.execute(
            f"SELECT id FROM swimmers WHERE last_name = '{l_name}' AND first_name = '{f_name}'"
        )
        r = c.fetchone()
        try:
            id = str(r[0])
        except TypeError:
            print(f"Unable to locate {result['name']}")
            continue
        c.close()
    pprint.pprint(f"{result['name']} - {id}")
    pprint.pprint(result)
    splits = json.dumps(result["splits"])
    con.execute(
        "INSERT INTO entries (id, swimmer, meet, event, seed, time, splits) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            generate_id(3),
            id,
            MEET,
            result["event"],
            result["seed"],
            result["time"],
            splits,
        ],
    )
    con.commit()
    time.sleep(1)
