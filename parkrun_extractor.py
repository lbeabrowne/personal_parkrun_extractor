"""
Parkrun Personal Data Extractor
================================
Extracts your personal parkrun results (Event, Date, Position, Finish Time, Age Grade, Course Personal Best, New Personal Best)
and saves them to a CSV file, including geocoded lat/lon for each event.

Requirements:
    pip install requests beautifulsoup4 python-dotenv

How to get your cookies:
    1. Log in to parkrun.org.uk in Chrome/Firefox
    2. Press F12 to open DevTools
    3. Go to the "Network" tab
    4. Refresh the page
    5. Click on any request to parkrun.org.uk
    6. Scroll to "Request Headers" and find the "Cookie" header
    7. Copy the entire cookie string and paste it into your .env file

.env file format:
    PARKRUN_ID=A1234567
    COOKIE_STRING=your_cookie_string_here
"""

import requests
import os
import time
import urllib3
from bs4 import BeautifulSoup
import csv
from urllib.parse import unquote
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
PARKRUN_ID = os.getenv("PARKRUN_ID")
COOKIE_STRING = os.getenv("COOKIE_STRING")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parkrun_results.csv")

# Map parkrun domains to ISO country codes for geocoding
DOMAIN_TO_COUNTRY = {
    "parkrun.org.uk":  "gb",
    "parkrun.co.at":   "at",
    "parkrun.com.au":  "au",
    "parkrun.co.za":   "za",
    "parkrun.lt":      "lt",
    "parkrun.us":      "us",
    "parkrun.ie":      "ie",
    "parkrun.dk":      "dk",
    "parkrun.fi":      "fi",
    "parkrun.fr":      "fr",
    "parkrun.it":      "it",
    "parkrun.de":      "de",
    "parkrun.pl":      "pl",
    "parkrun.se":      "se",
    "parkrun.no":      "no",
    "parkrun.sg":      "sg",
    "parkrun.co.nz":   "nz",
    "parkrun.com.ar":  "ar",
    "parkrun.ru":      "ru",
    "parkrun.ca":      "ca",
    "parkrun.jp":      "jp",
    "parkrun.co.zw":   "zw",
    "parkrun.com.my":  "my",
}


def parse_cookies(cookie_string):
    """Convert a raw cookie string into a dict."""
    cookie_string = unquote(cookie_string)
    cookies = {}
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, value = part.partition("=")
            cookies[key.strip()] = value.strip()
    return cookies


def fetch_results(parkrun_id, cookies):
    """Fetch the full results page for a given athlete."""
    num = parkrun_id.lstrip("Aa")
    url = f"https://www.parkrun.org.uk/parkrunner/{num}/all/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.parkrun.org.uk/",
    }

    print(f"Fetching results from: {url}")
    response = requests.get(url, headers=headers, cookies=cookies, timeout=15)

    if response.status_code == 403:
        raise PermissionError(
            "Access denied (403). Your cookies may have expired — "
            "please refresh them from your browser and try again."
        )
    if response.status_code != 200:
        raise ConnectionError(f"Unexpected status code: {response.status_code}")

    return response.text


