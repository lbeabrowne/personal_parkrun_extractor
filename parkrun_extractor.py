"""
Parkrun Personal Data Extractor
================================
Extracts your personal parkrun results (Event, Date, Position, Finish Time, Age Grade, Course Personal Best, New Personal Best)
and saves them to a CSV file.

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
    ATHLETE_NUMBER=A1234567
    COOKIE_STRING=your_cookie_string_here
"""

import requests
import os
from bs4 import BeautifulSoup
import csv
from urllib.parse import unquote
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
ATHLETE_NUMBER = os.getenv("ATHLETE_NUMBER")
COOKIE_STRING = os.getenv("COOKIE_STRING")

OUTPUT_FILE = "parkrun_results.csv"


def parse_cookies(cookie_string):
    """Convert a raw cookie string into a dict."""
    # Decode URL encoding first (e.g. %3B → ; and %20 → space)
    cookie_string = unquote(cookie_string)
    cookies = {}
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, value = part.partition("=")
            cookies[key.strip()] = value.strip()
    return cookies


def fetch_results(athlete_number, cookies):
    """Fetch the full results page for a given athlete."""
    # Strip leading 'A' if present
    num = athlete_number.lstrip("Aa")
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

        result = extract_row(cols)
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


def extract_row(cols):
    """Extract fields from a table row using fixed column positions.

    Columns: Event | Run Date | Run Number | Pos | Time | Age Grade | PB?
    """
    if len(cols) < 5:
        return None

    event       = cols[0].strip()
    date_str    = cols[1].strip()
    run_number  = cols[2].strip()
    position    = cols[3].strip()
    raw_time = cols[4].strip()
    parts = raw_time.split(":")
    if len(parts) == 2:
        finish_time = f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    elif len(parts) == 3:
        finish_time = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    else:
        finish_time = raw_time
    age_grade   = cols[5].strip() if len(cols) > 5 else ""
    pb          = "Yes" if len(cols) > 6 and cols[6].strip() in ("PB", "New PB", "First Timer!") else "No"

    if not finish_time:
        return None

    return {
        "Event":                event,
        "Date":                 date_str,
        # "Run Number":           run_number, # removed
        "Position":             position,
        "Finish Time":          finish_time,
        "Age Grade":            age_grade,
        "Course Personal Best": pb,
    }


def save_to_csv(results, filename):
    """Save results list to a CSV file."""
    if not results:
        print("No results found to save.")
        return

    fieldnames = ["Event", "Date", "Position", "Finish Time", "Age Grade", "Course Personal Best", "New Personal Best"]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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

    print(f"\n📊 Summary for athlete {ATHLETE_NUMBER}")
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
    if not ATHLETE_NUMBER or ATHLETE_NUMBER == "A1234567":
        print("❌ Please set ATHLETE_NUMBER in your .env file before running.")
        return
    if not COOKIE_STRING or COOKIE_STRING == "your_cookie_string_here":
        print("❌ Please set COOKIE_STRING in your .env file before running.")
        return

    cookies = parse_cookies(COOKIE_STRING)

    try:
        html = fetch_results(ATHLETE_NUMBER, cookies)
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
    save_to_csv(results, OUTPUT_FILE)


if __name__ == "__main__":
    main()