"""Tests for raw-measurement CSV upload, subgroup summaries and Pp/Ppk."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import spc_utils as su  # noqa: E402

needs_uploader = pytest.mark.skipif(not hasattr(AppTest, "file_uploader"), reason="Streamlit AppTest without file_uploader support")


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


# ---------------- reading ----------------
def test_empty_file_is_rejected():
    with pytest.raises(su.UploadError, match="empty"):
        su.read_csv_bytes(b"   \n")


def test_semicolon_delimited_file_is_read():
    df = su.read_csv_bytes(b"Subgroup;X1;X2\n1;10.1;10.2\n2;10.0;10.3\n")
    assert list(df.columns) == ["Subgroup", "X1", "X2"] and len(df) == 2


def test_blank_rows_and_columns_are_dropped():
    df = su.read_csv_bytes(b"A,B,C\n1,2,\n,,\n3,4,\n")
    assert df.shape == (2, 2)


# ---------------- wide layout ----------------
def test_wide_with_id_column_matches_numpy():
    df = pd.DataFrame({"Subgroup": [1, 2, 3], "X1": [10.0, 10.2, 9.9], "X2": [10.1, 10.4, 9.8], "X3": [10.3, 10.0, 10.0]})
    labels, m, notes = su.matrix_from_wide(df, "Subgroup")
    assert labels == [1, 2, 3] and m.shape == (3, 3) and notes == []
    s = su.summarize_matrix(labels, m)
    assert s["Mean"].tolist() == pytest.approx([10.1333333, 10.2, 9.9], abs=1e-6)
    assert s["Range"].tolist() == pytest.approx([0.3, 0.4, 0.2])
    assert s["StdDev"].iloc[0] == pytest.approx(np.std([10.0, 10.1, 10.3], ddof=1))


def test_wide_without_id_numbers_subgroups():
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    labels, m, _ = su.matrix_from_wide(df, None)
    assert labels == [1, 2] and m.shape == (2, 2)


def test_wide_skips_incomplete_rows_and_says_so():
    df = pd.DataFrame({"X1": [1.0, 2.0, np.nan], "X2": [1.5, "oops", 3.0]})
    labels, m, notes = su.matrix_from_wide(df, None)
    assert m.shape == (1, 2) and labels == [1]
    assert "2 row(s)" in notes[0]


def test_wide_text_column_is_a_clear_error():
    df = pd.DataFrame({"Operator": ["A", "B"], "X1": [1.0, 2.0], "X2": [1.0, 2.0]})
    with pytest.raises(su.UploadError, match="Operator"):
        su.matrix_from_wide(df, None)


def test_single_measurement_column_is_rejected_with_advice():
    with pytest.raises(su.UploadError, match="single column"):
        su.matrix_from_wide(pd.DataFrame({"X1": [1.0, 2.0, 3.0]}), None)


def test_more_than_ten_columns_is_rejected():
    df = pd.DataFrame(np.ones((3, 11)), columns=[f"X{i}" for i in range(11)])
    with pytest.raises(su.UploadError, match="2 to 10"):
        su.matrix_from_wide(df, None)


def test_every_row_bad_is_rejected():
    df = pd.DataFrame({"X1": [np.nan, np.nan], "X2": [1.0, 2.0]})
    with pytest.raises(su.UploadError):
        su.matrix_from_wide(df, None)


# ---------------- long layout ----------------
def test_long_layout_preserves_group_order():
    df = pd.DataFrame({"Batch": ["B", "B", "A", "A", "C", "C"], "Value": [1.0, 2.0, 3.0, 5.0, 7.0, 7.5]})
    labels, m, _ = su.matrix_from_long(df, "Batch", "Value")
    assert labels == ["B", "A", "C"]
    assert m.tolist() == [[1.0, 2.0], [3.0, 5.0], [7.0, 7.5]]


def test_long_layout_unequal_sizes_names_the_offenders():
    df = pd.DataFrame({"Subgroup": [1, 1, 1, 2, 2, 2, 3, 3], "Value": np.arange(8.0)})
    with pytest.raises(su.UploadError, match=r"same size.*3 \(2\)"):
        su.matrix_from_long(df, "Subgroup", "Value")


def test_long_layout_skips_missing_values_but_then_checks_sizes():
    df = pd.DataFrame({"g": [1, 1, 2, 2], "v": [1.0, np.nan, 2.0, 3.0]})
    with pytest.raises(su.UploadError):
        su.matrix_from_long(df, "g", "v")


def test_long_layout_same_column_twice_is_an_error():
    with pytest.raises(su.UploadError):
        su.matrix_from_long(pd.DataFrame({"g": [1, 1], "v": [1.0, 2.0]}), "g", "g")


# ---------------- single-column layout ----------------
def test_sequence_groups_consecutive_readings():
    df = pd.DataFrame({"x": np.arange(1.0, 11.0)})
    labels, m, notes = su.matrix_from_sequence(df, "x", 5)
    assert labels == [1, 2] and m.tolist() == [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]] and notes == []


def test_sequence_leftover_readings_are_reported():
    labels, m, notes = su.matrix_from_sequence(pd.DataFrame({"x": np.arange(12.0)}), "x", 5)
    assert m.shape == (2, 5) and "last 2" in notes[0]


def test_sequence_too_few_readings():
    with pytest.raises(su.UploadError, match="fewer than one subgroup"):
        su.matrix_from_sequence(pd.DataFrame({"x": [1.0, 2.0, 3.0]}), "x", 5)


@pytest.mark.parametrize("n", [1, 11])
def test_sequence_subgroup_size_limits(n):
    with pytest.raises(su.UploadError):
        su.matrix_from_sequence(pd.DataFrame({"x": np.arange(50.0)}), "x", n)


# ---------------- guessing ----------------
def test_guess_id_column():
    assert su.guess_id_column(pd.DataFrame({"Subgroup": [1, 2], "X1": [1.0, 2.0]})) == "Subgroup"
    assert su.guess_id_column(pd.DataFrame({"Date": ["a", "b"], "X1": [1.0, 2.0]})) == "Date"
    assert su.guess_id_column(pd.DataFrame({"X1": [1.0, 2.0], "X2": [3.0, 4.0]})) is None


def test_guess_long_columns_and_layout():
    long_df = pd.DataFrame({"Subgroup": [1, 1, 2, 2], "Diameter": [1.0, 2.0, 3.0, 4.0]})
    assert su.guess_long_columns(long_df) == ("Subgroup", "Diameter")
    assert su.guess_layout(long_df) == "long"
    assert su.guess_layout(pd.DataFrame({"Subgroup": [1, 2], "X1": [1.0, 2.0], "X2": [1.0, 2.0]})) == "wide"
    assert su.guess_layout(pd.DataFrame({"Reading": np.arange(30.0)})) == "seq"
    wide12 = pd.DataFrame(np.ones((3, 12)), columns=[f"X{i}" for i in range(12)])
    assert su.guess_layout(wide12) == "wide"   # reported as too wide rather than silently reading one column


# ---------------- Pp / Ppk ----------------
def test_pp_ppk_centered():
    r = su.overall_capability([9.9, 10.0, 10.1], usl=10.3, lsl=9.7)   # mean 10, sd 0.1
    assert r["pp"] == pytest.approx(1.0) and r["ppk"] == pytest.approx(1.0) and r["sigma"] == pytest.approx(0.1)


def test_pp_ppk_off_center():
    r = su.overall_capability([9.9, 10.0, 10.1], usl=10.3, lsl=9.8)
    assert r["pp"] == pytest.approx(0.5 / 0.6)
    assert r["ppk"] == pytest.approx(0.2 / 0.3)
    assert r["ppk"] <= r["pp"]


def test_pp_ppk_constant_data_does_not_crash():
    r = su.overall_capability([5.0, 5.0, 5.0], usl=6.0, lsl=4.0)
    assert np.isnan(r["pp"]) and np.isnan(r["ppk"])


def test_overall_sigma_exceeds_within_sigma_when_process_shifts():
    labels, m, _ = su.matrix_from_wide(su.read_csv_bytes(su.example_csv().encode()), "Subgroup")
    s = su.summarize_matrix(labels, m)
    within = su.sigma_within(s["Range"].mean(), m.shape[1])
    overall = su.overall_capability(m.ravel(), 10.05, 9.95)["sigma"]
    assert overall > within  # the example has a shift after subgroup 12


# ---------------- example file ----------------
def test_example_csv_is_deterministic_and_parses():
    assert su.example_csv() == su.example_csv()
    df = su.read_csv_bytes(su.example_csv().encode())
    assert df.shape == (20, 6) and su.guess_layout(df) == "wide"
    labels, m, notes = su.matrix_from_wide(df, su.guess_id_column(df))
    assert m.shape == (20, 5) and notes == [] and labels == list(range(1, 21))
    assert m[12:].mean() - m[:12].mean() == pytest.approx(0.014, abs=0.01)


# ---------------- page behaviour ----------------
def _app() -> AppTest:
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import spc\nspc.render()\n"
    return AppTest.from_string(script, default_timeout=60)


def _upload(at: AppTest, name: str, data: bytes) -> AppTest:
    at.run()
    next(f for f in at.file_uploader if f.label == "CSV file").set_value((name, data, "text/csv"))
    return at.run()


def _n_slider(at):
    return next((s for s in at.slider if s.label == "Subgroup size (n) for chart constants"), None)


def _metric(at, label):
    return next((m for m in at.metric if m.label == label), None)


@needs_uploader
def test_wide_upload_drives_the_whole_page():
    at = _upload(_app(), "run1.csv", su.example_csv().encode())
    assert not at.exception
    assert any("Loaded 20 subgroups of 5 readings (100 measurements)" in s.value for s in at.success)
    assert _metric(at, "Subgroup size (n), from your file").value == "5"
    assert _metric(at, "Pp (overall)") is not None and _metric(at, "Ppk (overall)") is not None
    assert _metric(at, "Cp (potential)") is not None
    assert _n_slider(at) is None  # the n slider is replaced by the n found in the file
    assert len(at.dataframe) >= 1


@needs_uploader
def test_upload_placeholders_and_notice():
    at = _upload(_app(), "run1.csv", su.example_csv().encode())
    target = next(w for w in at.number_input if w.label == "Target mean")
    assert target.value == pytest.approx(10.005, abs=0.002)
    assert any("placeholders" in i.value for i in at.info)


@needs_uploader
def test_example_file_shows_the_shift_in_run_rules_and_ppk_note():
    at = _upload(_app(), "run1.csv", su.example_csv().encode())
    assert any("on one side of the centerline" in w.value and "X-bar chart" in w.value for w in at.warning)


@needs_uploader
def test_long_layout_file_is_detected_and_loaded():
    wide = pd.read_csv(pd.io.common.StringIO(su.example_csv()))
    long = wide.melt(id_vars="Subgroup", value_vars=[c for c in wide.columns if c != "Subgroup"], value_name="Diameter")
    long = long.sort_values("Subgroup", kind="stable")[["Subgroup", "Diameter"]]
    at = _upload(_app(), "long.csv", csv_bytes(long))
    assert not at.exception
    assert any("Loaded 20 subgroups of 5 readings" in s.value for s in at.success)


@needs_uploader
def test_single_column_file_is_grouped_by_subgroup_size():
    vals = pd.DataFrame({"Reading": np.round(np.random.default_rng(1).normal(25.0, 0.05, 103), 3)})
    at = _upload(_app(), "seq.csv", csv_bytes(vals))
    assert not at.exception
    assert any("Loaded 20 subgroups of 5 readings" in s.value for s in at.success)
    assert any("last 3" in c.value for c in at.caption)


@needs_uploader
def test_bad_file_shows_error_and_falls_back_to_sample_data():
    bad = pd.DataFrame(np.ones((6, 12)), columns=[f"X{i}" for i in range(12)])   # 12 measurements per row
    at = _upload(_app(), "bad.csv", csv_bytes(bad))
    assert not at.exception
    assert any("Showing the sample data instead" in e.value for e in at.error)
    assert _n_slider(at) is not None  # sample-data mode again
    assert _metric(at, "Cp (potential)") is not None


@needs_uploader
def test_empty_file_shows_error():
    at = _upload(_app(), "empty.csv", b"\n")
    assert not at.exception
    assert any("empty" in e.value for e in at.error)


@needs_uploader
def test_removing_the_file_returns_to_sample_mode():
    at = _upload(_app(), "run1.csv", su.example_csv().encode())
    next(f for f in at.file_uploader if f.label == "CSV file").set_value(None)
    at.run()
    assert not at.exception
    assert _n_slider(at) is not None and _metric(at, "Pp (overall)") is None


@needs_uploader
def test_too_few_subgroups_gets_the_existing_warning():
    small = pd.DataFrame({"Subgroup": [1, 2, 3], "X1": [1.0, 2.0, 3.0], "X2": [1.1, 2.1, 3.1]})
    at = _upload(_app(), "small.csv", csv_bytes(small))
    assert not at.exception
    assert any("at least 5 subgroups" in w.value for w in at.warning)
