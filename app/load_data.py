import os
import logging
import time
from decimal import Decimal
from datetime import date, timedelta

import requests
import xml.etree.ElementTree as ET
import psycopg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

with open("/run/secrets/db_password") as f:
    DB_PASSWORD = f.read().strip()

DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_HOST = os.environ.get("DB_HOST", "db")


def fetch_rates(target_date: date) -> tuple[list[tuple], list[tuple]]:
    url = "https://www.cbr.ru/scripts/XML_daily.asp"
    logger.info("Запрашиваю курсы за %s", target_date)

    try:
        resp = requests.get(url, params={"date_req": target_date.strftime("%d/%m/%Y")})
        resp.encoding = "cp1251"
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Не удалось получить данные с ЦБ: %s", e)
        raise

    root = ET.fromstring(resp.text)

    rates = []
    currencies = []
    for valute in root.findall("Valute"):
        char_code = valute.find("CharCode").text
        name = valute.find("Name").text

        currencies.append((char_code, name))
        rates.append((
            target_date,
            char_code,
            int(valute.find("Nominal").text),
            Decimal(valute.find("Value").text.replace(",", ".")),
        ))

    logger.info("Получено %d валют", len(rates))
    return rates, currencies


def load(target_date: date) -> None:
    rates, currencies = fetch_rates(target_date)

    with psycopg.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
    ) as conn:
        with conn.cursor() as cur:
            for char_code, name in currencies:
                cur.execute("""
                    INSERT INTO staging.currencies (char_code, currency_name)
                    VALUES (%s, %s)
                    ON CONFLICT (char_code) DO UPDATE
                    SET currency_name = EXCLUDED.currency_name
                """, (char_code, name))

            cur.execute("DELETE FROM staging.rates WHERE rate_date = %s", (target_date,))
            with cur.copy("COPY staging.rates (rate_date, char_code, nominal, rate) FROM STDIN") as copy:
                for row in rates:
                    copy.write_row(row)
        conn.commit()

    logger.info("Загружено %d строк за %s", len(rates), target_date)


if __name__ == "__main__":
    start = date(2025, 7, 15)
    end = date.today()

    current = start
    while current <= end:
        try:
            load(current)
            time.sleep(1)
        except Exception as e:
            logger.error("Ошибка за %s: %s", current, e)
        current += timedelta(days=1)