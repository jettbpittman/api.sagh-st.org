import aiosqlite
import asyncio
import datetime
import json
import pprint
import random
import os
import re
import operator
import base64
import secrets
from passlib.hash import argon2
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable
from enum import Enum
from tabulate import tabulate

import asyncpg
from aiohttp import web
import aiohttp_cors

router = web.RouteTableDef()


class NotFoundException(BaseException):
    pass


with open("creds.json", "r") as f:
    creds = json.load(f)


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


def get_event_name(e):
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
    :param id_type: integer - 1: Swimmer, 2: Meet, 3: Entry, 4: Team, 5: User
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


class Events(Enum):
    TWO_MEDLEY_R = "200 Medley Relay"
    TWO_FREE = "200 Freestyle"
    TWO_IM = "200 Individual Medley"
    FIFTY_FREE = "50 Freestyle"
    ONE_FLY = "100 Butterfly"
    ONE_FREE = "100 Freestyle"
    FIVE_FREE = "500 Freestyle"
    TWO_FREE_R = "200 Freestyle Relay"
    ONE_BACK = "100 Backstroke"
    ONE_BREAST = "100 Breaststroke"
    FOUR_FREE_R = "400 Freestyle Relay"


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
    rows = await db.fetch("SELECT * FROM entries WHERE event = $1", str(id))
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
        "SELECT id FROM swimmers WHERE team = $1 ORDER BY last_name", str(team)
    )
    entries = {}
    m = await fetch_meet(db, meet)
    for swimmer in rows:
        rows2 = await db.fetch(
            "SELECT * FROM entries WHERE meet = $1 AND swimmer = $2",
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
    rows = await db.fetch("SELECT event FROM entries WHERE meet = $1", int(id))
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
        "SELECT * FROM swimmers WHERE team = $1 AND active = true", str(id)
    )
    roster = []
    for swimmer in rows:
        s = await fetch_swimmer_lite(db, swimmer["id"])
        roster.append(s)
    return sorted(roster, key=lambda d: d["last_name"])


async def fetch_team_roster_all(db: asyncpg.Connection, id: str):
    rows = await db.fetch("SELECT * FROM swimmers WHERE team = $1", str(id))
    roster = []
    for swimmer in rows:
        s = await fetch_swimmer_lite(db, swimmer["id"])
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
    entries = await db.fetchrow("SELECT count(*) FROM entries WHERE swimmer = $1", int(id))
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
        "stats": {
            "entries": entries[0],
            "meet_count": len(meets),
            "meets": json.dumps([list(record) for record in meets])
        }
    }


async def fetch_swimmer_entries(db: asyncpg.Connection, id: int):
    rows = await db.fetch("SELECT event FROM entries WHERE swimmer = $1", int(id))
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
        "SELECT * FROM entries WHERE swimmer = $1 AND event = $2", int(id), str(event)
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
        "stats": {
            "entries": entries[0]
        }
    }


async def fetch_meet(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT * FROM meets WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"Meet {id} does not exist!")
    return {
        "id": row["id"],
        "name": row["name"],
        "venue": row["venue"],
        "designator": row["designator"],
        "date": row["date"],
        "season": row["season"],
        "most_recent": row["most_recent"],
    }


async def fetch_all_meets(db: asyncpg.Connection):
    rows = await db.fetch("SELECT * FROM meets")
    if not rows:
        raise NotFoundException(f"Unexpected error!")
    meets = []
    for row in rows:
        meets.append(
            {
                "season": row["season"],
                "id": row["id"],
                "name": row["name"],
                "venue": row["venue"],
                "designator": row["designator"],
                "date": row["date"],
                "most_recent": row["most_recent"],
            }
        )
    meets.sort(key=lambda d: d["season"], reverse=True)
    return meets


async def fetch_meets_by_season(db: asyncpg.Connection, season: int):
    rows = await db.fetch("SELECT * FROM meets WHERE season = $1", int(season))
    if not rows:
        raise NotFoundException(f"No meets in season {season}")
    meets = []
    for row in rows:
        meets.append(
            {
                "season": row["season"],
                "id": row["id"],
                "name": row["name"],
                "venue": row["venue"],
                "designator": row["designator"],
                "date": row["date"],
                "most_recent": row["most_recent"],
            }
        )
    return meets


