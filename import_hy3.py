import json
import psycopg2
import pprint
import datetime
import random
import time

FILE = "r85a"
MEET = 21274392002560
TEAM = "SAGH"
SHORTNAME = "GHMV"

with open(f"{FILE}.json", "r") as f:
    mm_json = json.load(f)

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


def assemble_event_code(e, split):
    code = ""
    if e["gender"] == "Gender.FEMALE":
        code += "F"
    if e["gender"] == "Gender.MALE":
        code += "M"
    if e["relay"] and split:
        dist = int(e["distance"] / 4)
        code += str(dist)
    elif e['relay']:
        code += str(e["distance"]) + "R"
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


events = mm_json["meet"]["events"]
m = []

for event in events:
    ev = events[event]
    event_code = assemble_event_code(ev, False)
    for entry in ev["entries"]:
        try:
            if entry["swimmers"][0]["team_code"] == TEAM:
                if entry["relay"]:
                    lead_event_code = assemble_event_code(ev, True)
                    if lead_event_code[-1] == "M":
                        lead_event_code = assemble_event_code(ev, True)[:-1] + "B"
                    lead_swimmer = entry["swimmers"][0]
                    swimmers = entry['swimmers']
                    lead_ptime = None
                    lead_ftime = None
                    if entry["prelim_splits"]:
                        psplits = list(entry["prelim_splits"].values())
                        psplits.sort()
                        print(psplits)
                        if ev["distance"] == 200:
                            lead_ptime = psplits[0]
                            lead_psplits = []
                        if ev["distance"] == 400:
                            lead_ptime = psplits[1]
                            lead_psplits = [psplits[0], psplits[1]]
                        if ev["distance"] == 800:
                            lead_ptime = psplits[3]
                            lead_psplits = [psplits[0], psplits[1], psplits[2], psplits[3]]
                        ptime = format_time(entry['prelim_time'])
                    if entry["finals_splits"]:
                        fsplits = list(entry["finals_splits"].values())
                        fsplits.sort()
                        print(fsplits)
                        if ev["distance"] == 200:
                            lead_ftime = fsplits[0]
                            lead_fsplits = []
                        if ev["distance"] == 400:
                            lead_ftime = fsplits[1]
                            lead_fsplits = [fsplits[0], fsplits[1]]
                        if ev["distance"] == 800:
                            lead_ftime = fsplits[3]
                            lead_fsplits = [fsplits[0], fsplits[1], fsplits[2], fsplits[3]]
                        ftime = format_time(entry['finals_time'])
                    if lead_ptime:
                        if entry["prelim_time_code"] == "WithTimeTimeCode.DISQUALIFICATION":
                            continue
                        m.append(
                            {
                                "name": f"{lead_swimmer['last_name']}, {lead_swimmer['first_name']}",
                                "usa_swimming_id": lead_swimmer["usa_swimming_id"],
                                "event": lead_event_code,
                                "seed": "RELAY_LEADOFF",
                                "time": format_time(lead_ptime),
                                "splits": lead_psplits,
                                "swimmers": None
                            })
                        m.append({
                            "name": f"{SHORTNAME}, {entry['relay_team_id']}",
                            "usa_swimming_id": "",
                            "event": event_code,
                            "seed": format_time(entry['seed_time']),
                            "time": ptime,
                            "splits": psplits,
                            "swimmers": swimmers
                        })
                    if lead_ftime:
                        if entry["finals_time_code"] == "WithTimeTimeCode.DISQUALIFICATION":
                            continue
                        m.append(
                            {
                                "name": f"{lead_swimmer['last_name']}, {lead_swimmer['first_name']}",
                                "usa_swimming_id": lead_swimmer["usa_swimming_id"],
                                "event": lead_event_code,
                                "seed": "RELAY_LEADOFF",
                                "time": format_time(lead_ftime),
                                "splits": lead_fsplits,
                                "swimmers": None
                            }
                        )
                        if entry["prelim_time"]:
                            seed = format_time(entry["prelim_time"])
                        else:
                            seed = format_time(entry["seed_time"])
                        m.append({
                            "name": f"{SHORTNAME}, {entry['relay_team_id']}",
                            "event": event_code,
                            "usa_swimming_id": "",
                            "seed": seed,
                            "time": ftime,
                            "splits": fsplits,
                            "swimmers": swimmers
                        })
                else:
                    lead_swimmer = entry["swimmers"][0]
                    if entry["prelim_time"]:
                        if entry["prelim_time_code"] == "WithTimeTimeCode.DISQUALIFICATION":
                            continue
                        psplits = list(entry["prelim_splits"].values())
                        psplits.sort()
                        m.append(
                            {
                                "name": f"{lead_swimmer['last_name']}, {lead_swimmer['first_name']}",
                                "usa_swimming_id": lead_swimmer["usa_swimming_id"],
                                "event": event_code,
                                "seed": format_time(entry["seed_time"]),
                                "time": format_time(entry["prelim_time"]),
                                "splits": psplits,
                                "swimmers": None
                            }
                        )
                    if entry["finals_time"]:
                        if entry["finals_time_code"] == "WithTimeTimeCode.DISQUALIFICATION":
                            continue
                        if entry["prelim_time"]:
                            seed = format_time(entry["prelim_time"])
                        else:
                            seed = format_time(entry["seed_time"])
                        psplits = list(entry["finals_splits"].values())
                        psplits.sort()
                        m.append(
                            {
                                "name": f"{lead_swimmer['last_name']}, {lead_swimmer['first_name']}",
                                "usa_swimming_id": lead_swimmer["usa_swimming_id"],
                                "event": event_code,
                                "seed": seed,
                                "time": format_time(entry["finals_time"]),
                                "splits": psplits,
                                "swimmers": None
                            }
                        )
            else:
                continue
        except IndexError:
            continue

