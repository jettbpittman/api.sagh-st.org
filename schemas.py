import datetime
from enum import Enum


class Meet:
    """
    Swim Meet
    """
    id: int
    designator: str
    name: str
    venue: str
    date: datetime.datetime


class Swimmer:
    """
    Swimmer
    """
    first_name: str
    last_name: str
    middle_name: str
    id: int
    dob: str
    age: int
    grade: int
    team: str


class Team:
    """
    Team
    """
    name: str
    id: int
    address: str
    head_coach: str
    email: str
    code: str
    roster: [Swimmer]


class Entry:
    """
    Meet Entry
    """
    swimmer: Swimmer
    event: Events
    seed: float
    time: float
    splits: [int]


class Events(Enum):
    """
    List of Events and Codes
    """
    TWO_MEDLEY_R = "200 Medley Relay"
    TWO_FREE = "200 Freestyle"
    TWO_IM = "200 Individual Medley"
    FIFTY_FREE = "50 Freestyle"
    ONE_DIVING = "1 meter Diving"
    ONE_FLY = "100 Butterfly"
    ONE_FREE = "100 Freestyle"
    FIVE_FREE = "500 Freestyle"
    TWO_FREE_R = "200 Freestyle Relay"
    ONE_BACK = "100 Backstroke"
    ONE_BREAST = "100 Breaststroke"
    FOUR_FREE_R = "400 Freestyle Relay"

