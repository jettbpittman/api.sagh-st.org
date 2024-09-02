import asyncio
import datetime
import json
import calendar
import random
import os
import base64
import secrets
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from passlib.hash import argon2
from typing import AsyncIterator, Awaitable, Callable
from tabulate import tabulate

import asyncpg
from aiohttp import web
import aiohttp_cors

router = web.RouteTableDef()

venues = {
    "AH": "Alamo Heights Natatorium",
    "AM": "Texas A&M Student Recreation Center Natatorium",
    "BU": "YMCA of the Highland Lakes",
    "CC": "Corpus Cristi ISD Natatorium",
    "CO": "Coronado Pool",
    "NE": "Josh Davis Natatorium/Bill Walker Pool",
    "NS": "NISD Natatorium & Swim Center",
    "SA": "San Antonio Natatorium",
    "SW": "Southwest Aquatic Center",
    "TM": "TMI Episcopal",
    "UT": "Lee & Joe Jamail Texas Swimming Center",
    "PA": "Palo Alto Natatorium",
    "LC": "Lamar CISD Natatorium",
    "DC": "Don Cook Natatorium",
    "BL": "George Block Aquatic Center",
    "SC": "Schertz Aquatics Center",
    "RR": "RRISD Aquatic Center",
    "TBA": "TBA",
    "UNK": "Unknown",
}

venue_colors = {
    "AH": "F8FFB0",
    "AM": "FFCCCC",
    "BU": "FFCCFF",
    "CC": "99CCFF",
    "CO": "99CCFF",
    "NE": "CCCCFF",
    "NS": "66DD88",
    "SA": "FFCC99",
    "SW": "99FFCC",
    "TM": "FFFFFF",
    "UT": "FFCC99",
    "PA": "99CCFF",
    "DC": "99CCFF",
    "LC": "99CCFF",
    "BL": "66DD88",
    "SC": "99CCFF",
    "RR": "FFCCFF",
    "TBA": "FFFFFF",
    "UNK": "FFFFFF"
}


class NotFoundException(BaseException):
    pass


with open("creds.json", "r") as f:
    creds = json.load(f)


def welcome_email(email, name):
    message = MIMEMultipart("alternative")
    message['From'] = creds['email']['sender_email']
    message['To'] = email
    message['Subject'] = "ghmvswim.org New User Registration"
    text = f"""Hey {name}!
    Welcome to ghmvswim.org, your go-to spot for all things GHMV swim!
    If you are a swimmer or parent and would like to link your account to a swimmer, please click the link here [insert link] to request linking.
    Sincerely,
    Jett Pittman
    Webmaster, ghmvswim.org
    jett@ghmvswim.org
    """

    message.attach(MIMEText(text, "plain"))
    with smtplib.SMTP_SSL(creds['email']['smtp_url'], creds['email']['smtp_port'],
                          context=ssl.create_default_context()) as server:
        server.login(creds['email']['username'], creds['email']['password'])
        server.sendmail(creds['email']['sender_email'], email, message.as_string())


def create_date(start, end=None):
    try:
        if end is None:
            d = datetime.datetime.strptime(start, "%Y%m%d")
            return f"{d.day} {calendar.month_name[d.month]} {d.year}"
        if end:
            s = datetime.datetime.strptime(start, "%Y%m%d")
            e = datetime.datetime.strptime(end, "%Y%m%d")
            if s.month == e.month:
                return f"{s.day}-{e.day} {calendar.month_name[e.month]} {s.year}"
            else:
                return f"{s.day} {calendar.month_name[s.month]} - {e.day} {calendar.month_name[e.month]} {s.year}"
    except Exception as e:
        return f"Unknown"


def top5Sort(e):
    if len(e["time"]) <= 5:
        adjusted_t = f"0:{e['time']}"
        return adjusted_t
    else:
        return e["time"]


def sortByTime(e):
    if len(e["time"]) <= 5:
        adjusted_t = f"0:{e['time']}"
        return adjusted_t
    else:
        return e["time"]


async def get_event_name(db, e):
    ev = await fetch_event(db, e)
    if ev['gender'] == "M":
        return f"Men {ev['name']}"
    if ev['gender'] == "F":
        return f"Women {ev['name']}"
    if ev['gender'] == "I":
        return f"Mixed {ev['name']}"


def get_event_name_simple(e):
    if e[-2] == "R":
        if e[-1] == "F":
            return f"{e[:-2]} Freestyle Relay"
        if e[-1] == "M":
            return f"{e[:-2]} Medley Relay"
    if e[-1] == "F":
        return f"{e[:-1]} Freestyle"
    if e[-1] == "M":
        return f"{e[:-1]} Individual Medley"
    if e[-1] == "B":
        return f"{e[:-1]} Backstroke"
    if e[-1] == "S":
        return f"{e[:-1]} Breaststroke"
    if e[-1] == "L":
        return f"{e[:-1]} Butterfly"


