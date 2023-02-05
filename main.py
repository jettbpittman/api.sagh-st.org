import asyncio
import datetime
import json
import random
import re
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Dict, List, TypeAlias, Union
from enum import IntEnum, Enum

import aiosqlite
from aiohttp import web

router = web.RouteTableDef()


class NotFoundException(BaseException):
    pass


def top5Sort(e):
    if len(e['time']) <= 5:
        adjusted_t = f"0:{e['time']}"
        return adjusted_t
    else:
        return e['time']


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
    return (int(ts) << 16) + (year << 20) + (id_type << 24) + (random.randint(1, 1000) << 32)


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


async def fetch_team(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM teams WHERE code = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Team {id} does not exist!")
        return {
            "name": row['name'],
            "address": row['address'],
            "head_coach": row['head_coach'],
            "email": row['email'],
            "phone": row['phone'],
            "code": row['code'],
            "roster": await fetch_team_roster(db, id)
        }


async def fetch_entry(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM entries WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Entry {id} does not exist!")
        return {
            "id": row['id'],
            "swimmer": await fetch_swimmer(db, row['swimmer']),
            "meet": await fetch_meet(db, row['meet']),
            "event": await fetch_event(db, row['event']),
            "seed": row['seed'],
            "time": row['time'],
            "splits": json.loads(row['splits'])
        }


async def fetch_entry_lite(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM entries WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Entry {id} does not exist!")
        return {
            "id": row['id'],
            "meet": await fetch_meet(db, row['meet']),
            "event": await fetch_event(db, row['event']),
            "seed": row['seed'],
            "time": row['time'],
            "splits": json.loads(row['splits'])
        }


async def fetch_event(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM events WHERE code = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Event {id} does not exist!")
        return {
            "code": row['code'],
            "name": row['name'],
            "distance": row['distance'],
            "stroke": row['stroke'],
            "relay": row['relay']
        }


async def fetch_event_all_entries(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM entries WHERE event = ?", [id]
    ) as cursor:
        rows = await cursor.fetchall()
        if not rows:
            raise NotFoundException(f"Event {id} does not exist!")
        entries = []
        for entry in rows:
            e = {
                "swimmer": await fetch_swimmer(db, entry['swimmer']),
                "meet": await fetch_meet(db, entry['meet']),
                "seed": entry['seed'],
                "time": entry['time'],
                "splits": json.loads(entry['splits'])
            }
            entries.append(e)
        return entries


async def fetch_event_top_five(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM entries WHERE event = ?", [id]
    ) as cursor:
        rows = await cursor.fetchall()
        if not rows:
            raise NotFoundException(f"Event {id} does not exist!")
        entries = []
        for entry in rows:
            s = await fetch_swimmer(db, entry['swimmer'])
            name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}"
            m = await fetch_meet(db, entry['meet'])
            e = {
                "swimmer": name,
                "swim_id": s['id'],
                "meet": m['designator'],
                "season": m['season'],
                "time": str(entry['time'])
            }
            entries.append(e)
        entries.sort(key=top5Sort)
        swimmers = []
        top5 = []
        for entry in entries:
            if entry['swim_id'] in swimmers:
                continue
            else:
                swimmers.append(entry['swim_id'])
                top5.append(entry)
        return top5[:5]


async def fetch_entries_by_team(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM entries WHERE team = ?", [id]
    ) as cursor:
        rows = await cursor.fetchall()
        if not rows:
            raise NotFoundException(f"Event {id} does not exist!")
        entries = []
        for entry in rows:
            s = await fetch_swimmer(db, entry['swimmer'])
            name = f"{s['last_name']}, {s['first_name']} {s['middle_name']}"
            m = await fetch_meet(db, entry['meet'])
            e = {
                "swimmer": name,
                "swim_id": s['id'],
                "meet": m['designator'],
                "season": m['season'],
                "time": str(entry['time'])
            }
            entries.append(e)
        entries.sort(key=top5Sort)
        swimmers = []
        top5 = []
        for entry in entries:
            if entry['swim_id'] in swimmers:
                continue
            else:
                swimmers.append(entry['swim_id'])
                top5.append(entry)
        return top5[:5]


async def fetch_team_roster(db: aiosqlite.Connection, id: int):
    async with db.execute(
        "SELECT * FROM swimmers WHERE team = ? AND active = 1", [id]
    ) as cursor:
        rows = await cursor.fetchall()
        roster = []
        for swimmer in rows:
            s = await fetch_swimmer_lite(db, swimmer['id'])
            roster.append(s)
        return roster


async def fetch_team_lite(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM teams WHERE code = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Team {id} does not exist!")
        return {
            "name": row['name'],
            "address": row['address'],
            "head_coach": row['head_coach'],
            "email": row['email'],
            "phone": row['phone'],
            "code": row['code']
        }


async def fetch_swimmer(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM swimmers WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Swimmer {id} does not exist!")
        return {
            "id": row['id'],
            "first_name": row['first_name'],
            "middle_name": row['middle_name'],
            "last_name": row['last_name'],
            "age": row['age'],
            "class": row['class'],
            "team": await fetch_team_lite(db, row['team']),
            "active": row['active']
        }


async def fetch_swimmer_lite(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM swimmers WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Swimmer {id} does not exist!")
        return {
            "id": row['id'],
            "first_name": row['first_name'],
            "middle_name": row['middle_name'],
            "last_name": row['last_name'],
            "age": row['age'],
            "class": row['class'],
            "active": row['active']
        }


async def fetch_meet(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM meets WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Meet {id} does not exist!")
        return {
            "id": row['id'],
            "name": row['name'],
            "venue": row['venue'],
            "designator": row['designator'],
            "date": row['date'],
            "season": row['season']
        }


def handle_json_error(
        func: Callable[[web.Request], Awaitable[web.Response]]
) -> Callable[[web.Request], Awaitable[web.Response]]:
    async def handler(request: web.Request) -> web.Response:
        try:
            return await func(request)
        except asyncio.CancelledError:
            raise
        except NotFoundException as ex:
            return web.json_response(
                {"status": str(ex)}, status=404
            )
        except Exception as ex:
            return web.json_response(
                {"status": "failed", "reason": str(ex)}, status=400
            )
    return handler


# Swimmer Queries
@router.post("/swimmers")
@handle_json_error
async def create_swimmer(request: web.Request) -> web.Response:
    info = await request.json()
    first_name = info['first_name']
    last_name = info['last_name']
    middle_name = info['middle_name']
    age = info['age']
    year = info['class']
    team = info['team']
    if "join_date" in info:
        join_date = info['join_date']
        id = generate_id(1, year, join_date)
    else:
        id = generate_id(1, year)
    if "active" in info:
        active = info['active']
    else:
        active = True
    db = request.config_dict['DB']
    await db.execute(
        "INSERT INTO swimmers (id, first_name, last_name, middle_name, age, class, team, active) VALUES(?, ?, ?, ?, "
        "?, ?, ?, ?)",
        [id, first_name, last_name, middle_name, age, year, team, active]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "age": age,
            "class": year,
            "team": await fetch_team_lite(db, team),
            "active": active
        }
    )


@router.get("/swimmers/{id}")
async def get_swimmers(request: web.Request) -> web.Response:
    swimmer_id = request.match_info['id']
    db = request.config_dict['DB']
    swimmer = await fetch_swimmer(db, swimmer_id)
    return web.json_response(swimmer)


# Team Queries
@router.post("/teams")
async def create_team(request: web.Request) -> web.Response:
    info = await request.json()
    name = info['name']
    address = info['address']
    head_coach = info['head_coach']
    email = info['email']
    phone = info['phone']
    code = info['code']
    id = generate_id(4)
    db = request.config_dict['DB']
    await db.execute(
        "INSERT INTO teams (id, name, address, head_coach, email, phone, code) VALUES(?, ?, ?, ?, ?, ?, ?)",
        [id, name, address, head_coach, email, phone, code]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "name": name,
            "address": address,
            "head_coach": head_coach,
            "email": email,
            "phone": phone,
            "code": code
        }
    )


@router.get("/teams/{id}")
async def get_team(request: web.Request) -> web.Response:
    team_id = request.match_info['id']
    db = request.config_dict['DB']
    team = await fetch_team(db, team_id)
    return web.json_response(team)


# Meet Queries
@router.post("/meets")
async def create_meet(request: web.Request) -> web.Response:
    info = await request.json()
    name = info['name']
    venue = info['venue']
    designator = info['designator']
    date = info['date']
    season = info['season']
    id = generate_id(2)
    db = request.config_dict['DB']
    await db.execute(
        "INSERT INTO meets (id, name, venue, designator, date, season) VALUES(?, ?, ?, ?, ?, ?)",
        [id, name, venue, designator, date, season]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "name": name,
            "venue": venue,
            "designator": designator,
            "date": date,
            "season": season
        }
    )


@router.get("/meets/{id}")
async def get_team(request: web.Request) -> web.Response:
    meet_id = request.match_info['id']
    db = request.config_dict['DB']
    meet = await fetch_meet(db, meet_id)
    return web.json_response(meet)


# Entry Queries
@router.post("/entries")
async def create_entry(request: web.Request) -> web.Response:
    info = await request.json()
    swimmer = info['swimmer']
    meet = info['meet']
    event = info['event']
    seed = info['seed']
    time = info['time']
    splits = list(info['splits'])
    id = generate_id(3)
    splits = json.dumps(splits)
    db = request.config_dict['DB']
    await db.execute(
        "INSERT INTO entries (id, swimmer, meet, event, seed, time, splits) VALUES(?, ?, ?, ?, ?, ?, ?)",
        [id, swimmer, meet, event, seed, time, splits]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "swimmer": await fetch_swimmer(db, swimmer),
            "meet": await fetch_meet(db, meet),
            "event": await fetch_event(db, event),
            "seed": seed,
            "time": time,
            "splits": json.loads(splits)
        }
    )


@router.get("/entries/{id}")
async def get_entry(request: web.Request) -> web.Response:
    entry_id = request.match_info['id']
    db = request.config_dict['DB']
    entry = await fetch_entry(db, entry_id)
    return web.json_response(entry)


@router.get("/events/{code}/all")
@handle_json_error
async def get_event_all(request: web.Request) -> web.Response:
    event_code = request.match_info['code']
    db = request.config_dict['DB']
    entries = await fetch_event_all_entries(db, event_code)
    return web.json_response(entries)


@router.get("/events/{code}/top5")
@handle_json_error
async def get_event_top5(request: web.Request) -> web.Response:
    event_code = request.match_info['code']
    db = request.config_dict['DB']
    entries = await fetch_event_top_five(db, event_code)
    return web.json_response(entries)


# Ping
@router.get("/ping")
@handle_json_error
async def ping_http(request: web.Request) -> web.Response:
    return web.json_response(data={"ping": "pong"})


def get_db_path() -> Path:
    here = Path.cwd()
    while not (here / ".git").exists():
        if here == here.parent:
            raise RuntimeError("Cannot find root github dir")
        here = here.parent

    return here / "db.sqlite3"


async def init_db(app: web.Application) -> AsyncIterator[None]:
    sqlite_db = get_db_path()
    db = await aiosqlite.connect(sqlite_db)
    db.row_factory = aiosqlite.Row
    app["DB"] = db
    yield
    await db.close()


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(router)
    app.cleanup_ctx.append(init_db)
    return app


def try_make_db() -> None:
    sqlite_db = get_db_path()
    if sqlite_db.exists():
        return


try_make_db()

web.run_app(init_app())
