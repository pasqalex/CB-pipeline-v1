import os
import logging
from decimal import Decimal
from datetime import date

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

DB_NAME = os.environ["POSTGRES_DB"]
DB_USER = os.environ["POSTGRES_USER"]
DB_HOST = "db"


def fetch_rates(target_date: date) -> list[tuple]:
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
    rows = []
    for valute in root.findall("Valute"):
        rows.append((
            target_date,
            valute.find("CharCode").text,
            int(valute.find("Nominal").text),
            Decimal(valute.find("Value").text.replace(",", ".")),
        ))

    logger.info("Получено %d валют", len(rows))
    return rows


def load(target_date: date) -> None:
    rows = fetch_rates(target_date)

    with psycopg.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM staging.rates WHERE rate_date = %s", (target_date,))
            with cur.copy("COPY staging.rates (rate_date, char_code, nominal, rate) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
        conn.commit()

    logger.info("Загружено %d строк за %s", len(rows), target_date)


if __name__ == "__main__":
    load(date.today())