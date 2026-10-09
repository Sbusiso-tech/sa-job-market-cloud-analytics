"""Map free-text South African locations (and Adzuna ``location.area`` lists) to one of the 9 provinces."""
from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

GAUTENG = "Gauteng"
WESTERN_CAPE = "Western Cape"
KWAZULU_NATAL = "KwaZulu-Natal"
EASTERN_CAPE = "Eastern Cape"
FREE_STATE = "Free State"
LIMPOPO = "Limpopo"
MPUMALANGA = "Mpumalanga"
NORTH_WEST = "North West"
NORTHERN_CAPE = "Northern Cape"
REMOTE = "Remote"
UNKNOWN = "Unknown"

SA_PROVINCES = (
    GAUTENG,
    WESTERN_CAPE,
    KWAZULU_NATAL,
    EASTERN_CAPE,
    FREE_STATE,
    LIMPOPO,
    MPUMALANGA,
    NORTH_WEST,
    NORTHERN_CAPE,
)
PROVINCES = (*SA_PROVINCES, REMOTE, UNKNOWN)

PROVINCE_ALIASES = {
    "gauteng": GAUTENG,
    "western cape": WESTERN_CAPE,
    "west cape": WESTERN_CAPE,
    "kwazulu-natal": KWAZULU_NATAL,
    "kwazulu natal": KWAZULU_NATAL,
    "kwa-zulu natal": KWAZULU_NATAL,
    "kwazulu": KWAZULU_NATAL,
    "kzn": KWAZULU_NATAL,
    "natal": KWAZULU_NATAL,
    "eastern cape": EASTERN_CAPE,
    "free state": FREE_STATE,
    "freestate": FREE_STATE,
    "orange free state": FREE_STATE,
    "limpopo": LIMPOPO,
    "mpumalanga": MPUMALANGA,
    "north west": NORTH_WEST,
    "north-west": NORTH_WEST,
    "northwest": NORTH_WEST,
    "northern cape": NORTHERN_CAPE,
}

CITY_TO_PROVINCE = {
    # Gauteng
    "johannesburg": GAUTENG,
    "joburg": GAUTENG,
    "jhb": GAUTENG,
    "johannesburg cbd": GAUTENG,
    "sandton": GAUTENG,
    "rosebank": GAUTENG,
    "fourways": GAUTENG,
    "bryanston": GAUTENG,
    "rivonia": GAUTENG,
    "sunninghill": GAUTENG,
    "woodmead": GAUTENG,
    "midrand": GAUTENG,
    "randburg": GAUTENG,
    "roodepoort": GAUTENG,
    "soweto": GAUTENG,
    "parktown": GAUTENG,
    "braamfontein": GAUTENG,
    "melrose": GAUTENG,
    "illovo": GAUTENG,
    "bedfordview": GAUTENG,
    "germiston": GAUTENG,
    "boksburg": GAUTENG,
    "benoni": GAUTENG,
    "kempton park": GAUTENG,
    "edenvale": GAUTENG,
    "alberton": GAUTENG,
    "springs": GAUTENG,
    "ekurhuleni": GAUTENG,
    "east rand": GAUTENG,
    "west rand": GAUTENG,
    "krugersdorp": GAUTENG,
    "pretoria": GAUTENG,
    "pretoria east": GAUTENG,
    "tshwane": GAUTENG,
    "centurion": GAUTENG,
    "menlyn": GAUTENG,
    "hatfield": GAUTENG,
    "irene": GAUTENG,
    "vereeniging": GAUTENG,
    "vanderbijlpark": GAUTENG,
    "isando": GAUTENG,
    "olifantsfontein": GAUTENG,
    # Western Cape
    "cape town": WESTERN_CAPE,
    "cape town cbd": WESTERN_CAPE,
    "city of cape town": WESTERN_CAPE,
    "stellenbosch": WESTERN_CAPE,
    "bellville": WESTERN_CAPE,
    "century city": WESTERN_CAPE,
    "claremont": WESTERN_CAPE,
    "durbanville": WESTERN_CAPE,
    "tyger valley": WESTERN_CAPE,
    "tygervalley": WESTERN_CAPE,
    "brackenfell": WESTERN_CAPE,
    "parow": WESTERN_CAPE,
    "goodwood": WESTERN_CAPE,
    "somerset west": WESTERN_CAPE,
    "paarl": WESTERN_CAPE,
    "wellington": WESTERN_CAPE,
    "george": WESTERN_CAPE,
    "mossel bay": WESTERN_CAPE,
    "knysna": WESTERN_CAPE,
    "worcester": WESTERN_CAPE,
    "woodstock": WESTERN_CAPE,
    "observatory": WESTERN_CAPE,
    "sea point": WESTERN_CAPE,
    "green point": WESTERN_CAPE,
    "pinelands": WESTERN_CAPE,
    "milnerton": WESTERN_CAPE,
    "montague gardens": WESTERN_CAPE,
    "epping": WESTERN_CAPE,
    "strand": WESTERN_CAPE,
    "west coast": WESTERN_CAPE,
    "cape winelands": WESTERN_CAPE,
    # KwaZulu-Natal
    "durban": KWAZULU_NATAL,
    "ethekwini": KWAZULU_NATAL,
    "umhlanga": KWAZULU_NATAL,
    "umhlanga rocks": KWAZULU_NATAL,
    "pinetown": KWAZULU_NATAL,
    "westville": KWAZULU_NATAL,
    "ballito": KWAZULU_NATAL,
    "pietermaritzburg": KWAZULU_NATAL,
    "msunduzi": KWAZULU_NATAL,
    "richards bay": KWAZULU_NATAL,
    "newcastle": KWAZULU_NATAL,
    "ladysmith": KWAZULU_NATAL,
    "la lucia": KWAZULU_NATAL,
    "new germany": KWAZULU_NATAL,
    "hillcrest": KWAZULU_NATAL,
    # Eastern Cape
    "gqeberha": EASTERN_CAPE,
    "port elizabeth": EASTERN_CAPE,
    "nelson mandela bay": EASTERN_CAPE,
    "east london": EASTERN_CAPE,
    "buffalo city": EASTERN_CAPE,
    "mthatha": EASTERN_CAPE,
    "makhanda": EASTERN_CAPE,
    "grahamstown": EASTERN_CAPE,
    "uitenhage": EASTERN_CAPE,
    "kariega": EASTERN_CAPE,
    "jeffreys bay": EASTERN_CAPE,
    # Free State
    "bloemfontein": FREE_STATE,
    "mangaung": FREE_STATE,
    "welkom": FREE_STATE,
    "sasolburg": FREE_STATE,
    "bethlehem": FREE_STATE,
    "kroonstad": FREE_STATE,
    # Limpopo
    "polokwane": LIMPOPO,
    "pietersburg": LIMPOPO,
    "tzaneen": LIMPOPO,
    "lephalale": LIMPOPO,
    "thohoyandou": LIMPOPO,
    "mokopane": LIMPOPO,
    "phalaborwa": LIMPOPO,
    # Mpumalanga
    "mbombela": MPUMALANGA,
    "nelspruit": MPUMALANGA,
    "witbank": MPUMALANGA,
    "emalahleni": MPUMALANGA,
    "middelburg": MPUMALANGA,
    "secunda": MPUMALANGA,
    "ermelo": MPUMALANGA,
    "white river": MPUMALANGA,
    # North West
    "rustenburg": NORTH_WEST,
    "mahikeng": NORTH_WEST,
    "mafikeng": NORTH_WEST,
    "potchefstroom": NORTH_WEST,
    "klerksdorp": NORTH_WEST,
    "brits": NORTH_WEST,
    "hartbeespoort": NORTH_WEST,
    # Northern Cape
    "kimberley": NORTHERN_CAPE,
    "upington": NORTHERN_CAPE,
    "kathu": NORTHERN_CAPE,
    "springbok": NORTHERN_CAPE,
}

