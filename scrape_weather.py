"""Save a snapshot of Time and Date's worldwide weather table as a CSV."""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
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
    };
});
"""


def metric_values(values, pattern, convert_from, convert):
    """Return standardized measurements and a mask of malformed source values."""
    values = values.str.replace("−", "-", regex=False)
    missing = values.isna() | values.str.fullmatch(r"[-–—]|n/a|\?.*", case=False)
    parts = values.mask(missing).str.extract(pattern)
    numbers = pd.to_numeric(parts[0].str.replace(",", ".", regex=False), errors="coerce")
    needs_conversion = parts[1].str.lower().eq(convert_from).fillna(False)
    numbers = numbers.mask(needs_conversion, convert(numbers))
    return numbers.round(1), ~missing & numbers.isna()


def clean_weather(raw_path):
    weather = pd.read_csv(raw_path, dtype="string", keep_default_na=False)
    weather = weather.apply(lambda column: column.str.split().str.join(" ").replace("", pd.NA))

    valid_href = weather["href"].str.fullmatch(r"/weather/[^/?#]+/[^/?#]+", na=False)
    missing_identity = weather[["city", "country", "href"]].isna().any(axis=1)
    invalid_locations = missing_identity | ~valid_href
    duplicates = weather.loc[~invalid_locations, "href"].duplicated().sum()
    print(
        f"Before cleaning: {len(weather)} rows, {duplicates} duplicate city rows, "
        f"{invalid_locations.sum()} rows with missing or invalid location data."
    )
    weather = weather.loc[~invalid_locations].drop_duplicates(subset="href").copy()
    weather["city_weather_url"] = weather["href"].map(lambda href: urljoin(SOURCE_URL, href))

    number = r"([+-]?\d+(?:[.,]\d+)?)"
    weather["temperature_c"], bad_temp = metric_values(
        weather["temperature"], rf"(?i)^{number}\s*°([CF])$", "f", lambda value: (value - 32) * 5 / 9
    )
    weather["wind_kmh"], bad_wind = metric_values(
        weather["wind"], rf"(?i)^{number}\s*(km/h|mph)$", "mph", lambda value: value * 1.609344
    )
    negative_wind = weather["wind_kmh"].lt(0).fillna(False)
    weather["wind_kmh"] = weather["wind_kmh"].mask(negative_wind)

    print(
        f"After cleaning: {len(weather)} rows, "
        f"{weather['city_weather_url'].duplicated().sum()} duplicate city rows. "
        f"Blank temperatures: {weather['temperature_c'].isna().sum()} "
        f"({bad_temp.sum()} malformed). "
        f"Blank wind speeds: {weather['wind_kmh'].isna().sum()} "
        f"({(bad_wind | negative_wind).sum()} malformed)."
    )
    if weather.empty:
        raise ValueError("The raw CSV contains no valid city rows.")
    return weather[list(COLUMNS)]


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

    for row in raw_rows:
        row["scraped_at_utc"] = scraped_at
    return raw_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=Path("weather.csv"))
    args = parser.parse_args()

    raw_path = args.output.with_name(f"{args.output.stem}_raw.csv")
    try:
        records = scrape_weather()
        with raw_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        cleaned = clean_weather(raw_path)
        cleaned.to_csv(args.output, index=False)
    except (OSError, ValueError, WebDriverException) as error:
        parser.exit(1, f"Weather scrape failed: {error}\n")
    print(f"Saved raw data to {raw_path} and {len(cleaned)} cleaned cities to {args.output}")



if __name__ == "__main__":
    main()
