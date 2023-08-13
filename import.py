#!/usr/bin/python3

import json
import psycopg2
import pprint
import datetime
import random
import time
import hytek_parser
import sys
import orjson
import attrs
from prettytable import PrettyTable as pt

TEAM = "SAGH"
SHORTNAME = "GHMV"


def sortKey(e):
    if e['finals_overall_place'] == 0:
        if e['finals_dq_info']:
            return 999999999999999
        return 999999999999998
    if e['finals_overall_place'] is None:
        if e['prelim_dq_info']:
            return 999999999999999
        else:
            return 999999999999998
    return e['finals_overall_place']


def sortEvents(e):
    return e["number"]


def gender(g):
    if g == "Gender.MALE":
        return "Mens"
    if g == "Gender.FEMALE":
        return "Womens"
    if g == "Gender.UNKNOWN":
        return "Mixed"


def course(c):
    if c == "Course.SCY":
        return "yd"
    if c == "Course.SCM" or c == "Course.LCM":
        return "m"
    if c == "Course.DQ":
        return "DQ"


def stroke(s, r):
    if s == "Stroke.FREESTYLE":
        return "Freestyle"
    if s == "Stroke.BACKSTROKE":
        return "Backstroke"
    if s == "Stroke.BREASTSTROKE":
        return "Breaststroke"
    if s == "Stroke.BUTTERFLY":
        return "Butterfly"
    if s == "Stroke.MEDELY" and r is False:
        return "Individual Medley"
    else:
        return "Medley"


def timeState(d):
    if d["dq_info"]:
        return "DQ"
    if d['time_code'] == "WithTimeTimeCode.NO_SHOW":
        return "NS"
    else:
        return d['finals_time']


def timeStatePF(d, s):
    if s == "p":
        if d["prelim_dq_info"]:
            return "DQ"
        elif d['prelim_time_code'] == "WithTimeTimeCode.NO_SHOW":
            return "NS"
        else:
            return d['prelim_time']
    if s == "f":
        if d["finals_dq_info"]:
            return "DQ"
        elif d['finals_time_code'] == "WithTimeTimeCode.NO_SHOW":
            return "NS"
        else:
            return d['finals_time']


def formatDelta(time, seed=False):
    if time == "NT" or time is None:
        return "NT"
    if seed:
        if time == "0.0" or time == 0.0:
            return "NT"
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


def niceSplits(s):
    r = ""
    for i in s:
        r += f"{formatDelta(i)}    "
    return r.strip()


def relay(r):
    if r:
        return "Relay"
    else:
        return ""


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

try:
    if sys.argv[1]:
        if isinstance(sys.argv[1], str):
            FILE = sys.argv[1]
        else:
            print("first argument must be the path to the hy3 file!")
            sys.exit()
    else:
        print("requires the following argument: 1 - path to hy3, 2 - meet ID, 3 - options (--import, --html, --text)")
        sys.exit()
except IndexError:
    print("requires the following argument: 1 - path to hy3, 2 - meet ID, 3 - options (--import, --html, --text)")
    sys.exit()

print(sys.argv)

mm = hytek_parser.parse_hy3(FILE)
d = attrs.asdict(mm)

mm_json = json.loads(orjson.dumps(
        d,
        option=orjson.OPT_NON_STR_KEYS | orjson.OPT_NAIVE_UTC | orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        default=str
    ).decode())


if "--import" in sys.argv:
    print("importing")
    try:
        if sys.argv[2]:
            if isinstance(sys.argv[2], int):
                MEET = sys.argv[2]
            else:
                print("second argument must be the meet ID!")
                sys.exit()
        else:
            print(
                "requires the following argument: 1 - path to hy3, 2 - meet ID, 3 - options (--import, --html, --text)")
            sys.exit()
    except IndexError:
        print("requires the following argument: 1 - path to hy3, 2 - meet ID, 3 - options (--import, --html, --text)")
        sys.exit()

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
                                    "seed": "RL",
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
                                    "seed": "RL",
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