def parse_results(html):
    """Parse the All Results table from the HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    # Get the 3rd table on the page (index 2)
    all_tables = soup.find_all("table")
    if len(all_tables) < 3:
        raise ValueError("Could not find the results table — fewer than 3 tables on the page.")
    table = all_tables[2]

    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]

    results = []
    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) < 5:
            continue

        # Extract href from the event name link in the first column
        first_td = row.find("td")
        link = first_td.find("a") if first_td else None
        href = link["href"] if link and link.has_attr("href") else ""

        result = extract_row(cols, href)
        if result:
            results.append(result)

    # Calculate overall personal best across all events
    # Results are newest first, so reverse to process chronologically
    chronological = list(reversed(results))
    best_seconds = None
    for r in chronological:
        parts = r["Finish Time"].split(":")
        try:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            if best_seconds is None or seconds < best_seconds:
                r["New Personal Best"] = "Yes"
                best_seconds = seconds
            else:
                r["New Personal Best"] = "No"
        except Exception:
            r["New Personal Best"] = "No"

    # Restore original order (newest first)
    return list(reversed(chronological))


def extract_row(cols, href=""):
    """Extract fields from a table row using fixed column positions.

    Columns: Event | Run Date | Run Number | Pos | Time | Age Grade | PB?
    """
    if len(cols) < 5:
        return None

    event      = cols[0].strip()
    date_str   = cols[1].strip()
    run_number = cols[2].strip()
    position   = cols[3].strip()
    raw_time   = cols[4].strip()

    parts = raw_time.split(":")
    if len(parts) == 2:
        finish_time = f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    elif len(parts) == 3:
        finish_time = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    else:
        finish_time = raw_time

    age_grade = cols[5].strip() if len(cols) > 5 else ""
    pb        = "Yes" if len(cols) > 6 and cols[6].strip() in ("PB", "New PB", "First Timer!") else "No"

    if not finish_time:
        return None

    return {
        "Event":                event,
        "Date":                 date_str,
        "Position":             position,
        "Finish Time":          finish_time,
        "Age Grade":            age_grade,
        "Course Personal Best": pb,
        "Event URL":            href,  # used internally for geocoding, not saved to CSV
    }


def geocode_events(results):
    """Add Latitude and Longitude columns by geocoding unique event names."""
    cache = {}
    unique_events = list({r["Event"] for r in results if r["Event"]})
    print(f"\n🌍 Geocoding {len(unique_events)} unique event location(s)...")

    session = requests.Session()
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    for event in unique_events:
        if event in cache:
            continue

        # Determine country code from the event URL
        sample = next((r for r in results if r["Event"] == event), None)
        href = sample.get("Event URL", "") if sample else ""
        country_code = "gb"  # default to GB
        for domain, code in DOMAIN_TO_COUNTRY.items():
            if domain in href:
                country_code = code
                break

        for query in [f"{event} parkrun", event]:
            try:
                time.sleep(1)
                # Try with country code first
                response = session.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": query, "format": "json", "limit": 1, "countrycodes": country_code},
                    headers={"User-Agent": "parkrun_personal_extractor"},
                    timeout=10
                )
                data = response.json()

                if not data:
                    # Fall back to worldwide search
                    time.sleep(1)
                    response = session.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"q": query, "format": "json", "limit": 1},
                        headers={"User-Agent": "parkrun_personal_extractor"},
                        timeout=10
                    )
                    data = response.json()

                if data:
                    cache[event] = (round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6))
                    print(f"   ✅ {event} ({country_code}) → {cache[event]}")
                    break

            except Exception as e:
                print(f"   ❌ Geocoding error for {event}: {e}")
                cache[event] = (None, None)
        else:
            if event not in cache:
                cache[event] = (None, None)
                print(f"   ⚠️  Could not geocode: {event}")

    # Apply cached coordinates to all rows
    for r in results:
        lat, lon = cache.get(r["Event"], (None, None))
        r["Latitude"]  = lat
        r["Longitude"] = lon

    return results


def save_to_csv(results, filename):
    """Save results list to a CSV file."""
    if not results:
        print("No results found to save.")
        return

    # Event URL was used internally only — exclude from CSV output
    fieldnames = [
        "Event", "Date", "Position", "Finish Time", "Age Grade",
        "Course Personal Best", "New Personal Best", "Latitude", "Longitude"
    ]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Saved {len(results)} results to '{filename}'")


def print_summary(results):
    """Print a quick summary to the terminal."""
    if not results:
        return

    times = []
    for r in results:
        t = r["Finish Time"]
        try:
            parts = list(map(int, t.split(":")))
            if len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
            else:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            times.append(seconds)
        except Exception:
            pass

    print(f"\n📊 Summary for athlete {PARKRUN_ID}")
    print(f"   Total runs : {len(results)}")

    if times:
        def fmt(s):
            m, sec = divmod(s, 60)
            return f"{m}:{sec:02d}"

        print(f"   Fastest    : {fmt(min(times))}")
        print(f"   Slowest    : {fmt(max(times))}")
        print(f"   Average    : {fmt(int(sum(times) / len(times)))}")

    locations = list({r["Event"] for r in results if r["Event"]})
    print(f"   Locations  : {len(locations)} unique events")
    for loc in sorted(locations):
        print(f"              - {loc}")


def main():
    if not PARKRUN_ID or PARKRUN_ID == "A1234567":
        print("❌ Please set PARKRUN_ID in your .env file before running.")
        return
    if not COOKIE_STRING or COOKIE_STRING == "your_cookie_string_here":
        print("❌ Please set COOKIE_STRING in your .env file before running.")
        return

    cookies = parse_cookies(COOKIE_STRING)

    try:
        html = fetch_results(PARKRUN_ID, cookies)
    except (PermissionError, ConnectionError) as e:
        print(f"❌ {e}")
        return

    try:
        results = parse_results(html)
    except ValueError as e:
        print(f"❌ {e}")
        return

    if not results:
        print("⚠️  No results could be parsed. The page structure may have changed.")
        return

    print_summary(results)
    results = geocode_events(results)
    save_to_csv(results, OUTPUT_FILE)


if __name__ == "__main__":
    main()