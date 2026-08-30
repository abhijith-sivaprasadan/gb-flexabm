import json
from datetime import date, timedelta

import pytest

from gb_flexabm import data


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
    raw = b"SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND\n2024-01-01,1,100\n2024-01-01,2,200\n"
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
    assert frame.national_demand_mw.tolist() == [100, 200]
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