async def fetch_latest_meet(db: asyncpg.Connection):
    row = await db.fetchrow("SELECT * FROM meets WHERE most_recent = 1")
    if not row:
        raise NotFoundException(f"No recent meet!")
    return {
        "id": row["id"],
        "name": row["name"],
        "venue": row["venue"],
        "designator": row["designator"],
        "date": row["date"],
        "season": row["season"],
        "most_recent": row["most_recent"],
    }


async def fetch_all_users(db: asyncpg.Connection):
    rows = await db.fetch("SELECT id, username, name, email, permissions, active, linked_swimmer FROM users")
    if not rows:
        raise NotFoundException(f"No users found!")
    users = []
    for row in rows:
        users.append(
            {
                "id": row['id'],
                "username": row["username"],
                "name": row["name"],
                "email": row["email"],
                "permissions": row["permissions"],
                "linked_swimmer": row['linked_swimmer'],
                "active": row["active"],
            }
        )
    return users


async def fetch_user(db: asyncpg.Connection, id: int):
    row = await db.fetchrow("SELECT id, username, name, email, permissions, active, linked_swimmer FROM users WHERE id = $1", int(id))
    if not row:
        raise NotFoundException(f"No user found!")
    return {
                "id": row['id'],
                "username": row["username"],
                "name": row["name"],
                "email": row["email"],
                "permissions": row["permissions"],
                "active": row["active"],
                "linked_swimmer": row['linked_swimmer'],
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


@router.post("/auth/check")
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


# User Queries
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
        id, name, password, email, permissions, username,
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
            "active": user['active']
        }
    )


@router.get("/cors-is-so-annoying")
@handle_json_error
async def corsSucks(request: web.Request) -> web.Response:
    return web.json_response({"message": "i bet you can't read this"})


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
    a = await auth_required(request, permissions=2)
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
    a = await auth_required(request, permissions=2)
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
    swimmer_id = request.match_info["id"]
    db = request.config_dict["DB"]
    swimmer = await fetch_swimmer(db, swimmer_id)
    return web.json_response(swimmer)


@router.get("/swimmers/{id}/entries")
async def get_swimmer_all_entries(request: web.Request) -> web.Response:
    swimmer_id = request.match_info["id"]
    db = request.config_dict["DB"]
    entries = await fetch_swimmer_entries(db, swimmer_id)
    return web.json_response(entries)


@router.get("/swimmers/{id}/entries/{event}")
async def get_swimmer_all_entries_event(request: web.Request) -> web.Response:
    swimmer_id = request.match_info["id"]
    event_code = request.match_info["event"]
    db = request.config_dict["DB"]
    entries = await fetch_swimmer_entries_event(db, swimmer_id, event_code)
    return web.json_response(entries)


@router.get("/swimmers/{id}/best")
async def get_swimmer_bests(request: web.Request) -> web.Response:
    swimmer_id = request.match_info["id"]
    db = request.config_dict["DB"]
    entries = await fetch_swimmer_best_times(db, swimmer_id)
    return web.json_response(entries)


