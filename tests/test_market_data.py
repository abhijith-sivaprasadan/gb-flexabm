import json

import pandas as pd
import pytest

from gb_flexabm.market_data import (
    PROVIDER,
    audit_market,
    audit_summary,
    fetch_chunk,
    hourly_market,
    normalize,
    read_market_audit,
    training_requests,
    verify_chunk,
)
from gb_flexabm.study import Protocol


@pytest.fixture
def protocol():
    return Protocol.from_dict(
        {
            "schema_version": 1,
            "status": "draft",
            "mode": "explanatory_backcast",
            "money_base_year": 2025,
            "splits": {"train": [2016], "validation": [2017], "holdout": [2018]},
            "prior_exposure": ["Authored fixtures"],
            "metrics": {"example": 1},
            "baselines": ["persistence"],
        }
    )


def rows(request, dataset="mid"):
    result = []
    for stamp in pd.date_range(
        request["start_utc"], request["end_utc"], freq="30min", inclusive="left"
    ):
        local = stamp.tz_convert("Europe/London")
        midnight = local.normalize().tz_convert("UTC")
        item = {
            "startTime": stamp.isoformat(),
            "settlementDate": str(local.date()),
            "settlementPeriod": int((stamp - midnight).total_seconds() / 1800) + 1,
        }
        if dataset == "mid":
            item.update(dataProvider=PROVIDER, price=-5.0, volume=12.0)
        else:
            item.update(
                dataset="FUELHH",
                fuelType="CCGT",
                generation=1500.0,
                publishTime=(stamp + pd.Timedelta(minutes=30)).isoformat(),
            )
        result.append(item)
    return result


def encoded(items):
    return json.dumps(items).encode()


def test_requests_are_training_only_and_below_seven_day_limit(protocol):
    plan = training_requests(protocol, "mid")
    times = []
    for entry in plan:
        start, end = pd.Timestamp(entry["start_utc"]), pd.Timestamp(entry["end_utc"])
        assert end - start <= pd.Timedelta(days=6)
        times.extend(pd.date_range(start, end, freq="30min", inclusive="left"))
    assert pd.DatetimeIndex(times).equals(
        pd.date_range("2016-01-01", "2017-01-01", freq="30min", inclusive="left", tz="UTC")
    )
    with pytest.raises(ValueError, match="not authorised"):
        training_requests(protocol, "mid", [2017])


def test_negative_prices_and_volume_are_not_provider_averaged(protocol):
    entry = training_requests(protocol, "mid")[0]
    items = rows(entry)
    items += [{**items[0], "dataProvider": "N2EXMIDP", "price": 0, "volume": 0}]
    frame, audit = normalize(encoded({"data": items}), entry)
    assert frame.price.eq(-5).all() and audit["target_usable"]
    assert audit["zero_volume_index_intervals"] == 0


def test_zero_volume_is_preserved_but_blocks_price_target(protocol):
    entry = training_requests(protocol, "mid")[0]
    items = rows(entry)
    items[0]["price"], items[0]["volume"] = 0, 0
    frame, audit = normalize(encoded(items), entry)
    assert frame.price.iloc[0] == 0
    assert audit["complete_for_observed_categories"]
    assert not audit["target_usable"] and audit["zero_volume_index_intervals"] == 1


@pytest.mark.parametrize("dataset", ["mid", "fuelhh"])
def test_empty_response_is_a_gap_not_zero_observations(protocol, dataset):
    entry = training_requests(protocol, dataset)[0]
    frame, audit = normalize(b"[]", entry)
    assert frame.empty and audit["empty_response"]
    assert not audit["complete_for_observed_categories"] and not audit["target_usable"]


def test_missing_middle_interval_is_not_imputed(protocol):
    entry = training_requests(protocol, "mid")[0]
    items = rows(entry)
    del items[17]
    frame, audit = normalize(encoded(items), entry)
    assert len(frame) == 287 and audit["coverage"][0]["missing_intervals"] == 1
    assert not audit["target_usable"]


def test_inclusive_api_endpoint_is_trimmed_without_month_overlap(protocol):
    entry = training_requests(protocol, "mid")[0]
    next_entry = training_requests(protocol, "mid")[1]
    _, audit = normalize(encoded(rows(entry) + [rows(next_entry)[0]]), entry)
    assert audit["trimmed_boundary_rows"] == 1 and audit["target_usable"]


@pytest.mark.parametrize("month", [3, 10])
def test_dst_observations_match_settlement_periods(protocol, month):
    entry = [
        e for e in training_requests(protocol, "mid") if pd.Timestamp(e["start_utc"]).month == month
    ][-2]
    _, audit = normalize(encoded(rows(entry)), entry)
    assert audit["target_usable"]


def test_wrong_settlement_mapping_and_naive_timestamp_fail(protocol):
    entry = training_requests(protocol, "mid")[0]
    items = rows(entry)
    items[0]["settlementPeriod"] = 2
    with pytest.raises(ValueError, match="disagree"):
        normalize(encoded(items), entry)
    items = rows(entry)
    items[0]["startTime"] = "2016-01-01T00:00:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize(encoded(items), entry)


def test_conflicting_prices_rejected_identical_duplicates_deduplicated(protocol):
    entry = training_requests(protocol, "mid")[0]
    items = rows(entry)
    assert normalize(encoded(items + [items[0]]), entry)[1]["target_usable"]
    with pytest.raises(ValueError, match="Conflicting"):
        normalize(encoded(items + [{**items[0], "price": 99}]), entry)