if "--text" or "--html" in sys.argv:
    print("formatting")
    name = input("please enter year and meet discrim (ie 2023-154A): ")
    events = mm_json['meet']['events']
    sorted(events)

    e = []

    for event in events:
        ev = events[event]
        if ev['stroke'] == "Stroke.UNKNOWN":
            e.append({
                "name": f"Event {ev['number']} - {gender(ev['gender'])} 1 Meter Diving",
                "number": ev['number'],
                'swimmers': [], "relay": {ev['relay']}, "diving": "true"})
        else:
            e.append({
                "name": f"Event {ev['number']} - {gender(ev['gender'])} {ev['distance']}{course(ev['course'])} {stroke(ev['stroke'], ev['relay'])} {relay(ev['relay'])}",
                "number": ev['number'],
                'swimmers': [], "relay": {ev['relay']}, "diving": "false"})
        num = len(e)
        times = ev['entries']
        times.sort(key=sortKey)
        if ev['relay']:
            times.sort(key=sortKey)
            for time in times:
                try:
                    f_splits = list(time['finals_splits'].values())
                    f_splits.sort()
                except KeyError:
                    f_splits = None
                try:
                    p_splits = list(time['prelim_splits'].values())
                    p_splits.sort()
                except KeyError:
                    p_splits = None
                try:
                    prelims_time = time['prelim_time']
                except KeyError:
                    prelims_time = None
                try:
                    finals_time = time['finals_time']
                except KeyError:
                    finals_time = None
                try:
                    team_code = time['relay_swim_team_code']
                except IndexError:
                    team_code = "UN"
                team = {
                    "name": f"\'{time['relay_team_id']}\' {team_code}",
                    "team": team_code, "finals_time": formatDelta(finals_time),
                    "prelim_time": formatDelta(prelims_time),
                    "finals_splits": f_splits, "prelim_splits": p_splits,
                    "seed": formatDelta(time['seed_time'], seed=True),
                    "finals_dq_info": time['finals_dq_info'], "prelim_dq_info": time['prelim_dq_info'],
                    "finals_time_code": time['finals_time_code'], "prelim_time_code": time['prelim_time_code'],
                    "finals_place": time['finals_overall_place'], "prelim_place": time['prelim_overall_place'],
                    "swimmers": [], "relay": True}
                try:
                    for relayer in time['swimmers']:
                        team['swimmers'].append(
                            f"{relayer['last_name']}, {relayer['first_name']} {relayer['middle_initial'].strip()} {relayer['age']}")
                except IndexError:
                    pass
                e[num - 1]['swimmers'].append(team)
        elif ev['stroke'] == "Stroke.UNKNOWN":
            # diving
            times.sort(key=sortKey)
            for time in times:
                try:
                    splits = []
                    try:
                        prelims_time = time['prelim_time']
                    except KeyError:
                        prelims_time = None
                    try:
                        finals_time = time['finals_time']
                    except KeyError:
                        finals_time = None
                    swimmer = {
                        "name": f"{time['swimmers'][0]['last_name']}, {time['swimmers'][0]['first_name']} {time['swimmers'][0]['middle_initial'].strip()} {time['swimmers'][0]['age']}",
                        "team": time['swimmers'][0]['team_code'], "finals_time": finals_time,
                        "prelim_time": prelims_time,
                        "finals_splits": splits, "prelim_splits": splits, "seed": time['seed_time'],
                        "finals_dq_info": time['finals_dq_info'], "prelim_dq_info": time['prelim_dq_info'],
                        "finals_time_code": time['finals_time_code'], "prelim_time_code": time['prelim_time_code'],
                        "finals_place": time['finals_overall_place'], "prelim_place": time['prelim_overall_place'],
                        "relay": False}
                    e[num - 1]['swimmers'].append(swimmer)
                except IndexError:
                    pass
            e.sort(key=sortEvents)
        else:
            times.sort(key=sortKey)
            for time in times:
                try:
                    try:
                        f_splits = list(time['finals_splits'].values())
                        f_splits.sort()
                    except KeyError:
                        f_splits = None
                    try:
                        p_splits = list(time['prelim_splits'].values())
                        p_splits.sort()
                    except KeyError:
                        p_splits = None
                    try:
                        prelims_time = time['prelim_time']
                    except KeyError:
                        prelims_time = None
                    try:
                        finals_time = time['finals_time']
                    except KeyError:
                        finals_time = None
                    swimmer = {
                        "name": f"{time['swimmers'][0]['last_name']}, {time['swimmers'][0]['first_name']}"
                                f" {time['swimmers'][0]['middle_initial'].strip()} {time['swimmers'][0]['age']}",
                        "team": time['swimmers'][0]['team_code'], "finals_time": formatDelta(finals_time),
                        "prelim_time": formatDelta(prelims_time), "finals_splits": f_splits,
                        "prelim_splits": p_splits, "seed": formatDelta(time['seed_time'], seed=True),
                        "finals_dq_info": time['finals_dq_info'], "prelim_dq_info": time['prelim_dq_info'],
                        "finals_time_code": time['finals_time_code'], "prelim_time_code": time['prelim_time_code'],
                        "finals_place": time['finals_overall_place'], "prelim_place": time['prelim_overall_place'],
                        "relay": False}
                    e[num - 1]['swimmers'].append(swimmer)
                except IndexError:
                    pass
        times.sort(key=sortKey)
        e.sort(key=sortEvents)
    if "--champs" in sys.argv:
        for ev in e:
            tbF = pt()
            tbF.title = f"{ev['name'].strip()} - Finals"
            if ev['relay']:
                tbF.field_names = ["Place", "Name", "Team", "Prelims", "Finals"]
                for s in ev['swimmers']:
                    if s['finals_place'] is None:
                        continue
                    name1 = f"{s['name']}"
                    try:
                        name1 += f"\n1) {s['swimmers'][0]}  2) {s['swimmers'][1]}  3) {s['swimmers'][2]}  4) {s['swimmers'][3]}"
                    except:
                        pass
                    if s['finals_splits'] and s['finals_time_code'] == "WithTimeTimeCode.NORMAL":
                        name1 += f"\n{niceSplits(s['finals_splits'])}"
                    tbF.add_row([int(s['finals_place']), name1, s['team'], timeStatePF(s, "p"), timeStatePF(s, "f")])
            elif ev['diving']:
                tbF.field_names = ["Place", "Name", "Team", "Prelims", "Finals"]
                for s in ev['swimmers']:
                    if s['finals_place'] is None:
                        continue
                    tbF.add_row([s['finals_place'], s['name'], s['team'], s['prelim_time'], s['finals_time']])
            else:
                tbF.field_names = ["Place", "Name", "Team", "Prelims", "Finals"]
                for s in ev['swimmers']:
                    if s['finals_place'] is None:
                        continue
                    if s['finals_splits'] and s['finals_time_code'] == "WithTimeTimeCode.NORMAL":
                        tbF.add_row(
                            [int(s['finals_place']), f"{s['name']}\n{niceSplits(s['finals_splits'])}", s['team'],
                             timeStatePF(s, "p"),
                             timeStatePF(s, "f")])
                    else:
                        tbF.add_row(
                            [int(s['finals_place']), s['name'], s['team'], timeStatePF(s, "p"), timeStatePF(s, "f")])

            tbP = pt()
            tbP.title = f"{ev['name'].strip()} - Preliminaries"
            if ev['relay']:
                tbP.field_names = ["Place", "Name", "Team", "Seed", "Prelims"]
                for s in ev['swimmers']:
                    if not s['prelim_place']:
                        continue
                    name1 = f"{s['name']}"
                    try:
                        name1 += f"\n1) {s['swimmers'][0]}  2) {s['swimmers'][1]}  3) {s['swimmers'][2]}  4) {s['swimmers'][3]}"
                    except:
                        pass
                    if s['prelim_splits'] and s['prelim_time_code'] == "WithTimeTimeCode.NORMAL":
                        name1 += f"\n{niceSplits(s['prelim_splits'])}"
                    tbP.add_row([int(s['prelim_place']), name1, s['team'], s['seed'], timeStatePF(s, "p")])
            elif ev['diving']:
                tbP.field_names = ["Place", "Name", "Team", "Seed", "Prelims"]
                for s in ev['swimmers']:
                    tbP.add_row([int(s['prelim_place']), s['name'], s['team'], s['seed'], s['prelim_time']])
            else:
                tbP.field_names = ["Place", "Name", "Team", "Seed", "Prelims"]
                for s in ev['swimmers']:
                    pprint.pprint(s)
                    if s['prelim_splits'] and s['prelim_time_code'] == "WithTimeTimeCode.NORMAL":
                        tbP.add_row(
                            [int(s['prelim_place']), f"{s['name']}\n{niceSplits(s['prelim_splits'])}", s['team'],
                             s['seed'], timeStatePF(s, "p")])
                    else:
                        tbP.add_row([int(s['prelim_place']), s['name'], s['team'], s['seed'], timeStatePF(s, "p")])
            # print(tb)
            # print("\n")
            if "--text" in sys.argv:
                with open(f"{name}.txt", "a") as f:
                    f.write(tbF.get_string() + "\n\n" + tbP.get_string(sortby="Place") + "\n\n")
                    f.close()
            if "--html" in sys.argv:
                with open(f"{name}.html", "a") as f:
                    f.write(tbF.get_html_string() + tbP.get_html_string(sortby="Place"))
                    f.close()
        if "--html" in sys.argv:
            with open(f"{name}.html", "r") as f:
                p = f.read()
                f.close()
            with open(f"{name}.html", "w") as f:
                f.write(p)
                f.close()
    else:
        for ev in e:
            tb = pt()
            tb.title = ev['name']
            if ev['relay']:
                tb.field_names = ["Place", "Name", "Team", "Seed", "Finals"]
                for s in ev['swimmers']:
                    tb.add_row([s['finals_place'], s['name'], s['team'], s['seed'], timeStateTF(s)])
                    try:
                        tb.add_row(["",
                                    f"1) {s['swimmers'][0]}  2) {s['swimmers'][1]}  3) {s['swimmers'][2]}  4) {s['swimmers'][3]}",
                                    "", "", ""])
                    except:
                        pass
                    if s['finals_splits']:
                        tb.add_row(["", niceSplits(s['finals_splits']), "", "", ""])
            elif ev['diving']:
                tb.field_names = ["Place", "Name", "Team", "Seed", "Finals"]
                for s in ev['swimmers']:
                    tb.add_row([s['finals_place'], s['name'], s['team'], s['seed'], s['finals_time']])
            else:
                tb.field_names = ["Place", "Name", "Team", "Seed", "Finals"]
                for s in ev['swimmers']:
                    tb.add_row([s['finals_place'], s['name'], s['team'], s['seed'], timeStateTF(s)])
                    if s['finals_splits']:
                        tb.add_row(["", niceSplits(s['finals_splits']), "", "", ""])

            if "--text" in sys.argv:
                print("text")
                with open(f"{name}.txt", "w") as f:
                    f.write("")
                    f.close()
                with open(f"{name}.txt", "a") as f:
                    f.write(tb.get_string() + "\n\n")
                    f.close()
            if "--html" in sys.argv:
                print("html")
                with open(f"{name}.html", "a") as f:
                    f.write(tb.get_html_string())
                    f.close()
    if "--html" in sys.argv:
        with open(f"{name}.html", "r") as f:
            p = f.read()
            f.close()
        with open("templates/res-top.html", "r") as f1:
            top = f1.read()
            print("top")
            f1.close()
        with open("templates/res-bottom.html", "r") as f2:
            bottom = f2.read()
            print("bottom")
            f2.close()
        with open(f"results/{name}.html", "w") as f3:
            body = f"{top}\n<h2>{mm_json['meet']['name']}</h2>\n{p}\n{bottom}"
            f3.write(body)
            f3.close()