for result in m:
    c = cur.execute(
        f"SELECT id FROM swimmers WHERE usas_id = '{result['usa_swimming_id']}'"
    )
    r = cur.fetchone()
    if r:
        id = str(r[0])
    else:
        name = result["name"].split(",")
        l_name = name[0].strip()
        f_name = name[1].strip()
        c = cur.execute(
            f"SELECT id FROM swimmers WHERE last_name = '{l_name}' AND first_name = '{f_name}'"
        )
        r = cur.fetchone()
        try:
            id = str(r[0])
        except TypeError:
            print(f"Unable to locate {result['name']}")
            continue
    pprint.pprint(f"{result['name']} - {id}")
    pprint.pprint(result)
    splits = json.dumps(result["splits"])
    if result['swimmers']:
        relay = True
    else:
        relay = False
    print(relay)
    new_id = generate_id(3)
    cur.execute(
        "INSERT INTO entries (id, swimmer, meet, event, seed, time, splits, relay) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (new_id, id, MEET,
         result["event"], result["seed"], result["time"], splits, relay)
    )
    con.commit()
    if result['swimmers']:
        swimmers = []
        for swimmer in result['swimmers']:
            c = cur.execute(
                f"SELECT id FROM swimmers WHERE usas_id = '{swimmer['usa_swimming_id']}'"
            )
            r = cur.fetchone()
            if r:
                id = str(r[0])
                swimmers.append(id)
            else:
                c = cur.execute(
                    f"SELECT id FROM swimmers WHERE last_name = '{swimmer['last_name']}' AND first_name = '{swimmer['first_name']}'"
                )
                r = cur.fetchone()
                try:
                    id = str(r[0])
                    swimmers.append(id)
                except TypeError:
                    print(f"Unable to locate {result['name']}")
                    continue
        try:
            cur.execute(
                "INSERT INTO relays (entry, swimmer_1, swimmer_2, swimmer_3, swimmer_4) VALUES (%s, %s, %s, %s, %s)",
                (new_id, swimmers[0], swimmers[1], swimmers[2], swimmers[3])
            )
            con.commit()
        except:
            pass
    time.sleep(1)