def test_latest_generation_revision_and_signed_flows(protocol):
    entry = training_requests(protocol, "fuelhh")[0]
    items = rows(entry, "fuelhh")
    items += [{**items[0], "generation": 1200, "publishTime": "2016-01-01T01:00:00Z"}]
    items += [{**items[0], "fuelType": "INTFR", "generation": -200}]
    frame, audit = normalize(encoded(items), entry)
    assert frame.loc[frame.fuelType == "CCGT", "generation"].iloc[0] == 1200
    assert frame.loc[frame.fuelType == "INTFR", "generation"].iloc[0] == -200
    assert not audit["complete_for_observed_categories"]
    with pytest.raises(ValueError, match="Conflicting"):
        normalize(encoded(items + [{**items[-2], "generation": 1100}]), entry)


def test_generation_auxiliary_midnight_date_error_is_disclosed_not_shifted(protocol):
    entry = training_requests(protocol, "fuelhh")[0]
    items = rows(entry, "fuelhh")
    items[47]["settlementDate"] = "2016-01-02"
    frame, audit = normalize(encoded(items), entry)
    assert frame.timestamp_utc.iloc[47] == pd.Timestamp("2016-01-01T23:30Z")
    assert audit["settlement_mismatch_rows"] == 1
    assert audit["complete_for_observed_categories"] and not audit["boundary_reconciled"]


def test_invalid_auxiliary_spring_period_is_flagged_with_primary_time_intact(protocol):
    entry = next(e for e in training_requests(protocol, "fuelhh") if e["id"] == "2016-03-25")
    items = rows(entry, "fuelhh")
    items[0].update(settlementDate="2016-03-27", settlementPeriod=48)
    frame, audit = normalize(encoded(items), entry)
    assert frame.timestamp_utc.iloc[0] == pd.Timestamp(entry["start_utc"])
    assert audit["settlement_mismatch_rows"] == 1


def test_generation_off_grid_primary_time_is_rejected(protocol):
    entry = training_requests(protocol, "fuelhh")[0]
    items = rows(entry, "fuelhh")
    items[0]["startTime"] = "2016-01-01T00:15:00Z"
    with pytest.raises(ValueError, match="half-hour grid"):
        normalize(encoded(items), entry)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_hourly_prices_require_finite_positive_volume(protocol, invalid):
    entry = training_requests(protocol, "mid")[0]
    frame, _ = normalize(encoded(rows(entry)), entry)
    frame.loc[0, "volume"] = invalid
    with pytest.raises(ValueError, match="positive volume"):
        hourly_market(frame, "mid")


@pytest.mark.parametrize("dataset", ["mid", "fuelhh"])
def test_hourly_aggregation_preserves_mean_and_generation_energy(protocol, dataset):
    entry = training_requests(protocol, dataset)[0]
    frame, _ = normalize(encoded(rows(entry, dataset)), entry)
    field = "price" if dataset == "mid" else "generation"
    frame.loc[0, field] = 20
    hourly = hourly_market(frame, dataset)
    assert len(hourly) == len(frame) / 2
    assert hourly[field].sum() == pytest.approx(frame[field].sum() / 2)
    with pytest.raises(ValueError, match="Both half-hours"):
        hourly_market(frame.iloc[1:], dataset)


def test_rejected_raw_response_is_retained_and_not_implicitly_retried(
    protocol, tmp_path, monkeypatch
):
    import gb_flexabm.market_data as module

    entry = training_requests(protocol, "mid")[0]
    monkeypatch.setattr(module, "_download", lambda url: b'{"unexpected": true}')
    with pytest.raises(ValueError, match="observation list"):
        fetch_chunk(tmp_path, entry)
    assert next(tmp_path.glob("elexon-mid/*/*/source.json")).read_bytes() == b'{"unexpected": true}'
    assert len(list(tmp_path.glob("elexon-mid/*/*/rejected.json"))) == 1
    with pytest.raises(ValueError, match="incomplete/rejected"):
        fetch_chunk(tmp_path, entry)


def test_download_cache_and_tamper_rejection(protocol, tmp_path, monkeypatch):
    import gb_flexabm.market_data as module

    entry = training_requests(protocol, "mid")[0]
    monkeypatch.setattr(module, "_download", lambda url: encoded(rows(entry)))
    record = fetch_chunk(tmp_path, entry)
    monkeypatch.setattr(module, "_download", lambda url: pytest.fail("Cache must not refetch"))
    assert fetch_chunk(tmp_path, entry) == record
    _, checked = verify_chunk(tmp_path, entry)
    assert checked["coverage"]["target_usable"]
    report = audit_market(protocol, tmp_path, "mid", tmp_path / "audit.json")
    assert read_market_audit(tmp_path / "audit.json") == report
    assert audit_summary(report).iloc[0]["verified response chunks"] == 1
    assert not report["years"][0]["complete"] and not report["S2_complete"]
    source = next(tmp_path.glob("elexon-mid/*/*/source.json"))
    source.write_bytes(b"[]")
    with pytest.raises(ValueError, match="checksum"):
        fetch_chunk(tmp_path, entry)


def test_public_audit_rejects_modified_success_claim(protocol, tmp_path):
    path = tmp_path / "audit.json"
    report = audit_market(protocol, tmp_path, "mid", path)
    report["years"][0]["complete"] = True
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="checksum"):
        read_market_audit(path)
