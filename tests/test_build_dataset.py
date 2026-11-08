"""Тесты сборки витрины: разбор CSV, нормализация, загрузка в SQLite."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from scripts import build_dataset

RAW_HEADER = [
    "name",
    "year",
    "selling_price",
    "km_driven",
    "fuel",
    "seller_type",
    "transmission",
    "owner",
    "mileage",
    "engine",
    "max_power",
    "torque",
    "seats",
]

ROW = {
    "name": "LADA Vesta Comfort",
    "year": "2018",
    "selling_price": "620000",
    "km_driven": "45000",
    "fuel": "бензин",
    "seller_type": "Dealer",
    "transmission": "механика",
    "owner": "First Owner",
    "mileage": "17.5 kmpl",
    "engine": "1598 CC",
    "max_power": "106 bhp",
    "torque": "148Nm",
    "seats": "5",
}


def test_to_number_parses_integer_with_unit():
    assert build_dataset.to_number("1248 CC") == 1248.0


def test_to_number_parses_decimal_with_unit():
    assert build_dataset.to_number("74.5 bhp") == 74.5


def test_to_number_returns_none_for_empty_string():
    assert build_dataset.to_number("") is None


def test_to_number_returns_none_without_digits():
    assert build_dataset.to_number("—") is None


def test_to_int_rounds_value():
    assert build_dataset.to_int("106.4 bhp") == 106


def test_to_int_returns_none_for_empty():
    assert build_dataset.to_int("") is None


def test_normalize_text_collapses_spaces():
    assert build_dataset.normalize_text("  LADA   Vesta  ") == "LADA Vesta"


def test_normalize_text_handles_none():
    assert build_dataset.normalize_text(None) == ""


def test_parse_brand_model_simple_name():
    assert build_dataset.parse_brand_model("LADA Vesta Comfort") == ("LADA", "Vesta", "Comfort")


def test_parse_multiword_brand():
    brand, model, _ = build_dataset.parse_brand_model("Mercedes-Benz E-Class 220 d")
    assert brand == "Mercedes-Benz"
    assert model == "E-Class"


def test_parse_land_rover_name():
    brand, model, trim = build_dataset.parse_brand_model("Land Rover Freelander 2")
    assert (brand, model, trim) == ("Land Rover", "Freelander", "2")


def test_parse_alias_wagon_r():
    brand, model, _ = build_dataset.parse_brand_model("Maruti Wagon R LXI")
    assert brand == "Maruti"
    assert model == "Wagon R"


def test_parse_alias_grand_i10():
    _, model, _ = build_dataset.parse_brand_model("Hyundai Grand i10 Magna")
    assert model == "Grand i10"


def test_parse_single_token_name():
    assert build_dataset.parse_brand_model("LADA") == ("LADA", "", "")


def test_is_prefix_matches_compound_brand():
    tokens = ["Land", "Rover", "Freelander"]
    assert build_dataset.is_prefix(tokens, "Land Rover") is True
    assert build_dataset.is_prefix(tokens, "Land Cruiser") is False


def test_match_multiword_finds_brand():
    assert build_dataset.match_multiword(["Ashok", "Leyland", "Stile"]) == "Ashok Leyland"


def test_match_multiword_returns_empty_for_plain_name():
    assert build_dataset.match_multiword(["LADA", "Vesta"]) == ""


def test_multiword_part_keeps_rest_as_trim():
    assert build_dataset.multiword_part(["Ashok", "Leyland", "Stile", "LE"], "Ashok Leyland") == (
        "Ashok Leyland",
        "Stile",
        "LE",
    )


def test_multiword_part_without_model_token():
    assert build_dataset.multiword_part(["Land", "Rover"], "Land Rover") == ("Land Rover", "", "")


def test_plain_part_splits_name():
    assert build_dataset.plain_part(["LADA", "Niva", "Legend"]) == ("LADA", "Niva", "Legend")


def test_brand_and_rest_prefers_compound_brand():
    brand, model, _ = build_dataset.brand_and_rest(["Land", "Rover", "Defender"])
    assert (brand, model) == ("Land Rover", "Defender")


def test_resolve_model_keeps_unknown_head():
    assert build_dataset.resolve_model("LADA", "Vesta", "SW") == ("Vesta", "SW")


def test_hash_share_is_stable_and_bounded():
    first = build_dataset.hash_share("LADA Vesta")
    assert first == build_dataset.hash_share("LADA Vesta")
    assert 0.0 <= first < 1.0


def test_month_weight_is_positive_and_grows():
    assert build_dataset.month_weight(0) > 0
    assert build_dataset.month_weight(12) > build_dataset.month_weight(0)


def test_listing_weights_cover_timeline():
    weights = build_dataset.listing_weights()
    assert len(weights) == build_dataset.TIMELINE_MONTHS
    assert all(weight > 0 for weight in weights)


def test_cumulative_index_finds_first_crossing():
    assert build_dataset.cumulative_index([1.0, 2.0, 3.0], 2.5) == 1


def test_cumulative_index_falls_back_to_last_month():
    assert build_dataset.cumulative_index([1.0, 1.0], 99.0) == 1


def test_pick_month_stays_inside_timeline():
    month = build_dataset.pick_month("LADA Vesta|2018|620000")
    assert 0 <= month < build_dataset.TIMELINE_MONTHS
    assert month == build_dataset.pick_month("LADA Vesta|2018|620000")


def test_month_start_rolls_over_years():
    assert build_dataset.month_start(0) == date(2023, 1, 1)
    assert build_dataset.month_start(13) == date(2024, 2, 1)


def test_day_offset_is_within_month():
    offset = build_dataset.day_offset("LADA Vesta")
    assert 1 <= offset <= 27
    assert offset == build_dataset.day_offset("LADA Vesta")


def test_simulated_listing_date_has_iso_format():
    value = build_dataset.simulated_listing_date("LADA Vesta", "2018", "620000")
    assert len(value) == 10
    assert date.fromisoformat(value) >= build_dataset.TIMELINE_START


def test_identity_fields_describe_brand_and_source():
    fields = build_dataset.identity_fields(ROW, 7)
    assert fields["offer_id"] == 7
    assert fields["brand"] == "LADA"
    assert fields["model"] == "Vesta"
    assert fields["source"] == build_dataset.SOURCE_NAME


def test_market_fields_use_inr_currency():
    fields = build_dataset.market_fields(ROW)
    assert fields["currency"] == "INR"
    assert fields["price"] == 620000
    assert fields["year"] == 2018


def test_market_fields_replace_missing_numbers_with_zero():
    fields = build_dataset.market_fields({**ROW, "selling_price": "", "km_driven": ""})
    assert fields["price"] == 0
    assert fields["km_driven"] == 0


def test_spec_fields_keep_none_for_empty_values():
    fields = build_dataset.spec_fields({**ROW, "engine": "", "seats": "", "torque": ""})
    assert fields["engine_cc"] is None
    assert fields["seats"] is None
    assert fields["torque"] is None


def test_spec_fields_parse_numbers():
    fields = build_dataset.spec_fields(ROW)
    assert fields["engine_cc"] == 1598
    assert fields["power_bhp"] == 106
    assert fields["mileage_kmpl"] == 17.5


def test_listing_fields_mark_source_as_simulated():
    fields = build_dataset.listing_fields(ROW)
    assert fields["listed_at_source"] == "simulated"
    assert fields["listed_at"]


def test_normalize_covers_every_column():
    assert set(build_dataset.normalize(ROW, 1)) == set(build_dataset.COLUMNS)


def test_offer_tuple_follows_column_order():
    offer = build_dataset.normalize(ROW, 1)
    assert build_dataset.offer_tuple(offer) == tuple(
        offer[column] for column in build_dataset.COLUMNS
    )


def test_insert_sql_matches_column_count():
    assert build_dataset.INSERT_SQL.count("?") == len(build_dataset.COLUMNS)


@pytest.mark.parametrize(
    "table",
    ["offers", "catalog_models", "ingest_runs", "qa_runs", "qa_findings", "qa_alerts"],
)
def test_init_db_creates_table(empty_conn, table):
    row = empty_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    assert row is not None


@pytest.mark.parametrize(
    "view",
    [
        "v_offers",
        "v_monthly_demand",
        "v_brand_month",
        "v_fuel_mix",
        "v_model_economics",
        "v_content_gaps",
        "v_catalog_gap",
    ],
)
def test_init_db_creates_view(empty_conn, view):
    row = empty_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name=?", (view,)
    ).fetchone()
    assert row is not None


def test_apply_schema_is_repeatable(empty_conn):
    assert build_dataset.apply_schema(empty_conn) is empty_conn


def test_apply_views_is_repeatable(empty_conn):
    assert build_dataset.apply_views(empty_conn) is empty_conn


def test_fresh_db_overwrites_existing_file(tmp_path):
    path = tmp_path / "warehouse.sqlite"
    first = build_dataset.init_db(path)
    first.close()
    second = build_dataset.fresh_db(path)
    assert second.execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 0
    second.close()


def test_load_offers_inserts_rows(empty_conn):
    assert build_dataset.load_offers(empty_conn, [ROW, ROW]) == 2
    assert empty_conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 2


def test_load_views_keeps_data(empty_conn):
    build_dataset.load_offers(empty_conn, [ROW])
    build_dataset.load_views(empty_conn)
    assert empty_conn.execute("SELECT COUNT(*) FROM v_offers").fetchone()[0] == 1


def test_read_rows_parses_csv(tmp_path):
    path = tmp_path / "raw.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_HEADER)
        writer.writeheader()
        writer.writerow(ROW)
    rows = build_dataset.read_rows(path)
    assert len(rows) == 1
    assert rows[0]["name"] == "LADA Vesta Comfort"


def test_rebuild_loads_csv_into_new_database(tmp_path):
    raw = tmp_path / "raw.csv"
    with raw.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_HEADER)
        writer.writeheader()
        writer.writerow(ROW)
        writer.writerow(ROW)
    path = tmp_path / "warehouse.sqlite"
    assert build_dataset.rebuild(path, raw) == 2


def test_stats_reports_loaded_offers(empty_conn, tmp_path):
    build_dataset.load_offers(empty_conn, [ROW])
    path = empty_conn.execute("PRAGMA database_list").fetchone()[2]
    assert build_dataset.stats(path)["offers"] == 1
