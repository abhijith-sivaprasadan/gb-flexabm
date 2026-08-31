import json
from datetime import date, timedelta

import pandas as pd
import pytest

from gb_flexabm import data


def calendar_frame(year):
    stamps = pd.date_range(
        f"{year}-01-01", f"{year + 1}-01-01", freq="30min", inclusive="left", tz="UTC"
    )
    return pd.DataFrame(
        {"timestamp_utc": stamps, "duration_hours": 0.5, "national_demand_mw": 100.0}
    )


def source_bytes(year):
    frame = calendar_frame(year)
    days = frame.timestamp_utc.dt.tz_convert("Europe/London").dt.strftime("%Y-%m-%d")
    raw = pd.DataFrame({"SETTLEMENT_DATE": days, "ND": frame.national_demand_mw})
    raw["SETTLEMENT_PERIOD"] = raw.groupby("SETTLEMENT_DATE").cumcount() + 1
    return raw.to_csv(index=False).encode()


@pytest.mark.parametrize(
    "day,count", [(date(2024, 3, 31), 46), (date(2024, 10, 27), 50), (date(2024, 1, 1), 48)]
)
def test_settlement_day_dst_and_unique_utc(day, count):
    stamps = [data.settlement_start_utc(day, n) for n in range(1, count + 1)]
    assert len(set(stamps)) == count
    assert all(b - a == timedelta(minutes=30) for a, b in zip(stamps, stamps[1:]))
    with pytest.raises(ValueError):
        data.settlement_start_utc(day, count + 1)


def test_units_and_explicit_inflation_indices():
    assert data.energy_to_power_mw(10, 0.5) == 20
    assert data.constant_money(100, 80, 100) == 125
    with pytest.raises(ValueError):
        data.energy_to_power_mw(10, 0)


def test_neso_contract_rejects_gaps_and_duplicates(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND\n2024-01-01,1,100\n2024-01-01,3,200\n")
    with pytest.raises(ValueError, match="contiguous"):
        data.parse_neso_demand(source)
    source.write_text("SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND\n2024-01-01,1,100\n2024-01-01,1,200\n")
    with pytest.raises(ValueError, match="Duplicate"):
        data.parse_neso_demand(source)


def test_offline_fetch_provenance_and_tamper_detection(tmp_path, monkeypatch):
    raw = source_bytes(2024)
    meta = {
        "result": {
            "licenses": [{"name": "synthetic-test-fixture"}],
            "resources": [
                {
                    "name": "historic_demand_data_2024",
                    "path": "https://api.neso.energy/test.csv",
                    "id": "fixture",
                    "last_modified": "2024-01-02",
                }
            ],
        }
    }
    monkeypatch.setattr(
        data,
        "_download",
        lambda url: json.dumps(meta).encode() if url == data.NESO_METADATA else raw,
    )
    manifest = data.fetch_neso(2024, tmp_path)
    assert data.fetch_neso(2024, tmp_path) == manifest
    frame = data.validate_data_manifest(manifest)
    assert len(frame) == 17568
    assert (frame.national_demand_mw == 100).all()
    assert data.calendar_coverage(frame, 2024)["complete"]
    with pytest.raises(ValueError, match="differs"):
        data.validate_data_manifest(manifest, expected_year=2023)
    (manifest.parent / "source.csv").write_bytes(raw + b"altered")
    with pytest.raises(ValueError, match="checksum"):
        data.validate_data_manifest(manifest)


def test_non_official_source_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        data._download("https://example.com/file.csv")


@pytest.mark.parametrize("stamp", ["2024-02-01", "01/02/2024", "01-Feb-2024"])
def test_date_format_does_not_reverse_month_and_day(tmp_path, stamp):
    source = tmp_path / "source.csv"
    source.write_text(f"SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND\n{stamp},1,100\n")
    result = data.parse_neso_demand(source)
    assert result.timestamp_utc.iloc[0].date() == date(2024, 2, 1)


def test_redirect_is_rejected_before_following_untrusted_host():
    from urllib.request import Request

    with pytest.raises(ValueError, match="redirect"):
        data._NesoRedirect().redirect_request(
            Request(data.NESO_METADATA), None, 302, "Found", {}, "https://example.com/private"
        )
    assert data._allowed_download(
        f"https://{data.NESO_OBJECT_HOST}/dx-national-grid/national-grid/resources/example.csv",
        redirect=True,
    )
    assert not data._allowed_download(
        f"https://{data.NESO_OBJECT_HOST}/other-bucket/file.csv", redirect=True
    )


@pytest.mark.parametrize("year,rows", [(2023, 17520), (2024, 17568)])
def test_full_calendar_gate_and_dst_roundtrip(tmp_path, year, rows):
    source = tmp_path / "source.csv"
    source.write_bytes(source_bytes(year))
    frame = data.parse_neso_demand(source)
    report = data.require_complete_year(frame, year)
    assert report["complete"] and report["expected_rows"] == rows
    assert report["missing_intervals"] == report["unexpected_intervals"] == 0


@pytest.mark.parametrize("defect", ["head", "tail", "gap", "duplicate", "outside", "order"])
def test_calendar_gate_rejects_partial_and_wrong_year_data(defect):
    frame = calendar_frame(2024)
    if defect == "head":
        frame = frame.iloc[48:]
    elif defect == "tail":
        frame = frame.iloc[:-48]
    elif defect == "gap":
        frame = frame.drop(index=200)
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    elif defect == "outside":
        frame = calendar_frame(2023)
    else:
        frame = frame.iloc[::-1]
    with pytest.raises(ValueError, match="calendar coverage"):
        data.require_complete_year(frame, 2024)


@pytest.mark.parametrize("year", [True, 2024.0, 1800, 2200])
def test_calendar_year_is_explicit_and_validated(year):
    with pytest.raises(ValueError, match="Calendar year"):
        data.calendar_coverage(calendar_frame(2024), year)


def test_partial_acquisition_preserved_but_rejected(tmp_path, monkeypatch):
    raw = b"SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND\n2024-01-01,1,100\n"
    meta = {
        "result": {
            "resources": [
                {
                    "name": "historic_demand_data_2024",
                    "id": "fixture",
                    "path": "https://api.neso.energy/test.csv",
                }
            ]
        }
    }
    monkeypatch.setattr(
        data,
        "_download",
        lambda url: json.dumps(meta).encode() if url == data.NESO_METADATA else raw,
    )
    with pytest.raises(ValueError, match="calendar coverage"):
        data.fetch_neso(2024, tmp_path)
    manifest = next(tmp_path.glob("neso-demand/2024/*/manifest.json"))
    assert (manifest.parent / "source.csv").read_bytes() == raw
    assert not json.loads(manifest.read_text())["calendar_coverage"]["complete"]
    with pytest.raises(ValueError, match="calendar coverage"):
        data.validate_data_manifest(manifest)
    with pytest.raises(ValueError, match="calendar coverage"):
        data.fetch_neso(2024, tmp_path)
