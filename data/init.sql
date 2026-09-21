CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE staging.currencies (
    char_code VARCHAR(3) PRIMARY KEY,
    currency_name VARCHAR(100) NOT NULL
);

CREATE TABLE staging.rates (
    rate_date DATE NOT NULL,
    char_code VARCHAR(3) NOT NULL,
    nominal INTEGER NOT NULL,
    rate NUMERIC(20, 6) NOT NULL,
    PRIMARY KEY (rate_date, char_code)
);

CREATE OR REPLACE VIEW staging.rates_with_names AS
SELECT
    r.rate_date,
    r.char_code,
    c.currency_name,
    r.nominal,
    r.rate
FROM staging.rates r
JOIN staging.currencies c USING (char_code);