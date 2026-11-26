# Worldwide Weather Capstone

This project uses Python and Selenium to collect a snapshot of current conditions from [Time and Date’s Weather Around the World](https://www.timeanddate.com/weather/). The scraper reads the default **Worldwide / Most Popular** table and saves one row per city to a CSV. Later stages will load the data into SQLite, support command-line queries, and visualize it in Streamlit.

## Setup

Install Python 3 and Google Chrome. From the project folder, run these commands on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If you already created `.venv`, start with the activation command. On its first run, Selenium may download the Chrome driver automatically.

## Run the scraper

```bash
python scrape_weather.py
```

The scraper opens Chrome in headless mode, waits for the weather table, and writes `weather.csv` in the current folder. Running it again replaces that snapshot. Use `--output` to save a new snapshot under another filename:

```bash
python scrape_weather.py --output weather_new.csv
```

## CSV columns

| Column | Description |
| --- | --- |
| `city`, `country` | Location labels from the source table |
| `condition` | Weather description shown by the site |
| `temperature_c` | Temperature in degrees Celsius |
| `wind_kmh` | Wind speed in kilometers per hour |
| `local_time` | Local day and time as displayed for the city |
| `city_weather_url` | Link to the city’s weather page, used to identify duplicate rows |
| `scraped_at_utc` | UTC timestamp when the scraper read the table |

The scraper trims extra whitespace, standardizes temperature and wind units, and leaves unavailable readings blank. Each CSV captures a single point in time.
