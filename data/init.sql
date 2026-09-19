CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE staging.rates (
    rate_date DATE NOT NULL,
    char_code VARCHAR(3) NOT NULL,
    nominal INTEGER NOT NULL,
    rate NUMERIC(20, 6) NOT NULL,
    PRIMARY KEY (rate_date, char_code)
);