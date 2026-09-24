# Курсы валют ЦБ РФ - ETL-пайплайн

Простой ETL-пайплайн: ежедневные курсы валют с сайта Центрального банка РФ
(официальный XML-сервис) загружаются в PostgreSQL для дальнейшего анализа.

## Как это работает

1. Скрипт `app/load_data.py` запрашивает у ЦБ РФ (https://www.cbr.ru/scripts/XML_daily.asp)
   курсы валют за каждый день в заданном диапазоне дат.
2. XML ответ парсится и нормализуется: денежные значения конвертируются
   из строки с запятой в `Decimal`.
3. Данные загружаются в PostgreSQL в схему `staging`:
   - справочник валют (`staging.currencies`) обновляется через `INSERT ... ON CONFLICT`;
   - курсы (`staging.rates`) загружаются пакетно через `COPY FROM STDIN` -
   предварительно удаляются строки за этот день, поэтому загрузка идемпотентна.
4. Представление `staging.rates_with_names` соединяет курсы с названиями валют.

## Структура репозитория

```
.
├── app/
│   └── load_data.py        # ETL-скрипт
├── data/
│   └── init.sql            # схема и представление БД
├── .devcontainer/          # конфигурация Dev Container
├── docker-compose.yml      # оркестрация: БД + приложение
├── Dockerfile.prod         # production-образ приложения
├── Dockerfile.debug        # debug/dev-образ приложения
├── .dockerignore
├── .gitignore
└── requirements.txt
```

## Стек

- Python 3.11 (`requests`, `psycopg` 3)
- PostgreSQL 18
- Docker + Docker Compose

## Запуск

### 1. Подготовьте файл с паролем

```bash
mkdir -p secrets
echo "your_password" > secrets/db_password.txt
```

### 2. Создайте `.env` в корне проекта

```env
POSTGRES_USER=postgres
POSTGRES_DB=central_bank
```

### 3. Запустите

```bash
docker compose up --build
```

Контейнер `app` дождётся готовности БД (healthcheck) и начнёт загрузку данных.

## Безопасность

- Пароль БД передаётся через **Docker secrets** (`/run/secrets/db_password`),
  он не попадает ни в переменные окружения, ни в git.
- Параметр `no-new-privileges:true` для контейнера БД запрещает повышение
  привилегий процессами.
- Production-образ запускается от непривилегированного пользователя `contuser`
  и собирается в два этапа: зависимости устанавливаются в отдельном builder-слое.

## Схема данных

| Таблица              | Описание                                        |
|----------------------|-------------------------------------------------|
| `staging.currencies` | Справочник валют: код (ISO 4217) и название     |
| `staging.rates`      | Курсы: дата, код валюты, номинал, курс в рублях |
| `staging.rates_with_names` | View: курсы + названия валют              |

Курсы хранятся в `NUMERIC(20, 6)` - без потерь точности на плавающей точке.

## Пример запроса

```sql
SELECT rate_date, char_code, currency_name, nominal, rate
FROM staging.rates_with_names
WHERE char_code = 'USD'
ORDER BY rate_date DESC
LIMIT 10;
```

## Примечания

- Между запросами к ЦБ есть пауза 1 секунда, чтобы не нагружать сервис.
- Ошибки за отдельный день логируются, но не прерывают загрузку остальных дат.
- Диапазон загрузки задаётся в `load_data.py` (`start = date(2025, 7, 15)`).
