-- РђРЅР°Р»РёС‚РёС‡РµСЃРєРёРµ РІСЊСЋС…Рё. Р“РѕС‚РѕРІС‹ Рє РїРѕРґРєР»СЋС‡РµРЅРёСЋ РІ Apache Superset / Power BI РєР°Рє РёСЃС‚РѕС‡РЅРёРєРё.
DROP VIEW IF EXISTS v_offers;
CREATE VIEW v_offers AS
SELECT
    o.offer_id,
    o.brand,
    o.model,
    o.name,
    o.year,
    o.price,
    o.currency,
    o.km_driven,
    o.fuel,
    o.transmission,
    o.seller,
    o.owner,
    o.engine_cc,
    o.power_bhp,
    o.seats,
    o.listed_at,
    substr(o.listed_at, 1, 7) AS period,
    o.listed_at_source,
    CASE WHEN o.km_driven > 0 THEN ROUND(1.0 * o.price / o.km_driven, 2) END AS price_per_km,
    ((o.mileage_kmpl IS NOT NULL) + (o.engine_cc IS NOT NULL) + (o.power_bhp IS NOT NULL)
     + (o.torque IS NOT NULL) + (o.seats IS NOT NULL)) AS filled_fields,
    ROUND(100.0 * ((o.mileage_kmpl IS NOT NULL) + (o.engine_cc IS NOT NULL) + (o.power_bhp IS NOT NULL)
     + (o.torque IS NOT NULL) + (o.seats IS NOT NULL)) / 5.0, 1) AS completeness_pct
FROM offers o;

DROP VIEW IF EXISTS v_monthly_demand;
CREATE VIEW v_monthly_demand AS
SELECT
    period,
    COUNT(*)                        AS offers,
    ROUND(AVG(price), 0)            AS avg_price,
    ROUND(SUM(price) / 1000000.0, 2) AS value_mln,
    ROUND(AVG(km_driven), 0)        AS avg_km
FROM v_offers
GROUP BY period
ORDER BY period;

DROP VIEW IF EXISTS v_brand_month;
CREATE VIEW v_brand_month AS
SELECT
    v.period,
    v.brand,
    COUNT(*)             AS offers,
    ROUND(AVG(v.price), 0) AS avg_price
FROM v_offers v
GROUP BY v.period, v.brand;

DROP VIEW IF EXISTS v_fuel_mix;
CREATE VIEW v_fuel_mix AS
SELECT
    period,
    fuel,
    COUNT(*) AS offers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY period), 1) AS share_pct
FROM v_offers
GROUP BY period, fuel;

DROP VIEW IF EXISTS v_model_economics;
CREATE VIEW v_model_economics AS
SELECT
    brand,
    model,
    COUNT(*)               AS offers,
    ROUND(AVG(price), 0)   AS avg_price,
    MIN(price)             AS min_price,
    MAX(price)             AS max_price,
    ROUND(SUM(price) / 1000000.0, 2) AS value_mln,
    ROUND(AVG(completeness_pct), 1)  AS completeness_pct,
    ROUND(AVG(km_driven), 0)         AS avg_km,
    ROUND(AVG(year), 1)              AS avg_year
FROM v_offers
GROUP BY brand, model;

DROP VIEW IF EXISTS v_content_gaps;
CREATE VIEW v_content_gaps AS
SELECT
    brand,
    COUNT(*)                                                  AS offers,
    ROUND(100.0 * SUM(mileage_kmpl IS NULL) / COUNT(*), 1)    AS gap_mileage_pct,
    ROUND(100.0 * SUM(engine_cc IS NULL) / COUNT(*), 1)       AS gap_engine_pct,
    ROUND(100.0 * SUM(power_bhp IS NULL) / COUNT(*), 1)       AS gap_power_pct,
    ROUND(100.0 * SUM(seats IS NULL) / COUNT(*), 1)           AS gap_seats_pct,
    ROUND(AVG(completeness_pct), 1)                           AS completeness_pct
FROM v_offers
GROUP BY brand;

DROP VIEW IF EXISTS v_catalog_gap;
CREATE VIEW v_catalog_gap AS
SELECT
    c.brand,
    c.model,
    COUNT(c.catalog_id)  AS catalog_trims,
    COALESCE(o.offers, 0) AS offers,
    ROUND(COALESCE(o.offers, 0) * 1.0 / COUNT(c.catalog_id), 2) AS offers_per_trim
FROM catalog_models c
LEFT JOIN (
    SELECT brand, model, COUNT(*) AS offers FROM offers GROUP BY brand, model
) o ON o.brand = c.brand AND o.model = c.model
GROUP BY c.brand, c.model;