_REMOTE = re.compile(r"\b(?:remote|work from home|wfh|home[- ]based|anywhere)\b", re.IGNORECASE)
_COUNTRY = {"south africa", "za", "rsa", "suid-afrika"}


@lru_cache(maxsize=1)
def _lookup_pattern() -> re.Pattern:
    names = sorted({*PROVINCE_ALIASES, *CITY_TO_PROVINCE}, key=len, reverse=True)
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(n) for n in names) + r")(?![a-z])")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_province(value: str | None) -> str | None:
    """Return the canonical province value (one of ``PROVINCES``) for user input, else ``None``."""
    if not isinstance(value, str):
        return None
    cleaned = _clean(value)
    for province in PROVINCES:
        if province.lower() == cleaned:
            return province
    return PROVINCE_ALIASES.get(cleaned)


def _match(text: str) -> str | None:
    match = _lookup_pattern().search(_clean(text))
    if not match:
        return None
    key = match.group(1)
    return PROVINCE_ALIASES.get(key) or CITY_TO_PROVINCE.get(key)


def _city_from(location: str | None, area: list[str]) -> str | None:
    for candidate in reversed(area):
        cleaned = _clean(candidate)
        if cleaned in _COUNTRY or cleaned in PROVINCE_ALIASES:
            continue
        return candidate.strip()
    if location:
        first = location.split(",")[0].strip()
        cleaned = _clean(first)
        if first and cleaned not in _COUNTRY and cleaned not in PROVINCE_ALIASES and not _REMOTE.search(first):
            return first
    return None


def resolve_location(
    location: str | None, area: Iterable[str] | None = None, title: str | None = None
) -> tuple[str, str | None, bool]:
    """Return ``(province, city, is_remote)``.

    Adzuna's ``area`` list (``["South Africa", "Gauteng", "Johannesburg", "Sandton"]``) wins when it names a
    province; otherwise the most specific known city/suburb/metro in the area or display name decides.
    """
    area_list = [a for a in (area or []) if isinstance(a, str) and a.strip()]
    is_remote = bool(_REMOTE.search(location or "")) or bool(_REMOTE.search(title or ""))
    province = None
    for candidate in area_list:
        found = PROVINCE_ALIASES.get(_clean(candidate))
        if found:
            province = found
            break
    if province is None:
        for candidate in [*reversed(area_list), location or ""]:
            province = _match(candidate) if candidate else None
            if province:
                break
    city = _city_from(location, area_list)
    if province is None:
        province = REMOTE if is_remote else UNKNOWN
    return province, city, is_remote