# Team Queries
@router.post("/teams")
async def create_team(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
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
async def get_team(request: web.Request) -> web.Response:
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team(db, team_id)
    return web.json_response(team)


@router.get("/teams/{id}/roster/current")
async def get_team_roster_c(request: web.Request) -> web.Response:
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team_roster(db, team_id)
    return web.json_response(team)


@router.get("/teams/{id}/roster/all")
async def get_team_roster_all(request: web.Request) -> web.Response:
    team_id = request.match_info["id"]
    db = request.config_dict["DB"]
    team = await fetch_team_roster_all(db, team_id)
    return web.json_response(team)


# Meet Queries
@router.post("/meets")
async def create_meet(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
    if a.status != 200:
        return a
    info = await request.json()
    name = info["name"]
    venue = info["venue"]
    designator = info["designator"]
    date = info["date"]
    season = info["season"]
    latest = info["most_recent"]
    id = generate_id(2)
    db = request.config_dict["DB"]
    if latest == 1:
        await db.execute("UPDATE meets SET most_recent = 0 WHERE most_recent = 1")
    await db.execute(
        "INSERT INTO meets (id, name, venue, designator, date, season, most_recent) VALUES($1, $2, $3, $4, $5, $6, $7)",
        id,
        name,
        venue,
        designator,
        date,
        season,
        latest,
    )
    return web.json_response(
        {
            "id": id,
            "name": name,
            "venue": venue,
            "designator": designator,
            "date": date,
            "season": season,
            "most_recent": latest,
        }
    )


@router.get("/meets/{id}")
async def get_meet(request: web.Request) -> web.Response:
    meet_id = request.match_info["id"]
    db = request.config_dict["DB"]
    meet = await fetch_meet(db, meet_id)
    return web.json_response(meet)


@router.get("/meets/{id}/entries")
async def get_meet(request: web.Request) -> web.Response:
    meet_id = request.match_info["id"]
    db = request.config_dict["DB"]
    meet = await fetch_entries_by_meet(db, meet_id)
    return web.json_response(meet)


@router.get("/meets")
async def get_all_meets(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    meets = await fetch_all_meets(db)
    return web.json_response(meets)


@router.get("/season/{code}/meets")
async def get_season_meets(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    season = request.match_info["code"]
    meets = await fetch_meets_by_season(db, season)
    return web.json_response(meets)


@router.get("/latest/meet")
async def get_latest_meet(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    meet = await fetch_latest_meet(db)
    return web.json_response(meet)


@router.get("/meets/{meet}/entries/{team}")
async def get_meet_entries_by_team(request: web.Request) -> web.Response:
    meet_id = request.match_info["meet"]
    team_id = request.match_info["team"]
    db = request.config_dict["DB"]
    meet = await fetch_entries_by_team(db, meet=meet_id, team=team_id)
    return web.json_response(meet)


# Entry Queries
@router.post("/entries")
async def create_entry(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=2)
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
async def get_event_top5(request: web.Request) -> web.Response:
    event_code = request.match_info["code"]
    db = request.config_dict["DB"]
    entries = await fetch_event_top_five(db, event_code)
    return web.json_response(entries)


async def fetch_all_top5(db):
    events = ["200F", "200M", "50F", "100L", "100F", "500F", "100B", "100S", "200RM", "200RF", "400RF"]
    headers = [
        "Place",
        "Name",
        "Time",
        "Year",
        "Event",
        "Year",
        "Time",
        "Name",
        "Place",
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
                    get_event_name(event),
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
        f'<h2>GHMV Top 5 All Time</h2>\n<p style="color: darkred">UPDATED: {date.day} {date.strftime("%B")[0:3].upper()} {date.year}</p>\n'
        + tabulate(table, headers=headers, tablefmt="html")
    )


async def fetch_all_top5_unofficial(db):
    events = ["200F", "200M", "50F", "100L", "100F", "500F", "100B", "100S", "200RM", "200RF", "400RF"]
    headers = [
        "Place",
        "Name",
        "Time",
        "Year",
        "Event",
        "Year",
        "Time",
        "Name",
        "Place",
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
                    get_event_name(event),
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
        f'<h2>GHMV Top 5 All Time<br><span style="color: darkred; font-weight: bold;">UNOFFICIAL</span></h2>\n<p style="color: darkred">UPDATED: {date.day} {date.strftime("%B")[0:3].upper()} {date.year}</p>\n'
        + tabulate(table, headers=headers, tablefmt="html")
    )


@router.get("/top5")
async def get_all_top5(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    return web.Response(body=await fetch_all_top5(db))


@router.get("/top5-unofficial")
async def get_all_top5(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    return web.Response(body=await fetch_all_top5_unofficial(db))


@router.get("/top5/update")
async def get_all_top5(request: web.Request) -> web.Response:
    a = await auth_required(request, permissions=4)
    if a.status != 200:
        return a
    db = request.config_dict["DB"]
    top5 = await fetch_all_top5(db)
    with open(f'{os.path.expanduser("~")}/shared/top5-autoupdated.html', "w") as f:
        f.write(top5)
    return web.Response(body=top5)


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
