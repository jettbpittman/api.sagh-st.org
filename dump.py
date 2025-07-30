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

mm = hytek_parser.parse_hy3("S254_U.hy3")
d = attrs.asdict(mm)

mm_json: dict = json.loads(orjson.dumps(
        d,
        option=orjson.OPT_NON_STR_KEYS | orjson.OPT_NAIVE_UTC | orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        default=str
    ).decode())

with open("S254_U.json", "w") as f:
    f.write(json.dumps(mm_json))