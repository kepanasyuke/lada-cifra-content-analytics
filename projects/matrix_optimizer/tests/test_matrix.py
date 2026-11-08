"""Тесты аналитики товарной матрицы."""

from __future__ import annotations

from projects.matrix_optimizer import matrix


def test_abc_boundaries():
    assert matrix.abc_class(0.10) == "A"
    assert matrix.abc_class(0.80) == "A"
    assert matrix.abc_class(0.81) == "B"
    assert matrix.abc_class(0.96) == "C"


def test_xyz_boundaries():
    assert matrix.xyz_class(0.10) == "X"
    assert matrix.xyz_class(0.51) == "Y"
    assert matrix.xyz_class(1.01) == "Z"


def test_variation_of_flat_series_is_zero():
    assert matrix.coefficient_of_variation([5.0, 5.0, 5.0]) == 0.0
    assert matrix.coefficient_of_variation([]) == 0.0


def test_variation_grows_with_spread():
    stable = matrix.coefficient_of_variation([10.0, 11.0, 10.0])
    volatile = matrix.coefficient_of_variation([1.0, 30.0, 2.0])
    assert volatile > stable


def test_model_frame_sorted_by_value(conn):
    frame = matrix.model_frame(conn)
    values = [row["value"] for row in frame]
    assert values == sorted(values, reverse=True)


def test_model_frame_has_classes_and_full_cumulative(conn):
    frame = matrix.model_frame(conn)
    assert all(row["code"] == row["abc"] + row["xyz"] for row in frame)
    assert frame[-1]["cumulative"] == 100.0


def test_cells_cover_every_model(conn):
    frame = matrix.model_frame(conn)
    total = sum(item["models"] for item in matrix.cells(frame))
    assert total == len(frame)
    assert len(matrix.cells(frame)) == 9


def test_each_cell_has_recommendation(conn):
    assert all(item["recommendation"] for item in matrix.cells(matrix.model_frame(conn)))


def test_distribution_counts_classes(conn):
    frame = matrix.model_frame(conn)
    assert sum(item["value"] for item in matrix.distribution(frame, "abc")) == len(frame)


def test_gaps_and_orphans_with_empty_catalog(conn):
    assert matrix.gaps(conn) == []
    assert len(matrix.orphans(conn)) == 4


def test_summary_exposes_portfolio(conn):
    data = matrix.summary(conn)
    assert data["models"] >= 1
    assert data["value_mln"] > 0
    assert data["orphans"] == 4


def test_focus_list_returns_models_of_cell(conn):
    items = matrix.focus_list(conn, "AX", 5)
    assert all(item["code"] == "AX" for item in items)
