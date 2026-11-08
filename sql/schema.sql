-- Схема хранилища контент-аналитики LADA Цифра.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS offers (
    offer_id        INTEGER PRIMARY KEY,
    source          TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    brand           TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    trim            TEXT    NOT NULL DEFAULT '',
    year            INTEGER NOT NULL,
    price           INTEGER NOT NULL,
    currency        TEXT    NOT NULL DEFAULT 'INR',
    km_driven       INTEGER NOT NULL,
    fuel            TEXT    NOT NULL,
    seller          TEXT    NOT NULL,
    transmission    TEXT    NOT NULL,
    owner           TEXT    NOT NULL,
    mileage_kmpl    REAL,
    engine_cc       INTEGER,
    power_bhp       REAL,
    torque          TEXT,
    seats           INTEGER,
    listed_at       TEXT    NOT NULL,
    listed_at_source TEXT   NOT NULL DEFAULT 'simulated'
);

CREATE INDEX IF NOT EXISTS ix_offers_brand ON offers (brand);
CREATE INDEX IF NOT EXISTS ix_offers_period ON offers (listed_at);
CREATE INDEX IF NOT EXISTS ix_offers_model ON offers (brand, model);

CREATE TABLE IF NOT EXISTS catalog_models (
    catalog_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    brand           TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    trim            TEXT    NOT NULL DEFAULT '',
    year_from       INTEGER,
    year_to         INTEGER,
    fuel            TEXT,
    transmission    TEXT,
    engine_cc       INTEGER,
    power_bhp       REAL,
    seats           INTEGER,
    external_id     TEXT,
    updated_at      TEXT    NOT NULL,
    UNIQUE (brand, model, trim, fuel, transmission)
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    source      TEXT NOT NULL,
    pages       INTEGER NOT NULL DEFAULT 0,
    records     INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'running',
    note        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS qa_runs (
    run_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    offers     INTEGER NOT NULL,
    findings   INTEGER NOT NULL,
    alerts     INTEGER NOT NULL,
    score      REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL,
    rule_code  TEXT    NOT NULL,
    severity   TEXT    NOT NULL,
    scope      TEXT    NOT NULL,
    offer_id   INTEGER,
    brand      TEXT    NOT NULL DEFAULT '',
    model      TEXT    NOT NULL DEFAULT '',
    message    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_alerts (
    alert_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    INTEGER NOT NULL,
    level     TEXT    NOT NULL,
    code      TEXT    NOT NULL,
    title     TEXT    NOT NULL,
    detail    TEXT    NOT NULL,
    metric    REAL    NOT NULL,
    threshold REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_findings_run ON qa_findings (run_id);
CREATE INDEX IF NOT EXISTS ix_alerts_run ON qa_alerts (run_id);