def generate_id(id_type: int, year: int = 0, join_date: int = None) -> int:
    """

    :param year: integer - Graduation Year
    :param id_type: integer - 1: Swimmer, 2: Meet, 3: Entry, 4: Team, 5: User, 6: Attendance
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


async def fetch_standard(db: asyncpg.Connection, code):
    if type(code) == dict:
        code = code["code"]
    if code is None:
        return None
    row = await db.fetchrow("SELECT * FROM standards WHERE code = $1", str(code))
    if not row:
        raise NotFoundException(f"Standard {code} does not exist!")
    return {
        "code": row["code"],
        "name": row["name"],
        "authority": row["authority"],
        "min_time": row["min_time"],
        "year": row["year"],
        "event": row["event"],
        "gender": row["gender"],
        "short_name": row["short_name"],
        "course": row["course"],
    }


async def fetch_entry(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT * FROM entries WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"Entry {id} does not exist!")
    resp = {
        "id": row["id"],
        "swimmer": await fetch_swimmer(db, row["swimmer"]),
        "meet": await fetch_meet(db, row["meet"]),
        "event": await fetch_event(db, row["event"]),
        "seed": row["seed"],
        "time": row["time"],
        "splits": json.loads(row["splits"]),
        "standards": await fetch_standard(db, row["standards"]),
        "relay": None,
    }
    if row['relay']:
        try:
            swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(id))
            resp['relay'] = {
                "1": await fetch_swimmer_lite(db, swimmers['swimmer_1']),
                "2": await fetch_swimmer_lite(db, swimmers['swimmer_2']),
                "3": await fetch_swimmer_lite(db, swimmers['swimmer_3']),
                "4": await fetch_swimmer_lite(db, swimmers['swimmer_4'])
            }
        except:
            pass
    return resp


async def fetch_entry_lite(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT * FROM entries WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"Entry {id} does not exist!")
    resp = {
        "id": row["id"],
        "meet": await fetch_meet(db, row["meet"]),
        "event": await fetch_event(db, row["event"]),
        "seed": row["seed"],
        "time": row["time"],
        "splits": json.loads(row["splits"]),
        "standards": await fetch_standard(db, row["standards"]),
        "relay": None,
    }
    if row['relay']:
        try:
            swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(id))
            resp['relay'] = {
                "1": await fetch_swimmer_lite(db, swimmers['swimmer_1']),
                "2": await fetch_swimmer_lite(db, swimmers['swimmer_2']),
                "3": await fetch_swimmer_lite(db, swimmers['swimmer_3']),
                "4": await fetch_swimmer_lite(db, swimmers['swimmer_4'])
            }
        except:
            pass
    return resp


async def fetch_event(db: asyncpg.Connection, id: str):
    row = await db.fetchrow("SELECT * FROM events WHERE code = $1", str(id))
    if not row:
        raise NotFoundException(f"Event {id} does not exist!")
    return {
        "code": row["code"],
        "name": row["name"],
        "distance": row["distance"],
        "stroke": row["stroke"],
        "relay": row["relay"],
        "gender": row['gender']
    }


async def fetch_event_all_entries(db: asyncpg.Connection, id: str):
    rows = await db.fetch("SELECT * FROM entries WHERE event = $1", str(id))
    if not rows:
        raise NotFoundException(f"Event {id} does not exist!")
    entries = []
    for entry in rows:
        e = {
            "id": entry["id"],
            "swimmer": await fetch_swimmer(db, entry["swimmer"]),
            "meet": await fetch_meet(db, entry["meet"]),
            "event": await fetch_event(db, entry["event"]),
            "seed": entry["seed"],
            "time": entry["time"],
            "splits": json.loads(entry["splits"]),
            "standards": await fetch_standard(db, entry["standards"]),
            "relay": None,
        }
        if entry['relay']:
            try:
                swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(entry['id']))
                e['relay'] = {
                    "1": await fetch_swimmer_lite(db, swimmers['swimmer_1']),
                    "2": await fetch_swimmer_lite(db, swimmers['swimmer_2']),
                    "3": await fetch_swimmer_lite(db, swimmers['swimmer_3']),
                    "4": await fetch_swimmer_lite(db, swimmers['swimmer_4'])
                }
            except:
                pass
        entries.append(e)
    return entries


async def fetch_event_top_five(db: asyncpg.Connection, id: str, official=True):
    rows = await db.fetch("SELECT * FROM entries WHERE event = $1 AND ignored = false", str(id))
    if not rows:
        raise NotFoundException(f"Event {id} does not exist!")
    entries = []
    for entry in rows:
        try:
            if json.loads(entry["splits"])[0] == 0.0:
                continue
        except IndexError:
            pass
        s = await fetch_swimmer(db, entry["swimmer"])
        if entry['relay']:
            try:
                swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(entry['id']))
                s_list = [swimmers["swimmer_1"], swimmers["swimmer_2"], swimmers["swimmer_3"], swimmers["swimmer_4"]]
                name = ""
                for swimmer_id in s_list:
                    swimmer = await fetch_swimmer_lite(db, swimmer_id)
                    name += f", {swimmer['first_name'][0]} {swimmer['last_name']}"
                name = name.strip()[2:]
            except:
                pass
        else:
            name = f"{s['first_name']} {s['last_name']}".strip()
        m = await fetch_meet(db, entry["meet"])
        e = {
            "id": entry["id"],
            "swimmer": name,
            "swimmer_id": s['id'],
            "homeschool": s['homeschool'],
            "meet": m,
            "season": m['season'],
            "event": await fetch_event(db, entry["event"]),
            "seed": entry["seed"],
            "time": entry["time"],
            "splits": json.loads(entry["splits"]),
            "standards": await fetch_standard(db, entry["standards"]),
            "relay": None,
        }
        if entry['relay']:
            try:
                swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(entry['id']))
                e['relay'] = {
                    "1": await fetch_swimmer_lite(db, swimmers['swimmer_1']),
                    "2": await fetch_swimmer_lite(db, swimmers['swimmer_2']),
                    "3": await fetch_swimmer_lite(db, swimmers['swimmer_3']),
                    "4": await fetch_swimmer_lite(db, swimmers['swimmer_4'])
                }
            except:
                pass
        if e['homeschool'] and official:
            continue
        entries.append(e)
    entries.sort(key=top5Sort)
    swimmers = []
    relayers = []
    top5 = []
    for entry in entries:
        if entry['relay']:
            if entry['relay'] in relayers:
                continue
            else:
                relayers.append(entry['relay'])
                top5.append(entry)
        elif entry["swimmer_id"] in swimmers:
            continue
        else:
            swimmers.append(entry["swimmer_id"])
            top5.append(entry)
    return top5[:5]


async def fetch_entries_by_team(db: asyncpg.Connection, team, meet):
    rows = await db.fetch(
        "SELECT id FROM swimmers WHERE team = $1 ORDER BY last_name, first_name, middle_name", str(team)
    )
    entries = {}
    m = await fetch_meet(db, meet)
    for swimmer in rows:
        rows2 = await db.fetch(
            "SELECT * FROM entries WHERE meet = $1 AND swimmer = $2  AND ignored = false",
            int(meet),
            int(swimmer["id"]),
        )
        for entry in rows2:
            s = await fetch_swimmer(db, entry["swimmer"])
            name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}"
            e = {
                "swim_id": s["id"],
                "swimmer": name,
                "homeschool": s['homeschool'],
                "meet": m['designator'],
                "event": await fetch_event(db, entry["event"]),
                "seed": entry["seed"],
                "time": entry["time"],
                "season": m["season"],
                "splits": json.loads(entry['splits']),
                "standards": await fetch_standard(db, entry["standards"]),
                "relay": None,
            }
            if entry['relay']:
                try:
                    swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(entry['id']))
                    e['relay'] = {
                        "1": await fetch_swimmer_lite(db, swimmers['swimmer_1']),
                        "2": await fetch_swimmer_lite(db, swimmers['swimmer_2']),
                        "3": await fetch_swimmer_lite(db, swimmers['swimmer_3']),
                        "4": await fetch_swimmer_lite(db, swimmers['swimmer_4'])
                    }
                except:
                    pass
            try:
                entries[entry["event"]].append(e)
            except KeyError:
                entries[entry["event"]] = [e]
    for event in entries:
        entries[event].sort(key=sortByTime)
    keys = list(entries.keys())
    keys.sort()
    sorted_entries = {i: entries[i] for i in keys}
    return sorted_entries


async def fetch_entries_by_meet(db: asyncpg.Connection, id: int):
    rows = await db.fetch("SELECT event FROM entries WHERE meet = $1 AND ignored = false", int(id))
    if not rows:
        raise NotFoundException(f"Meet {id} does not exist!")
    entries = []
    events = []
    for event in rows:
        event = event["event"]
        if event in events:
            continue
        events += [event]
        ev = await fetch_event(db, event)
        obj = ev
        obj["entries"] = []
        rows1 = await db.fetch(
            "SELECT * FROM entries WHERE meet = $1 AND event = $2", int(id), str(event)
        )
        for entry in rows1:
            s = await fetch_swimmer(db, entry["swimmer"])
            name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}".strip()
            x = {
                "swimmer": name,
                "homeschool": s['homeschool'],
                "meet": await fetch_meet(db, entry['meet']),
                "event": await fetch_event(db, entry['event']),
                "seed": entry["seed"],
                "time": entry["time"],
                "splits": json.loads(entry["splits"]),
                "standards": await fetch_standard(db, entry["standards"]),
                "relay": None,
            }
            if entry['relay']:
                try:
                    swimmers = await db.fetchrow("SELECT * FROM relays WHERE entry = $1", int(entry['id']))
                    x['relay'] = {
                        "1": await fetch_swimmer_lite(db, swimmers['swimmer_1']),
                        "2": await fetch_swimmer_lite(db, swimmers['swimmer_2']),
                        "3": await fetch_swimmer_lite(db, swimmers['swimmer_3']),
                        "4": await fetch_swimmer_lite(db, swimmers['swimmer_4'])
                    }
                except:
                    pass
            obj["entries"].append(x)
        obj["entries"].sort(key=sortByTime)
        entries.append(obj)
    return entries


async def fetch_team_roster(db: asyncpg.Connection, id: str):
    rows = await db.fetch(
        "SELECT id FROM swimmers WHERE team = $1 AND active = true AND manager = false ORDER BY last_name, first_name, middle_name",
        str(id)
    )
    roster = []
    for swimmer in rows:
        if swimmer['id'] in [1, 2, 3]:
            continue
        s = await fetch_swimmer_lite(db, swimmer["id"])
        roster.append(s)
    return sorted(roster, key=lambda d: d["last_name"])


async def fetch_team_managers(db: asyncpg.Connection, id: str):
    rows = await db.fetch(
        "SELECT id FROM swimmers WHERE team = $1 AND active = true AND manager = true", str(id)
    )
    roster = []
    for swimmer in rows:
        if swimmer['id'] in [1, 2, 3]:
            continue
        s = await fetch_swimmer_lite(db, swimmer["id"])
        roster.append(s)
    return sorted(roster, key=lambda d: d["last_name"])


async def fetch_team_roster_all(db: asyncpg.Connection, id: str):
    rows = await db.fetch("SELECT id FROM swimmers WHERE team = $1 ORDER BY last_name, first_name, middle_name", str(id))
    roster = []
    for swimmer in rows:
        s = await fetch_swimmer_lite(db, swimmer["id"])
        roster.append(s)
    return sorted(roster, key=lambda d: d["last_name"])


async def fetch_team_roster_all_noperms(db: asyncpg.Connection, id: str):
    rows = await db.fetch("SELECT id, last_name, first_name, middle_name, class FROM swimmers WHERE team = $1 ORDER BY last_name, first_name, middle_name", str(id))
    roster = []
    for swimmer in rows:
        s = await fetch_swimmer_noperms(db, swimmer["id"])
        roster.append(s)
    return sorted(roster, key=lambda d: d["last_name"])


async def fetch_team(db: asyncpg.Connection, id: str):
    row = await db.fetchrow("SELECT * FROM teams WHERE code = $1", str(id))
    if not row:
        raise NotFoundException(f"Team {id} does not exist!")
    return {
        "name": row["name"],
        "address": row["address"],
        "head_coach": row["head_coach"],
        "email": row["email"],
        "phone": row["phone"],
        "code": row["code"],
    }


async def fetch_swimmer(db: asyncpg.Connection, id: int):
    entries_i = await db.fetchrow("SELECT count(*) FROM entries WHERE swimmer = $1", int(id))
    entries_r = await db.fetchrow("SELECT count(*) FROM relays WHERE $1 in (swimmer_1, swimmer_2, swimmer_3, swimmer_4)", int(id))
    meets = await db.fetch("SELECT DISTINCT meet FROM entries WHERE swimmer = $1", int(id))
    row = await db.fetchrow("SELECT * FROM swimmers WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"Swimmer {id} does not exist!")
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "middle_name": row["middle_name"],
        "last_name": row["last_name"],
        "age": row["age"],
        "gender": row["gender"],
        "class": row["class"],
        "team": await fetch_team(db, row["team"]),
        "active": row["active"],
        "homeschool": row['homeschool'],
        "dob": row['dob'],
        "usas_id": row['usas_id'],
        "manager": row['manager'],
        "stats": {
            "entries": entries_i[0] + entries_r[0],
            "meet_count": len(meets),
            "meets": json.dumps([list(record) for record in meets])
        }
    }


async def fetch_swimmer_entries(db: asyncpg.Connection, id: int):
    rows = await db.fetch("SELECT event FROM entries WHERE swimmer = $1  AND ignored = false", int(id))
    if not rows:
        raise NotFoundException(f"Swimmer {id} does not exist!")
    entries = []
    events = []
    for event in rows:
        event = event["event"]
        if event in events:
            continue
        events.append(event)
        ev = await fetch_event(db, event)
        obj = ev
        obj["entries"] = []
        rows1 = await db.fetch(
            "SELECT * FROM entries WHERE swimmer = $1 AND event = $2",
            int(id),
            str(event),
        )
        for entry in rows1:
            s = await fetch_swimmer(db, entry["swimmer"])
            name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}".strip()
            obj["entries"].append(
                {
                    "swimmer": name,
                    "homeschool": s['homeschool'],
                    "meet": await fetch_meet(db, entry["meet"]),
                    "event": await fetch_event(db, entry["event"]),
                    "seed": entry["seed"],
                    "time": entry["time"],
                    "splits": json.loads(entry["splits"]),
                    "standards": await fetch_standard(db, entry["standards"]),
                }
            )
        obj["entries"].sort(key=sortByTime)
        entries.append(obj)
    return entries


async def fetch_swimmer_best_times(db: asyncpg.Connection, id: int):
    s = await fetch_swimmer_lite(db, id)
    name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}".strip()
    g = s["gender"].upper()
    events_list = {}
    events = [
        f"{g}200F",
        f"{g}200M",
        f"{g}50F",
        f"{g}100L",
        f"{g}100F",
        f"{g}500F",
        f"{g}100B",
        f"{g}100S",
    ]
    for event in events:
        entries = await fetch_swimmer_entries_event(db, id, event)
        if not entries:
            entry = {
                "swimmer": name,
                "time": "NT",
                "meet": {"name": ""},
                "event": await fetch_event(db, event),
            }
            events_list[event] = entry
            continue
        entries.sort(key=top5Sort)
        fastest = entries[0]
        try:
            if fastest["splits"] == 0.0:
                entry = {
                    "swimmer": name,
                    "time": "NT",
                    "meet": {"name": ""},
                    "event": await fetch_event(db, event),
                }
                events_list[event] = entry
                continue
        except IndexError:
            pass
        entry = {
            "swimmer": name,
            "homeschool": s['homeschool'],
            "meet": fastest["meet"],
            "event": fastest["event"],
            "seed": fastest["seed"],
            "time": fastest["time"],
            "splits": fastest["splits"],
            "standards": await fetch_standard(db, fastest["standards"]),
        }
        events_list[event] = entry
    return events_list


async def fetch_swimmer_entries_event(db: asyncpg.Connection, id: int, event: str):
    rows = await db.fetch(
        "SELECT * FROM entries WHERE swimmer = $1 AND event = $2 AND ignored = false", int(id), str(event)
    )
    if not rows:
        return []
    entries = []
    for entry in rows:
        s = await fetch_swimmer(db, entry["swimmer"])
        name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}".strip()
        entries.append(
            {
                "swimmer": name,
                "homeschool": s['homeschool'],
                "meet": await fetch_meet(db, entry["meet"]),
                "event": await fetch_event(db, entry["event"]),
                "seed": entry["seed"],
                "time": entry["time"],
                "splits": json.loads(entry["splits"]),
                "standards": await fetch_standard(db, entry["standards"]),
            }
        )
    return entries


async def fetch_swimmer_lite(db: asyncpg.Connection, id: int):
    entries = await db.fetchrow("SELECT count(*) FROM entries WHERE swimmer = $1", int(id))
    row = await db.fetchrow("SELECT * FROM swimmers WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"Swimmer {id} does not exist!")
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "middle_name": row["middle_name"],
        "last_name": row["last_name"],
        "age": row["age"],
        "gender": row["gender"],
        "class": row["class"],
        "active": row["active"],
        "homeschool": row['homeschool'],
        "usas_id": row['usas_id'],
        "dob": row['dob'],
        "manager": row['manager'],
        "stats": {
            "entries": entries[0]
        }
    }


async def fetch_swimmer_noperms(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT * FROM swimmers WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"Swimmer {id} does not exist!")
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "middle_name": row["middle_name"],
        "last_name": row["last_name"],
        "class": row["class"],
    }


async def fetch_meet(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT * FROM meets WHERE id = $1 ORDER BY startdate", int(id))
    if not row:
        raise NotFoundException(f"Meet {id} does not exist!")
    return {
        "id": row["id"],
        "officialname": f"{row['startdate'][:4]} {row['host']} {row['name']}",
        "name": row["name"],
        "venue": row["venue"],
        "designator": row["designator"],
        "startdate": row["startdate"],
        "enddate": row["enddate"],
        "date": create_date(row['startdate'], row['enddate']),
        "season": row["season"],
        "host": row['host'],
        "notes": row['notes'],
        "concluded": row['concluded'],
        "format": row['format'],
        "pwarmups": row['pwarmups'],
        "fwarmups": row['fwarmups'],
        "pstart": row['pstart'],
        "fstart": row['fstart'],
        "infopath": row['infopath'],
        "heatspath": row['heatspath'],
        "sessionpath": row['sessionpath'],
        "resultspath": row['resultspath'],
        "scorespath": row['scorespath'],
        "psychpath": row['psychpath'],
        "last_updated": row['last_updated'].isoformat(),
    }


async def fetch_all_meets(db: asyncpg.Connection):
    rows = await db.fetch("SELECT * FROM meets ORDER BY startdate DESC")
    if not rows:
        raise NotFoundException(f"Unexpected error!")
    meets = []
    for row in rows:
        meets.append(
            {
                "season": row["season"],
                "id": row["id"],
                "officialname": f"{row['startdate'][:4]} {row['host']} {row['name']}",
                "name": row["name"],
                "venue": row["venue"],
                "designator": row["designator"],
                "startdate": row["startdate"],
                "enddate": row["enddate"],
                "concluded": row['concluded'],
                "format": row['format'],
                "date": create_date(row['startdate'], row['enddate']),
                "host": row['host'],
                "notes": row['notes'],
                "pwarmups": row['pwarmups'],
                "fwarmups": row['fwarmups'],
                "pstart": row['pstart'],
                "fstart": row['fstart'],
                "infopath": row['infopath'],
                "heatspath": row['heatspath'],
                "sessionpath": row['sessionpath'],
                "resultspath": row['resultspath'],
                "scorespath": row['scorespath'],
                "psychpath": row['psychpath'],
                "last_updated": row['last_updated'].isoformat(),
            }
        )
    meets.sort(key=lambda d: d["season"], reverse=True)
    return meets


async def fetch_meets_by_season(db: asyncpg.Connection, season: int):
    rows = await db.fetch("SELECT * FROM meets WHERE season = $1 ORDER BY startdate", int(season))
    if not rows:
        raise NotFoundException(f"No meets in season {season}")
    meets = []
    for row in rows:
        meets.append(
            {
                "season": row["season"],
                "id": row["id"],
                "officialname": f"{row['startdate'][:4]} {row['host']} {row['name']}",
                "name": row["name"],
                "venue": row["venue"],
                "designator": row["designator"],
                "startdate": row["startdate"],
                "enddate": row["enddate"],
                "concluded": row['concluded'],
                "format": row['format'],
                "date": create_date(row['startdate'], row['enddate']),
                "host": row['host'],
                "notes": row['notes'],
                "pwarmups": row['pwarmups'],
                "fwarmups": row['fwarmups'],
                "pstart": row['pstart'],
                "fstart": row['fstart'],
                "infopath": row['infopath'],
                "heatspath": row['heatspath'],
                "sessionpath": row['sessionpath'],
                "resultspath": row['resultspath'],
                "scorespath": row['scorespath'],
                "psychpath": row['psychpath'],
                "last_updated": row['last_updated'].isoformat(),
            }
        )
    return meets


async def fetch_latest_meet(db: asyncpg.Connection):
    row = await db.fetchrow("SELECT * FROM meets WHERE concluded = true ORDER BY startdate DESC LIMIT 1")
    if not row:
        raise NotFoundException(f"No recent meet!")
    return {
        "id": row["id"],
        "name": row["name"],
        "officialname": f"{row['startdate'][:4]} {row['host']} {row['name']}",
        "venue": row["venue"],
        "designator": row["designator"],
        "startdate": row["startdate"],
        "enddate": row["enddate"],
        "concluded": row['concluded'],
        "format": row['format'],
        "date": create_date(row['startdate'], row['enddate']),
        "season": row["season"],
        "host": row['host'],
        "notes": row['notes'],
        "pwarmups": row['pwarmups'],
        "fwarmups": row['fwarmups'],
        "pstart": row['pstart'],
        "fstart": row['fstart'],
        "infopath": row['infopath'],
        "heatspath": row['heatspath'],
        "sessionpath": row['sessionpath'],
        "resultspath": row['resultspath'],
        "scorespath": row['scorespath'],
        "psychpath": row['psychpath'],
        "last_updated": row['last_updated'].isoformat(),
    }


async def fetch_all_users(db: asyncpg.Connection):
    rows = await db.fetch(
        "SELECT id, username, name, email, permissions, active, linked_swimmer, latest_access FROM users ORDER BY name")
    if not rows:
        raise NotFoundException(f"No users found!")
    users = []
    for row in rows:
        if row['linked_swimmer']:
            ls = await fetch_swimmer_lite(db, row['linked_swimmer'])
        else:
            ls = None
        users.append(
            {
                "id": row['id'],
                "username": row["username"],
                "name": row["name"],
                "email": row["email"],
                "permissions": row["permissions"],
                "linked_swimmer": ls,
                "active": row["active"],
                "latest_access": row["latest_access"]
            }
        )
    return users


async def fetch_user(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT id, username, name, email, permissions, active, linked_swimmer, latest_access "
                            "FROM users WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"No user found!")
    if row['linked_swimmer']:
        ls = await fetch_swimmer_lite(db, row['linked_swimmer'])
    else:
        ls = None
    return {
        "id": row['id'],
        "username": row["username"],
        "name": row["name"],
        "email": row["email"],
        "permissions": row["permissions"],
        "active": row["active"],
        "linked_swimmer": ls,
        "latest_access": row['latest_access']
    }


def handle_json_error(
        func: Callable[[web.Request], Awaitable[web.Response]]
) -> Callable[[web.Request], Awaitable[web.Response]]:
    async def handler(request: web.Request) -> web.Response:
        try:
            return await func(request)
        except asyncio.CancelledError as ex:
            return web.json_response({"status": "ISE", "reason": ex}, status=500)
        except NotFoundException as ex:
            return web.json_response(
                {"status": "not found", "reason": str(ex)}, status=404
            )
        except Exception as ex:
            print(str(ex))
            return web.json_response(
                {"status": "failed", "reason": str(ex)}, status=400
            )

    return handler


async def auth_required(request: web.Request, permissions: int = 0):
    try:
        token = request.headers["token"]
    except KeyError:
        return web.json_response(
            {
                "status": "bad request",
                "reason": "you have not passed proper authentication headers!",
            },
            status=400,
        )
    db = request.config_dict["DB"]
    r = await db.fetchrow("SELECT user_id FROM auth_tokens WHERE token = $1", str(token))
    if r is None:
        resp = web.json_response(
            {"status": "unauthorized", "reason": "mismatched token"}, status=401
        )
        return resp
    else:
        r2 = await db.fetchrow(
            "SELECT permissions FROM users WHERE id = $1", int(r["user_id"])
        )
        if permissions <= r2["permissions"]:
            resp = web.json_response({"status": "ok", "id": r['user_id']})
            resp.user_id = r['user_id']
            return resp
        else:
            resp = web.json_response(
                {
                    "status": "forbidden",
                    "reason": f"you do not have sufficient permissions to access this endpoint! level {permissions} required, you have {r2['permissions']}",
                },
                status=403,
            )
            resp.user_id = r['user_id']
            return resp


def strip_token(token: str):
    t = token.split(".")
    id = (base64.b64decode(t[0].encode())).decode()
    token_r = t[0]
    return {"user_id": id, "token": token_r}


@handle_json_error
@router.post("/standards/create")
async def create_standard(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    info = await request.json()
    name = info['name']
    org = info['org']
    min_time = info['time']
    code = info['code']
    year = info['year']
    age = info['age']
    gender = info['gender']
    short_name = info['short_name']
    course = info['course']
    event = info['event']
    await db.execute(
        "INSERT INTO standards (name, authority, min_time, code, year, age, gender, short_name, course)"
        " VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)", name, org, min_time, code, int(year), age, gender, short_name,
        course
    )
    await db.execute(
        "UPDATE standards set event = $1 where code = $2", event, code
    )
    return web.json_response(info)


@router.post("/attendance/submit")
@handle_json_error
async def submit_attendance(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    info = await request.json()
    payload: dict = info
    date = payload.pop('date')
    type = payload.pop('type')
    resp = {"date": date, "type": type}
    for swimmer in payload:
        await db.execute(
            "INSERT INTO attendance (date, swimmer, status, type) VALUES ($1, $2, $3, $4) ON CONFLICT (date, "
            "swimmer, type) DO UPDATE SET status = $3", date, int(swimmer), payload[swimmer], type)
        resp[swimmer] = payload[swimmer]
    return web.json_response(resp)


@router.get("/attendance/date/{date}/{type}")
@handle_json_error
async def get_attendance_date(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    date = request.match_info['date']
    type = request.match_info['type']
    rows = await db.fetch("SELECT * FROM attendance WHERE date = $1 and type = $2", date, type)
    resp = {'date': date}
    for swimmer in rows:
        resp[swimmer['swimmer']] = swimmer['status']
    return web.json_response(resp)


@router.get("/attendance/swimmer/{swimmer}")
@handle_json_error
async def get_attendance_swimmer(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=1)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    swimmer = request.match_info['swimmer']
    rows = await db.fetch("SELECT * FROM attendance WHERE swimmer = $1", int(swimmer))
    resp = {'swimmer': await fetch_swimmer(db, swimmer), 'records': {}}
    for date in rows:
        resp['records'][date['date']] = [date['status'], date['type']]
    resp['records'] = dict(sorted(resp['records'].items(), reverse=True))
    return web.json_response(resp)


@router.post("/auth/check")
@handle_json_error
async def auth_check(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    token = strip_token(request.headers["token"])
    db = request.config_dict["DB"]
    r = await db.fetchrow(
        "SELECT name, username, email, permissions, active, linked_swimmer FROM users WHERE id = $1",
        int(token["user_id"]),
    )
    ts = datetime.datetime.now().isoformat()
    await db.execute("UPDATE users SET latest_access = $1 WHERE id = $2", str(ts), int(token["user_id"]))
    if r['active'] is False:
        return web.json_response({"status": "failed", "reason": "forbidden"}, status=403)
    return web.json_response(
        {
            "status": "ok",
            "user": {
                "id": token["user_id"],
                "name": r["name"],
                "username": r["username"],
                "email": r["email"],
                "permissions": r["permissions"],
                "linked_swimmer": r['linked_swimmer']
            },
        }
    )


@router.post("/calendar/add")
@handle_json_error
async def add_calendar_event(request: web.Request) -> web.Response:
    info = await request.json()
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    name = info['name']
    date = info['date']
    time = info['time']
    urgent = info['urgent']
    db = request.config_dict["DB"]
    await db.execute("INSERT INTO calendar (name, date, time, urgent) VALUES ($1, $2, $3, $4)", name, date, time,
                     urgent)
    return web.json_response(
        {
            "name": name,
            "date": date,
            "time": time,
            "urgent": urgent
        }
    )


# User Queries
@router.post("/users/register")
@handle_json_error
async def register_user(request: web.Request) -> web.Response:
    info = await request.json()
    name = info['name']
    username = info['username']
    email = info['email']
    password = argon2.hash(info["password"])
    id = generate_id(5)
    db = request.config_dict["DB"]
    await db.execute(
        "INSERT INTO users (id, name, password, email, permissions, username) VALUES ($1, $2, $3, $4, $5, $6)",
        id, name, password, email, int(0), username,
    )
    # welcome_email(email, name)
    return web.json_response(
        {
            "id": id,
            "name": name,
            "username": username,
            "email": email,
            "permissions": 0,
        }
    )


@router.post("/users/linking/request")
async def req_linking(request: web.Request) -> web.Response:
    info = await request.json()
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    user_id = info['user_id']
    verf_code = info['verification_code']
    db = request.config_dict["DB"]
    try:
        await db.execute("INSERT INTO linking_requests (user_id, swimmer_id, verification_code) VALUES ($1, $2, $3)", int(user_id),
                         int(info['swimmer_id']), verf_code)
        return web.json_response({"status": "success", "reason": "submitted request"}, status=200)
    except asyncpg.UniqueViolationError:
        return web.json_response({"status": "failed", "reason": "user has already requested linking"}, status=409)


@router.get("/users/linking/requests")
async def linking_requests(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    reqs = await db.fetch("SELECT * FROM linking_requests WHERE user_id = $1", int(a.user_id))
    reqs_list = []
    for req in reqs:
        reqs_list.append({"swimmer": await fetch_swimmer_lite(db, req['swimmer_id']), "submitted_at": req["created_at"].strftime('%Y-%m-%d %H:%M:%S'), "status": req['status'], "verification_code": req['verification_code']})
    return web.json_response(reqs_list)


@router.get("/users/linking/requestqueue")
async def linking_requests(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    reqs = await db.fetch("SELECT * FROM linking_requests WHERE status = 'unapproved'")
    reqs_list = []
    for req in reqs:
        reqs_list.append({"user": await fetch_user(db, req['user_id']), "swimmer": await fetch_swimmer_lite(db, req['swimmer_id']), "submitted_at": req["created_at"].strftime('%Y-%m-%d %H:%M:%S'), "status": req['status'], "verification_code": req['verification_code']})
    return web.json_response(reqs_list)

@router.post("/users/linking/approve")
async def approve_linking(request: web.Request) -> web.Response:
    info = await request.json()
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    user_id = info['user_id']
    swimmer_id = info['swimmer_id']
    db = request.config_dict["DB"]
    await db.execute("UPDATE users SET linked_swimmer = $1 WHERE id = $2", swimmer_id, user_id)
    await db.execute(
            "UPDATE linking_requests SET status = 'approved', approved_by = $1 WHERE user_id = $2 AND swimmer_id = $3",
            int(a.user_id), int(user_id), int(swimmer_id))
    return web.json_response({"status": "success", "reason": "linked swimmer"}, status=200)


@router.post("/users/linking/reject")
async def reject_linking(request: web.Request) -> web.Response:
    info = await request.json()
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    user_id = info['user_id']
    swimmer_id = info['swimmer_id']
    db = request.config_dict["DB"]
    await db.execute(
        "UPDATE linking_requests SET status = 'rejected', approved_by = $1 WHERE user_id = $2 AND swimmer_id = $3",
        int(a.user_id), int(user_id), int(swimmer_id))
    return web.json_response({"status": "success", "reason": "rejected linking"}, status=200)


@router.post("/users")
@handle_json_error
async def create_user(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    info = await request.json()
    name = info["name"]
    username = info["username"]
    email = info["email"]
    password = argon2.hash(info["password"])
    if "permissions" in info:
        permissions = info["permissions"]
    else:
        permissions = 0
    id = generate_id(5)
    db = request.config_dict["DB"]
    await db.execute(
        "INSERT INTO users (id, name, password, email, permissions, username) VALUES ($1, $2, $3, $4, $5, $6)",
        id, name, password, email, int(permissions), username,
    )
    return web.json_response(
        {
            "id": id,
            "name": name,
            "username": username,
            "email": email,
            "permissions": permissions,
        }
    )


@router.get("/users/all")
@handle_json_error
async def get_all_user(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    db = request.config_dict['DB']
    users = await fetch_all_users(db)
    return web.json_response(users)


@router.get("/users/{id}")
@handle_json_error
async def get_user(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    user_id = request.match_info['id']
    if user_id == "me" or user_id == a.user_id:
        user_id = a.user_id
    elif (await auth_required(request, permissions=4)).status == 200:
        pass
    else:
        return web.json_response({"status": "failed", "reason": "forbidden"}, status=403)
    db = request.config_dict['DB']
    user = await fetch_user(db, user_id)
    return web.json_response(user)


@router.patch("/users/{id}")
@handle_json_error
async def edit_user(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    user_id = request.match_info['id']
    fields = {}
    user = await request.json()
    if a.user_id == user_id:
        pass
    elif (await auth_required(request, permissions=4)).status == 200:
        if "permissions" in user:
            fields['permissions'] = user['permissions']
        if "active" in user:
            fields['active'] = user['active']
        if "linked_swimmer" in user:
            fields['linked_swimmer'] = user['linked_swimmer']
    else:
        return web.json_response({"status": "failed", "reason": "forbidden"}, status=403)
    if "name" in user:
        fields["name"] = user['name']
    if "email" in user:
        fields["email"] = user['email']
    if "username" in user:
        fields["username"] = user['username']
    db = request.config_dict['DB']
    if fields:
        field_values = ""
        for field in fields:
            field_values += f"{field} = {fields[field]}"
        await db.execute(
            f"UPDATE users SET {field_values} WHERE id = $1", int(user_id)
        )
    user = await db.fetchrow(
        "SELECT * FROM users WHERE id = $1", int(user_id)
    )
    return web.json_response(
        {
            "id": user['id'],
            "name": user['name'],
            "username": user['username'],
            "email": user['email'],
            "permissions": user['permissions'],
            "active": user['active'],
            "linked_swimmer": user['linked_swimmer']
        }
    )


@router.post("/users/{id}/password")
@handle_json_error
async def change_password(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    req_id = request.match_info['id']
    if int(a.user_id) != int(req_id):
        return web.json_response({"status": "failed", "reason": f"forbidden - your ID is {a.user_id} while you are "
                                                                f"trying to access {req_id}"}, status=403)
    info = await request.json()
    id = req_id
    old_password = info['old_password']
    new_password = info['new_password']
    db = request.config_dict['DB']
    ir = await db.fetchrow(
        "SELECT password FROM users WHERE id = $1", int(id)
    )
    if not argon2.verify(old_password, ir['password']):
        return web.json_response(
            {"status": "failed", "reason": "incorrect old password"}, status=401
        )
    else:
        hashed = argon2.hash(new_password)
        await db.execute(
            "UPDATE users SET password = $1 WHERE id = $2", hashed, int(id)
        )
        return web.json_response(
            {"status": "ok", "reason": "password reset!"}
        )


@router.post("/auth/login")
@handle_json_error
async def login(request: web.Request) -> web.Response:
    info = await request.json()
    username = info["username"]
    password = info["password"]
    db = request.config_dict["DB"]
    r = await db.fetchrow(
        "SELECT id, username, password FROM users WHERE username = $1", str(username)
    )
    if r is None:
        return web.json_response(
            {"status": "failed", "reason": "username/password mismatch"}, status=401
        )
    if not argon2.verify(password, r["password"]):
        return web.json_response(
            {"status": "failed", "reason": "username/password mismatch"}, status=401
        )
    else:
        token_r = secrets.token_urlsafe(32)
        token_i = base64.b64encode(str(r["id"]).encode()).decode()
        token = f"{token_i}.{token_r}"
        ts = datetime.datetime.now().isoformat()
        await db.execute(
            "INSERT INTO auth_tokens (user_id, token, timestamp) VALUES ($1, $2, $3)",
            int(r["id"]),
            str(token),
            str(ts)
        )
        return web.json_response({"user_id": r["id"], "token": token})


# Swimmer Queries
@router.post("/swimmers")
@handle_json_error
async def create_swimmer(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=3)
    if a.status != 200:
        return a
    info = await request.json()
    first_name = info["first_name"]
    last_name = info["last_name"]
    middle_name = info["middle_name"]
    year = info["class"]
    team = info["team"]
    gender = info["gender"]
    if "dob" in info:
        dob = info['dob']
    else:
        dob = None
    if "join_date" in info:
        join_date = info["join_date"]
        id = generate_id(1, year, join_date)
    else:
        id = generate_id(1, year)
    if "active" in info:
        active = bool(info["active"])
    else:
        active = True
    db = request.config_dict["DB"]
    await db.execute(
        "INSERT INTO swimmers (id, first_name, last_name, middle_name, class, team, active, gender, dob) VALUES($1, $2, "
        "$3, $4, $5, $6, $7, $8, $9)",
        id,
        first_name,
        last_name,
        middle_name,
        year,
        team,
        bool(active),
        gender,
        dob
    )
    return web.json_response(
        {
            "id": id,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "dob": dob,
            "class": year,
            "team": await fetch_team(db, team),
            "active": active,
        }
    )


@router.patch("/swimmers/{id}")
@handle_json_error
async def edit_swimmer(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=3)
    if a.status != 200:
        return a
    swimmer_id = request.match_info['id']
    swimmer = await request.json()
    fields = {}
    if "first_name" in swimmer:
        fields["first_name"] = swimmer['first_name']
    if "middle_name" in swimmer:
        fields["middle_name"] = swimmer['middle_name']
    if "last_name" in swimmer:
        fields["last_name"] = swimmer['last_name']
    if "class" in swimmer:
        fields["class"] = swimmer['class']
    if "active" in swimmer:
        fields["active"] = swimmer['active']
    if "usas_id" in swimmer:
        fields["usas_id"] = swimmer['usas_id']
    if fields:
        field_values = ""
        for field in fields:
            field_values += f"{field} = {fields[field]}"
        db = request.config_dict['DB']
        await db.execute(
            f"UPDATE swimmers SET {field_values} WHERE id = $1", int(swimmer_id)
        )
    swimmer = await db.fetchrow(
        "SELECT * FROM swimmers WHERE id = $1", int(swimmer_id)
    )
    return web.json_response(
        {
            "id": swimmer['id'],
            "first_name": swimmer['first_name'],
            "middle_name": swimmer['middle_name'],
            "last_name": swimmer['last_name'],
            "age": swimmer['age'],
            "class": swimmer['class'],
            "team": await fetch_team(db, swimmer['team']),
            "active": swimmer['active'],
            "usas_id": swimmer['usas_id']
        }
    )


@router.patch("/class/{id}/active")
@handle_json_error
async def change_class_status(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=3)
    if a.status != 200:
        return a
    class_id = request.match_info['id']
    json = await request.json()
    active = bool(json['active'])
    db = request.config_dict['DB']
    await db.execute(
        "UPDATE swimmers SET active = $1 WHERE class = $2", active, int(class_id)
    )
    return web.json_response({"status": "ok", "reason": "updated!"})


@router.get("/info")
@handle_json_error
async def db_info(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    entries = await db.fetchrow("SELECT count(*) from entries")
    meets = await db.fetchrow("SELECT count(*) from meets")
    athletes = await db.fetchrow("SELECT count(*) from swimmers")
    response = {
        "status": "online",
        "entries": entries["count"],
        "meets": meets["count"],
        "athletes": athletes["count"],
    }
    return web.json_response(response)


@router.get("/swimmers/{id}")
async def get_swimmers(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    swimmer_id = request.match_info["id"]
    db = request.config_dict["DB"]
    swimmer = await fetch_swimmer(db, swimmer_id)
    return web.json_response(swimmer)


@router.get("/swimmers/{id}/entries")
@handle_json_error
async def get_swimmer_all_entries(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    swimmer_id = request.match_info["id"]
    db = request.config_dict["DB"]
    entries = await fetch_swimmer_entries(db, swimmer_id)
    return web.json_response(entries)


@router.get("/swimmers/{id}/entries/{event}")
@handle_json_error
async def get_swimmer_all_entries_event(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    swimmer_id = request.match_info["id"]
    event_code = request.match_info["event"]
    db = request.config_dict["DB"]
    entries = await fetch_swimmer_entries_event(db, swimmer_id, event_code)
    return web.json_response(entries)


@router.get("/swimmers/{id}/best")
@handle_json_error
async def get_swimmer_bests(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=0)
    if a.status != 200:
        return a
    swimmer_id = request.match_info["id"]
    db = request.config_dict["DB"]
    entries = await fetch_swimmer_best_times(db, swimmer_id)
    return web.json_response(entries)


# Team Queries
@router.post("/teams")
@handle_json_error
async def create_team(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    info = await request.json()
    name = info["name"]
    address = info["address"]
    head_coach = info["head_coach"]
    email = info["email"]
    phone = info["phone"]
    code = info["code"]
    id = generate_id(4)
    db = request.config_dict["DB"]
    await db.execute(
        "INSERT INTO teams (id, name, address, head_coach, email, phone, code) VALUES($1, $2, $3, $4, $5, $6, $7)",
        id,
        name,
        address,
        head_coach,
        email,
        phone,
        code,
    )
    return web.json_response(
        {
            "id": id,
            "name": name,
            "address": address,
            "head_coach": head_coach,
            "email": email,
            "phone": phone,
            "code": code,
        }
    )


@router.get("/teams/{id}")
@handle_json_error
async def get_team(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=1)
    if a.status != 200:
        return a
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team(db, team_id)
    return web.json_response(team)


@router.get("/teams/{id}/roster/current")
@handle_json_error
async def get_team_roster_c(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=1)
    if a.status != 200:
        return a
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team_roster(db, team_id)
    return web.json_response(team)


@router.get("/teams/{id}/roster/current/managers")
@handle_json_error
async def get_team_roster_m(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=1)
    if a.status != 200:
        return a
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team_managers(db, team_id)
    return web.json_response(team)


@router.get("/teams/{id}/roster/all")
@handle_json_error
async def get_team_roster_all(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=1)
    if a.status != 200:
        return a
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team_roster_all(db, team_id)
    return web.json_response(team)


@router.get("/teams/{id}/roster/all_pub")
@handle_json_error
async def get_team_roster_all_pub(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=1)
    if a.status != 200:
        return a
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team_roster_all_noperms(db, team_id)
    return web.json_response(team)


# Meet Queries
@router.post("/meets")
@handle_json_error
async def create_meet(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=3)
    if a.status != 200:
        return a
    info = await request.json()
    name = info["name"]
    venue = info["venue"]
    designator = info["designator"]
    startdate = info["startdate"]
    season = info["season"]
    format = info['format']
    host = info['host']
    concluded = info['concluded']
    id = generate_id(2)
    db = request.config_dict["DB"]
    await db.execute(
        "INSERT INTO meets "
        "(id, name, venue, designator, startdate, season, concluded, host, format) "
        "VALUES "
        "($1, $2, $3, $4, $5, $6, $7, $8, $9)",
        id,
        name,
        venue,
        designator,
        startdate,
        season,
        concluded,
        host,
        format,
    )
    return web.json_response(
        {
            "id": id,
            "name": name,
            "venue": venue,
            "designator": designator,
            "startdate": startdate,
            "season": season,
            "concluded": concluded,
            "host": host,
            "format": format
        }
    )


@router.patch("/meets/{id}/dtinfo")
async def update_meet_dtinfo(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    info = await request.json()
    fields = {}
    meet_id = request.match_info["id"]
    if "pwarmups" in info:
        fields["pwarmups"] = f"'{info['pwarmups']}'"
    if "fwarmups" in info:
        fields["fwarmups"] = f"'{info['fwarmups']}'"
    if "pstart" in info:
        fields["pstart"] = f"'{info['pstart']}'"
    if "fstart" in info:
        fields["fstart"] = f"'{info['fstart']}'"
    if "startdate" in info:
        fields["startdate"] = f"'{info['startdate']}'"
    if "enddate" in info:
        fields["enddate"] = f"'{info['enddate']}'"
    db = request.config_dict['DB']
    if fields:
        field_values = ""
        for field in fields:
            field_values += f"{field} = {fields[field]}, "
        await db.execute(
            f"UPDATE meets SET {field_values[:-2]}, last_updated = default WHERE id = $1", int(meet_id)
        )
    meet = await db.fetchrow(
        "SELECT * FROM meets WHERE id = $1", int(meet_id)
    )
    return web.json_response(
        {
            "id": meet_id,
            "name": meet['name'],
            "venue": meet['venue'],
            "designator": meet['designator'],
            "startdate": meet['startdate'],
            "enddate": meet['enddate'],
            "season": meet['season'],
            "concluded": meet['concluded'],
            "host": meet['host'],
            "format": meet['format'],
            "pwarmups": meet['pwarmups'],
            "fwarmups": meet['fwarmups'],
            "pstart": meet['pstart'],
            "fstart": meet['fstart'],
            "infopath": meet['infopath'],
            "heatspath": meet['heatspath'],
            "sessionpath": meet['sessionpath'],
            "resultspath": meet['resultspath'],
            "scorespath": meet['scorespath'],
            "psychpath": meet['psychpath'],
            "last_updated": meet['last_updated'].isoformat(),
        }
    )


@router.patch("/meets/{id}/geninfo")
async def update_meet_geninfo(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    info = await request.json()
    fields = {}
    meet_id = request.match_info["id"]
    if "name" in info:
        fields["name"] = f"'{info['name']}'"
    if "venue" in info:
        fields["venue"] = f"'{info['venue']}'"
    if "designator" in info:
        fields["designator"] = f"'{info['designator']}'"
    if "season" in info:
        fields["season"] = info['season']
    if "concluded" in info:
        fields["concluded"] = info['concluded']
    if "host" in info:
        fields["host"] = f"'{info['host']}'"
    if "format" in info:
        fields["format"] = f"'{info['format']}'"
    if "notes" in info:
        fields["notes"] = f"'{info['notes']}'"
    db = request.config_dict['DB']
    if fields:
        field_values = ""
        for field in fields:
            field_values += f"{field} = {fields[field]}, "
        await db.execute(
            f"UPDATE meets SET {field_values[:-2]}, last_updated = default WHERE id = $1", int(meet_id)
        )
    meet = await db.fetchrow(
        "SELECT * FROM meets WHERE id = $1", int(meet_id)
    )
    return web.json_response(
        {
            "id": meet_id,
            "name": meet['name'],
            "venue": meet['venue'],
            "designator": meet['designator'],
            "startdate": meet['startdate'],
            "enddate": meet['enddate'],
            "season": meet['season'],
            "concluded": meet['concluded'],
            "host": meet['host'],
            "format": meet['format'],
            "pwarmups": meet['pwarmups'],
            "fwarmups": meet['fwarmups'],
            "pstart": meet['pstart'],
            "fstart": meet['fstart'],
            "infopath": meet['infopath'],
            "heatspath": meet['heatspath'],
            "sessionpath": meet['sessionpath'],
            "resultspath": meet['resultspath'],
            "scorespath": meet['scorespath'],
            "psychpath": meet['psychpath'],
            "last_updated": meet['last_updated'].isoformat(),
        }
    )


@router.patch("/meets/{id}/filesinfo")
async def update_meet_filesinfo(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    info = await request.json()
    fields = {}
    meet_id = request.match_info["id"]
    if "infopath" in info:
        fields["infopath"] = f"'{info['infopath']}'"
    if "heatspath" in info:
        fields["heatspath"] = f"'{info['heatspath']}'"
    if "sessionpath" in info:
        fields["sessionpath"] = f"'{info['sessionpath']}'"
    if "resultspath" in info:
        fields["resultspath"] = f"'{info['resultspath']}'"
    if "scorespath" in info:
        fields["scorespath"] = f"'{info['scorespath']}'"
    if "psychpath" in info:
        fields["psychpath"] = f"'{info['psychpath']}'"
    db = request.config_dict['DB']
    if fields:
        field_values = ""
        for field in fields:
            field_values += f"{field} = {fields[field]}, "
        await db.execute(
            f"UPDATE meets SET {field_values[:-2]}, last_updated = default WHERE id = $1", int(meet_id)
        )
    meet = await db.fetchrow(
        "SELECT * FROM meets WHERE id = $1", int(meet_id)
    )
    return web.json_response(
        {
            "id": meet_id,
            "name": meet['name'],
            "venue": meet['venue'],
            "designator": meet['designator'],
            "startdate": meet['startdate'],
            "enddate": meet['enddate'],
            "season": meet['season'],
            "concluded": meet['concluded'],
            "host": meet['host'],
            "format": meet['format'],
            "pwarmups": meet['pwarmups'],
            "fwarmups": meet['fwarmups'],
            "pstart": meet['pstart'],
            "fstart": meet['fstart'],
            "infopath": meet['infopath'],
            "heatspath": meet['heatspath'],
            "sessionpath": meet['sessionpath'],
            "resultspath": meet['resultspath'],
            "scorespath": meet['scorespath'],
            "psychpath": meet['psychpath'],
            "last_updated": meet['last_updated'].isoformat(),
        }
    )


@router.get("/meets/{id}")
@handle_json_error
async def get_meet(request: web.Request) -> web.Response:
    meet_id = request.match_info["id"]
    db = request.config_dict["DB"]
    meet = await fetch_meet(db, meet_id)
    return web.json_response(meet)


@router.get("/meets/{id}/entries")
@handle_json_error
async def get_meet_entries(request: web.Request) -> web.Response:
    meet_id = request.match_info["id"]
    db = request.config_dict["DB"]
    meet = await fetch_entries_by_meet(db, meet_id)
    return web.json_response(meet)


@router.get("/meets")
@handle_json_error
async def get_all_meets(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    meets = await fetch_all_meets(db)
    return web.json_response(meets)


@router.get("/season/{code}/meets")
@handle_json_error
async def get_season_meets(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    season = request.match_info["code"]
    meets = await fetch_meets_by_season(db, season)
    return web.json_response(meets)


@router.get("/season/{code}/meets/schedule")
@handle_json_error
async def get_season_schedule(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    season = request.match_info["code"]
    meets = await fetch_meets_by_season(db, season)
    html = '<tr><th style="width: 80%;">Meet</th><th style="width: 20%;">Files</th></tr>'
    for meet in meets:
        times = ""
        if meet['format'] == "pf":
            times = f'Warmups @ {meet["pwarmups"]} (P) {meet["fwarmups"]} (F) | Meet @ {meet["pstart"]} (P) {meet["fstart"]} (F)'
        else:
            times = f'Warmups @ {meet["fwarmups"]} | Meet @ {meet["fstart"]}'
        files = ""
        if meet['infopath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["infopath"]}">INFO</a></b><br>'
        if meet['heatspath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["heatspath"]}">HEATS</a></b><br>'
        if meet['sessionpath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["sessionpath"]}">SESSIONS</a></b><br>'
        if meet['resultspath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["resultspath"]}">RESULTS</a></b><br>'
        if meet['scorespath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["scorespath"]}">SCORES</a></b><br>'
        html += f'<tr class="meet-row"><td style="width: 80%; background-color: #{venue_colors[meet["venue"]]};" class="meet-info-col"><b>{meet["officialname"]}</b><br>{venues[meet["venue"]]} ({meet["venue"]})<br>{meet["date"]}<br>{times}<br><b style="color: darkred">{meet["notes"]}</b></td><td style="width: 20%; background-color: #{venue_colors[meet["venue"]]};" class="meet-files-col">{files[:-4]}</td></tr>'
    return web.Response(body=html)


@router.get("/season/{code}/meets/lastupdate")
async def get_last_meet_update(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    season = request.match_info["code"]
    meet = await db.fetchrow("SELECT * FROM meets WHERE season = $1 ORDER BY last_updated DESC LIMIT 1", int(season))
    date = meet['last_updated']
    date = date - datetime.timedelta(hours=5)
    formatted_date = f'{date.day} {date.strftime("%B")[0:3].upper()} {date.year}'
    return web.Response(body=formatted_date)


@router.get("/latest/meet")
@handle_json_error
async def get_latest_meet(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    meet = await fetch_latest_meet(db)
    return web.json_response(meet)


@router.get("/latest/meets/withintwoweeks")
async def get_meets_within_two_weeks(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    datenow = datetime.datetime.now()
    dateweekbefore = datenow - datetime.timedelta(days=7)
    dwb = f"{dateweekbefore.year}{dateweekbefore.month:02d}{dateweekbefore.day:02d}"
    dateweeklater = datenow + datetime.timedelta(days=7)
    dwl = f"{dateweeklater.year}{dateweeklater.month:02d}{dateweeklater.day:02d}"
    meets = await db.fetch(f"SELECT * FROM meets where startdate BETWEEN '{dwb}' AND '{dwl}' ORDER BY startdate DESC")
    html = ""
    for meet in meets:
        times = ""
        if meet['format'] == "pf":
            times = f'Warmups @ {meet["pwarmups"]} (P) {meet["fwarmups"]} (F) | Meet @ {meet["pstart"]} (P) {meet["fstart"]} (F)'
        else:
            times = f'Warmups @ {meet["fwarmups"]} | Meet @ {meet["fstart"]}'
        files = ""
        if meet['infopath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["infopath"]}">INFO</a></b><br>'
        if meet['heatspath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["heatspath"]}">HEATS</a></b><br>'
        if meet['sessionpath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["sessionpath"]}">SESSIONS</a></b><br>'
        if meet['resultspath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["resultspath"]}">RESULTS</a></b><br>'
        if meet['scorespath']:
            files += f'<b style="text-decoration: underline"><a href="{meet["scorespath"]}">SCORES</a></b><br>'
        html += f'<tr class="meet-row"><td style="width: 80%; background-color: #{venue_colors[meet["venue"]]};" class="meet-info-col"><b>{meet["startdate"][:4]} {meet["host"]} {meet["name"]}</b><br>{venues[meet["venue"]]} ({meet["venue"]})<br>{create_date(meet["startdate"], meet["enddate"])}<br>{times}<br><b style="color: darkred">{meet["notes"]}</b></td><td style="width: 20%; background-color: #{venue_colors[meet["venue"]]};" class="meet-files-col">{files[:-4]}</td></tr>'
    return web.Response(body=html)


@router.get("/meets/{meet}/entries/{team}")
@handle_json_error
async def get_meet_entries_by_team(request: web.Request) -> web.Response:
    meet_id = request.match_info["meet"]
    team_id = request.match_info["team"]
    db = request.config_dict["DB"]
    meet = await fetch_entries_by_team(db, meet=meet_id, team=team_id)
    return web.json_response(meet)


# Entry Queries
@router.post("/entries")
@handle_json_error
async def create_entry(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=3)
    if a.status != 200:
        return a
    info = await request.json()
    swimmer = info["swimmer"]
    meet = info["meet"]
    event = info["event"]
    seed = info["seed"]
    time = info["time"]
    splits = list(info["splits"])
    id = generate_id(3)
    splits = json.dumps(splits)
    db = request.config_dict["DB"]
    await db.execute(
        "INSERT INTO entries (id, swimmer, meet, event, seed, time, splits) VALUES($1, $2, $3, $4, $5, $6, $7)",
        int(id),
        int(swimmer),
        int(meet),
        str(event),
        str(seed),
        str(time),
        splits,
    )
    return web.json_response(
        {
            "id": id,
            "swimmer": await fetch_swimmer(db, swimmer),
            "meet": await fetch_meet(db, meet),
            "event": await fetch_event(db, event),
            "seed": seed,
            "time": time,
            "splits": json.loads(splits),
        }
    )


@router.get("/entries/{id}")
@handle_json_error
async def get_entry(request: web.Request) -> web.Response:
    entry_id = request.match_info["id"]
    db = request.config_dict["DB"]
    entry = await fetch_entry(db, entry_id)
    return web.json_response(entry)


@router.get("/events/{code}/all")
@handle_json_error
async def get_event_all(request: web.Request) -> web.Response:
    event_code = request.match_info["code"]
    db = request.config_dict["DB"]
    entries = await fetch_event_all_entries(db, event_code)
    return web.json_response(entries)


@router.get("/events/{code}/top5")
@handle_json_error
async def get_event_top5(request: web.Request) -> web.Response:
    event_code = request.match_info["code"]
    db = request.config_dict["DB"]
    entries = await fetch_event_top_five(db, event_code)
    return web.json_response(entries)


async def fetch_top5_school(db):
    events = ["200F", "200M", "50F", "100L", "100F", "500F", "100B", "100S"]
    headers = [
        "Rank",
        "Name",
        "Time",
        "Year",
        "Event",
        "Year",
        "Time",
        "Name",
        "Rank",
    ]
    table = []
    for event in events:
        m_event = "M" + event
        f_event = "F" + event
        m_entries = await fetch_event_top_five(db, m_event)
        f_entries = await fetch_event_top_five(db, f_event)
        counter = 1
        while counter <= 5:
            f_name = f_entries[counter - 1]["swimmer"]
            m_name = m_entries[counter - 1]["swimmer"]
            if counter == 1:
                row = [
                    counter,
                    f_name,
                    f_entries[counter - 1]["time"],
                    f_entries[counter - 1]["season"],
                    get_event_name_simple(event),
                    m_entries[counter - 1]["season"],
                    m_entries[counter - 1]["time"],
                    m_name,
                    counter,
                ]
            else:
                try:
                    row = [
                        counter,
                        f_name,
                        f_entries[counter - 1]["time"],
                        f_entries[counter - 1]["season"],
                        "",
                        m_entries[counter - 1]["season"],
                        m_entries[counter - 1]["time"],
                        m_name,
                        counter,
                    ]
                except IndexError:
                    pass
            table.append(row)
            counter += 1
    date = datetime.datetime.now()
    return (
            f'<h2>Great Hearts Monte Vista<br><span style="color: darkred; font-weight: bold;">SCHOOL '
            f'RECORDS</span></h2>\n<p'
            f'style="color: darkred">UPDATED: {date.day} {date.strftime("%B")[0:3].upper()} {date.year}</p>\n'
            + tabulate(table, headers=headers, tablefmt="html", numalign="center", stralign="center")
    )


async def fetch_top5_program(db):
    events = ["200F", "200M", "50F", "100L", "100F", "500F", "100B", "100S"]
    headers = [
        "Rank",
        "Name",
        "Time",
        "Year",
        "Event",
        "Year",
        "Time",
        "Name",
        "Rank",
    ]
    table = []
    for event in events:
        m_entries = await fetch_event_top_five(db, f"M{event}", official=False)
        f_entries = await fetch_event_top_five(db, f"F{event}", official=False)
        counter = 1
        while counter <= 5:
            f_name = f_entries[counter - 1]["swimmer"]
            m_name = m_entries[counter - 1]["swimmer"]
            if counter == 1:
                row = [
                    counter,
                    f_name,
                    f_entries[counter - 1]["time"],
                    f_entries[counter - 1]["season"],
                    get_event_name_simple(event),
                    m_entries[counter - 1]["season"],
                    m_entries[counter - 1]["time"],
                    m_name,
                    counter,
                ]
            else:
                try:
                    row = [
                        counter,
                        f_name,
                        f_entries[counter - 1]["time"],
                        f_entries[counter - 1]["season"],
                        "",
                        m_entries[counter - 1]["season"],
                        m_entries[counter - 1]["time"],
                        m_name,
                        counter,
                    ]
                except IndexError:
                    pass
            table.append(row)
            counter += 1
    date = datetime.datetime.now()
    return (
            f'<h2>Great Hearts Monte Vista<br><span style="color: darkred; font-weight: bold;">PROGRAM '
            f'RECORDS</span></h2>\n<p'
            f'style="color: darkred">UPDATED: {date.day} {date.strftime("%B")[0:3].upper()} {date.year}</p>\n'
            + tabulate(table, headers=headers, tablefmt="html", numalign="center", stralign="center")
    )


async def fetch_top5_relays(db):
    events = ["200RM", "200RF", "400RF"]
    headers = [
        "Rank",
        "Name",
        "Time",
        "Year",
        "Event",
        "Year",
        "Time",
        "Name",
        "Rank",
    ]
    table = []
    for event in events:
        m_entries = await fetch_event_top_five(db, f"M{event}")
        f_entries = await fetch_event_top_five(db, f"F{event}")
        counter = 1
        while counter <= 5:
            f_name = f_entries[counter - 1]["swimmer"]
            m_name = m_entries[counter - 1]["swimmer"]
            if counter == 1:
                row = [
                    counter,
                    f_name,
                    f_entries[counter - 1]["time"],
                    f_entries[counter - 1]["season"],
                    get_event_name_simple(event),
                    m_entries[counter - 1]["season"],
                    m_entries[counter - 1]["time"],
                    m_name,
                    counter,
                ]
            else:
                try:
                    row = [
                        counter,
                        f_name,
                        f_entries[counter - 1]["time"],
                        f_entries[counter - 1]["season"],
                        "",
                        m_entries[counter - 1]["season"],
                        m_entries[counter - 1]["time"],
                        m_name,
                        counter,
                    ]
                except IndexError:
                    pass
            table.append(row)
            counter += 1
    date = datetime.datetime.now()
    return (
            f'<h2>Great Hearts Monte Vista<br><span style="color: darkred; font-weight: bold;">RELAY '
            f'RECORDS</span></h2>\n<p'
            f'style="color: darkred">UPDATED: {date.day} {date.strftime("%B")[0:3].upper()} {date.year}</p>\n'
            + tabulate(table, headers=headers, tablefmt="html", numalign="center", stralign="center")
    )


@router.get("/records/top5/school")
async def get_school_top5(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    return web.Response(body=await fetch_top5_school(db))


@router.get("/records/top5/program")
async def get_program_top5(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    return web.Response(body=await fetch_top5_program(db))


@router.get("/records/top5/relays")
async def get_relay_top5(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    return web.Response(body=await fetch_top5_program(db))


@router.get("/top5/update")
async def update_top5(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    school = await fetch_top5_school(db)
    with open(f'{os.path.expanduser("~")}/shared/top5-school-autoupdated.html', "w") as f:
        f.write(school)
    program = await fetch_top5_program(db)
    with open(f'{os.path.expanduser("~")}/shared/top5-program-autoupdated.html', "w") as f:
        f.write(program)
    relays = await fetch_top5_relays(db)
    with open(f'{os.path.expanduser("~")}/shared/top5-relays-autoupdated.html', "w") as f:
        f.write(relays)
    return web.Response(body="Done!")


# Ping
@router.get("/ping")
@handle_json_error
async def ping_http(request: web.Request) -> web.Response:
    return web.json_response(data={"ping": "pong"})


async def init_db(app: web.Application) -> AsyncIterator[None]:
    db = await asyncpg.create_pool(
        user=creds["database"]["username"],
        password=creds["database"]["password"],
        database=creds["database"]["database"],
        host=creds["database"]["host"],
    )
    app["DB"] = db
    yield
    await db.close()


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(router)
    # Configure default CORS settings.
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        },
    )

    # Configure CORS on all routes.
    for route in list(app.router.routes()):
        print(route)
        cors.add(route)
    app.cleanup_ctx.append(init_db)
    return app


web.run_app(init_app())
