"""Save a snapshot of Time and Date's worldwide weather table as a CSV."""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

SOURCE_URL = "https://www.timeanddate.com/weather/"
COLUMNS = (
    "city", "country", "condition", "temperature_c", "wind_kmh",
    "local_time", "city_weather_url", "scraped_at_utc",
)

# Select cells by purpose so a missing-weather colspan cannot shift the data.
READ_TABLE = """
const cityCells = document.querySelectorAll('tbody td.tad-weather-table__city-cell');
return Array.from(cityCells, cityCell => {
    const row = cityCell.closest('tr');
    const cell = name => row.querySelector('.tad-weather-table__' + name + '-cell');
    const value = name => cell(name)?.innerText ?? '';
    return {
        city: value('city'),
        country: value('country'),
        condition: value('condition'),
        temperature: value('temperature'),
        wind: value('wind'),
        local_time: value('time'),
        href: cityCell.querySelector('a')?.getAttribute('href') ?? '',
        unavailable: Boolean(row.querySelector('.tad-weather-table__row-data-unavailable')),
    };
});
"""


def clean_text(value):
    return " ".join(value.split())


def metric_value(value, unit):
    value = clean_text(value).replace("−", "-")
    if not value or value in {"-", "–", "—", "N/A"} or value.startswith("?"):
        return None
    pattern = r"([+-]?\d+(?:[.,]\d+)?)\s*" + unit
    match = re.fullmatch(pattern, value, re.IGNORECASE)
    if match is None:
        raise ValueError(f"Unexpected weather reading {value!r}")
    number = float(match[1].replace(",", "."))
    if unit == "°[CF]" and value.upper().endswith("F"):
        number = (number - 32) * 5 / 9
    if unit == "(?:km/h|mph)" and value.lower().endswith("mph"):
        number *= 1.609344
    return round(number, 1)


def scrape_weather():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--lang=en-US")
    options.page_load_strategy = "eager"

    with webdriver.Chrome(options=options) as browser:
        browser.set_page_load_timeout(30)
        browser.get(SOURCE_URL)
        raw_rows = WebDriverWait(browser, 20).until(
            lambda driver: driver.execute_script(READ_TABLE),
            "The worldwide weather table did not load.",
        )
        scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    records = {}
    for row in raw_rows:
        city = clean_text(row["city"])
        country = clean_text(row["country"])
        if not (city and country and row["href"]):
            raise ValueError(f"Incomplete location data for {city or 'a table row'}.")

        city_url = urljoin(SOURCE_URL, row["href"])
        unavailable = row["unavailable"]
        records[city_url] = {
            "city": city,
            "country": country,
            "condition": "" if unavailable else clean_text(row["condition"]),
            "temperature_c": None if unavailable else metric_value(row["temperature"], "°[CF]"),
            "wind_kmh": None if unavailable else metric_value(row["wind"], "(?:km/h|mph)"),
            "local_time": clean_text(row["local_time"]),
            "city_weather_url": city_url,
            "scraped_at_utc": scraped_at,
        }
    return list(records.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=Path("weather.csv"))
    args = parser.parse_args()

    try:
        records = scrape_weather()
        with args.output.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(records)
    except (OSError, ValueError, WebDriverException) as error:
        parser.exit(1, f"Weather scrape failed: {error}\n")
    print(f"Saved {len(records)} cities to {args.output}")


if __name__ == "__main__":
    main()
