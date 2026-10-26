"""Original MID archive admission checks. All inputs are invented CSV fixtures."""

import json

import pandas as pd
import pytest

from gb_flexabm.legacy_mid_archive import (
    audit_mid_archive,
    verify_mid_audit,
    write_mid_audit,
)

SOURCE = "https://example.org/original-bmrs-mid.csv"
RETRIEVED = "2026-10-26T18:00:00Z"


def csv_rows(year=2016):
    rows = []
    for stamp in pd.date_range(
        f"{year}-01-01", f"{year + 1}-01-01", freq="30min", tz="UTC", inclusive="left"
    ):
        local = stamp.tz_convert("Europe/London")
        midnight_utc = local.normalize().tz_convert("UTC")
        period = int((stamp - midnight_utc).total_seconds() / 1800) + 1
        rows.append(
            f"MID,APXMIDP,{local.strftime('%Y%m%d')},{period},-10.5,50.25"
        )
    return rows


def archive(tmp_path, rows, *, trailer=True):
    path = tmp_path / "source.csv"
    lines = ["HDR,MARKET INDEX DATA", *rows]
    if trailer:
        lines.append(f"FTR,{len(rows)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def inspect(path, year=2016, **kw):
    return audit_mid_archive(
        path,
        year,
        source_url=SOURCE,
        licence="Archive terms pending source-specific review",
        retrieved_at_utc=RETRIEVED,
        **kw,
    )


def test_full_original_year_preserves_dst_and_negative_prices(tmp_path):
    rows = csv_rows()
    report = inspect(archive(tmp_path, rows))
    assert report["unique_apx_rows"] == 17568
    assert report["apx_price_product_complete"]
    assert report["coverage"]["missing_intervals"] == 0
    assert report["S2_complete"] is False
    assert report["historical_bundle_admitted"] is False
    assert report["archive_authenticity_certified"] is False
    assert any(",20160327,46," in row for row in rows)
    assert not any(",20160327,47," in row for row in rows)
    assert any(",20161030,50," in row for row in rows)


def test_missing_settlement_period_fails_closed_without_imputation(tmp_path):
    rows = csv_rows()
    rows.pop(27)
    report = inspect(archive(tmp_path, rows))
    assert report["coverage"]["missing_intervals"] == 1
    assert not report["apx_price_product_complete"]


def test_zero_volume_is_not_mistaken_for_zero_price(tmp_path):
    rows = csv_rows()
    rows[1] = rows[1].replace("-10.5,50.25", "0,0")
    report = inspect(archive(tmp_path, rows))
    assert report["coverage"]["complete"]
    assert report["zero_volume_apx_rows"] == 1
    assert not report["apx_price_product_complete"]


def test_duplicate_active_or_uncontrolled_revision_rejected(tmp_path):
    rows = csv_rows()
    with pytest.raises(ValueError, match="Duplicate active"):
        inspect(archive(tmp_path, [*rows, rows[0]]))
    inactive = rows[0] + ",N"
    with pytest.raises(ValueError, match="Inactive revision"):
        inspect(archive(tmp_path, [inactive, *rows]))
    flagged = [row + ",Y" for row in rows]
    report = inspect(
        archive(tmp_path, [inactive, *flagged]), revision_rule="active_flag"
    )
    assert report["apx_price_product_complete"]
    assert report["inactive_apx_rows_excluded"] == 1
    with pytest.raises(ValueError, match="explicit flag"):
        inspect(archive(tmp_path, rows), revision_rule="active_flag")


def test_invalid_clock_change_period_and_trailer_rejected(tmp_path):
    rows = csv_rows()
    rows[0] = "MID,APXMIDP,20160327,48,20,10"
    with pytest.raises(ValueError, match="settlement periods"):
        inspect(archive(tmp_path, rows))
    path = archive(tmp_path, csv_rows())
    path.write_text(path.read_text().replace("FTR,17568", "FTR,12"))
    with pytest.raises(ValueError, match="trailer count"):
        inspect(path)


def test_other_provider_never_fills_apx_gaps(tmp_path):
    rows = csv_rows()
    missing = rows.pop(0)
    other = missing.replace("APXMIDP", "N2EXMIDP")
    report = inspect(archive(tmp_path, [*rows, other]))
    assert not report["apx_price_product_complete"]
    assert report["other_provider_rows"] == 1
    assert report["coverage"]["missing_intervals"] == 1


def test_provenance_and_report_tamper_detection(tmp_path):
    path = archive(tmp_path, csv_rows())
    with pytest.raises(ValueError, match="UTC offset"):
        audit_mid_archive(
            path, 2016, source_url=SOURCE, licence="terms", retrieved_at_utc="2026-10-26"
        )
    with pytest.raises(ValueError, match="HTTPS"):
        audit_mid_archive(
            path, 2016, source_url="http://example.org/x", licence="terms",
            retrieved_at_utc=RETRIEVED
        )
    report = inspect(path)
    output = tmp_path / "audit.json"
    write_mid_audit(report, output)
    assert verify_mid_audit(output) == report
    with pytest.raises(FileExistsError, match="overwrite"):
        write_mid_audit(report, output)
    altered = json.loads(output.read_text())
    altered["S2_complete"] = True
    output.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="checksum"):
        verify_mid_audit(output)
