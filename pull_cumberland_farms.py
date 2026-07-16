#!/usr/bin/env python3
"""
Crawl the official Cumberland Farms store directory and build:
  cumberland-farms-locations.js
  cumberland-farms-locations.csv

Usage:
  python3 -m pip install requests beautifulsoup4
  python3 pull_cumberland_farms.py

Optional:
  python3 pull_cumberland_farms.py --states MA ME NH VT
  python3 pull_cumberland_farms.py --delay 0.25
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://www.cumberlandfarms.com"
DIRECTORY = f"{BASE}/stores-directory/"
ALL_STATES = ["CT", "FL", "MA", "ME", "NH", "NY", "RI", "VT"]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "BathroomReport location compiler/1.0 (personal project; respectful crawl)"
})

STORE_URL_RE = re.compile(
    r"^https?://(?:www\.)?cumberlandfarms\.com/stores-directory/"
    r"(?P<state>[a-z]{2})/(?P<city>[^/]+)/(?P<street>[^/]+)/(?P<store>\d+)/?$",
    re.I,
)
COORD_RE = re.compile(r"/maps/place/(-?\d+(?:\.\d+)?)%2C(-?\d+(?:\.\d+)?)", re.I)
TIME_RE = re.compile(
    r"(?P<open>\d{1,2}:\d{2}\s*[AP]M)\s*[—-]\s*(?P<close>\d{1,2}:\d{2}\s*[AP]M)",
    re.I,
)


def get(url: str, delay: float) -> requests.Response:
    time.sleep(delay)
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r


def soup(url: str, delay: float) -> BeautifulSoup:
    return BeautifulSoup(get(url, delay).text, "html.parser")


def same_site_directory_links(page: BeautifulSoup, prefix: str) -> list[str]:
    found = set()
    for a in page.select("a[href]"):
        u = urljoin(BASE, a["href"])
        p = urlparse(u)
        normalized = f"{p.scheme}://{p.netloc}{p.path}"
        if normalized.startswith(prefix):
            found.add(normalized.rstrip("/") + "/")
    return sorted(found)


def discover_store_urls(states: list[str], delay: float) -> list[str]:
    stores: set[str] = set()
    for state in states:
        state_url = f"{DIRECTORY}{state.lower()}/"
        print(f"Discovering {state}: {state_url}")
        state_page = soup(state_url, delay)
        city_links = same_site_directory_links(state_page, state_url)

        for i, city_url in enumerate(city_links, 1):
            city_page = soup(city_url, delay)
            links = same_site_directory_links(city_page, city_url)
            for u in links:
                if STORE_URL_RE.match(u):
                    stores.add(u)
            print(f"  {i:>3}/{len(city_links)} cities; {len(stores)} stores found", end="\r")
        print()
    return sorted(stores)


def parse_clock(value: str) -> int:
    value = value.strip().upper().replace(" ", "")
    m = re.match(r"(\d{1,2}):(\d{2})(AM|PM)", value)
    if not m:
        raise ValueError(value)
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "AM":
        hour = 0 if hour == 12 else hour
    else:
        hour = hour if hour == 12 else hour + 12
    return hour * 100 + minute


def normalize_hours(text: str) -> str:
    rows = TIME_RE.findall(text)
    if not rows:
        return ""
    converted = [(parse_clock(a), parse_clock(b)) for a, b in rows]
    if all(a == converted[0][0] and b == converted[0][1] for a, b in converted):
        opening, closing = converted[0]
        if opening == 0 and closing in (2359, 2400):
            return "24"
        # Site often uses 11:59 PM to mean midnight.
        if closing == 2359:
            closing = 2400
        return f"{opening:04d}-{closing:04d}"
    # The app currently supports one hours string, so use a conservative blank
    # when hours differ by day rather than silently publishing wrong hours.
    return ""


def slug(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_store(url: str, delay: float) -> dict:
    page = soup(url, delay)
    full_text = " ".join(page.stripped_strings)

    match = STORE_URL_RE.match(url)
    assert match
    state = match.group("state").upper()
    city_slug = unquote(match.group("city"))
    street_slug = unquote(match.group("street"))
    store_no = match.group("store")

    # Find the primary address block.
    heading_texts = [x.get_text(" ", strip=True) for x in page.select("h1,h2,h3,strong")]
    address_line = ""
    city_state_zip = ""

    # Reliable fallback from visible page text and URL.
    store_match = re.search(r"(.+?)\s+Store No\.\s*(\d+)", full_text, re.I)
    if store_match:
        address_line = store_match.group(1).strip()

    city_match = re.search(
        rf"([A-Z .'-]+),\s*{re.escape(state)},\s*(\d{{5}})",
        full_text,
        re.I,
    )
    if city_match:
        city = city_match.group(1).strip().title()
        zip_code = city_match.group(2)
        city_state_zip = f"{city}, {state} {zip_code}"
    else:
        city = city_slug.replace("-", " ").title()
        zip_code = ""
        city_state_zip = f"{city}, {state}".strip()

    # Coordinates are embedded in the official View Map Google URL.
    lat = lng = None
    for a in page.select("a[href]"):
        href = unquote(a["href"])
        cm = COORD_RE.search(href)
        if cm:
            lat, lng = float(cm.group(1)), float(cm.group(2))
            break
        cm2 = re.search(r"maps/place/(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", href)
        if cm2:
            lat, lng = float(cm2.group(1)), float(cm2.group(2))
            break

    hours = normalize_hours(full_text)

    street_display = address_line.title() if address_line else street_slug.replace("-", " ").title()
    addr = f"{street_display}, {city_state_zip}"
    name_road = re.sub(r"^\d+\s+", "", street_display).strip()
    name = f"{name_road}, {city}"

    unique_id = f"cumberland-{state.lower()}-{slug(city)}-{slug(name_road)}-{store_no}"

    return {
        "n": name,
        "lat": lat,
        "lng": lng,
        "addr": addr,
        "id": unique_id,
        "hrs": hours,
        "_store": store_no,
        "_state": state,
        "_source": url,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", nargs="+", default=ALL_STATES,
                        choices=ALL_STATES, help="States to pull")
    parser.add_argument("--delay", type=float, default=0.35,
                        help="Delay between requests in seconds")
    parser.add_argument("--output", default="cumberland-farms-locations.js")
    args = parser.parse_args()

    urls = discover_store_urls(args.states, args.delay)
    print(f"Found {len(urls)} official store pages.")

    rows = []
    failures = []
    for i, url in enumerate(urls, 1):
        try:
            item = parse_store(url, args.delay)
            rows.append(item)
            print(f"{i:>3}/{len(urls)} {item['addr']}")
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
            print(f"{i:>3}/{len(urls)} ERROR {url}: {exc}")

    # Keep only entries with coordinates because BathroomReport pins require them.
    missing_coords = [x for x in rows if x["lat"] is None or x["lng"] is None]
    clean = [x for x in rows if x["lat"] is not None and x["lng"] is not None]

    # Stable order: state, city/address, store number.
    clean.sort(key=lambda x: (x["_state"], x["addr"], x["_store"]))

    public = [
        {k: x[k] for k in ("n", "lat", "lng", "addr", "id", "hrs")}
        for x in clean
    ]

    output = Path(args.output)
    output.write_text(
        "window.cumberlandFarmsLocations = "
        + json.dumps(public, indent=2, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )

    csv_path = output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["n", "lat", "lng", "addr", "id", "hrs"])
        writer.writeheader()
        writer.writerows(public)

    report = {
        "states": args.states,
        "official_pages_found": len(urls),
        "locations_written": len(public),
        "missing_coordinates": missing_coords,
        "failures": failures,
    }
    Path("cumberland-farms-pull-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print()
    print(f"Wrote {len(public)} locations to {output}")
    print(f"Wrote CSV to {csv_path}")
    print(f"Missing coordinates: {len(missing_coords)}")
    print(f"Failures: {len(failures)}")
    print("Review cumberland-farms-pull-report.json before publishing.")


if __name__ == "__main__":
    main()
