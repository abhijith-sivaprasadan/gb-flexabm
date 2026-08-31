import hashlib
import importlib.util
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from gb_flexabm.public_inputs import (
    acquire,
    audit_imrp,
    byte_limit,
    check_url,
    checked_id,
    snapshot,
)

SPEC = importlib.util.spec_from_file_location(
    "extract_public_inputs",
    Path(__file__).resolve().parents[1] / "scripts/extract_public_inputs.py",
)
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


@pytest.fixture
def entry():
    return {"id": "test-input", "url": "https://www.gov.uk/public.csv", "format": "csv"}


@pytest.mark.parametrize(
    "url",
    [
        "http://www.gov.uk/public.csv",
        "https://www.gov.uk.evil.example/data",
        "https://localhost/data",
        "https://user:pass@www.gov.uk/data",
        "file:///etc/passwd",
        "https://www.gov.uk:1234/data",
    ],
)
def test_reject_unapproved_urls(url):
    with pytest.raises(ValueError):
        check_url(url)


@pytest.mark.parametrize("ident", ["../escape", "a/b", "C:\\x", ".", "UPPER", ""])
def test_reject_path_ids(ident):
    with pytest.raises(ValueError):
        checked_id(ident)


def test_snapshots_append_and_rehash(tmp_path, entry):
    first = snapshot(tmp_path, entry, b"a,b\n1,2\n", final_url=entry["url"], acquisition="fixture")
    second = snapshot(tmp_path, entry, b"a,b\n3,4\n", final_url=entry["url"], acquisition="fixture")
    assert first["sha256"] != second["sha256"]
    assert len(list(tmp_path.glob("*/*/manifest.json"))) == 2
    assert acquire(tmp_path, entry)["cache_reused"] is True
    for source in tmp_path.glob("*/*/source.csv"):
        source.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        acquire(tmp_path, entry)


def test_signed_redirect_query_not_recorded(tmp_path, entry):
    result = snapshot(
        tmp_path,
        entry,
        b"a\n1\n",
        acquisition="fixture",
        final_url="https://lccc-ckan-storage-production.s3.amazonaws.com/file?X-Amz-Signature=SECRET",
    )
    assert "SECRET" not in json.dumps(result)


def test_error_html_not_accepted_as_csv(tmp_path, entry):
    with pytest.raises(ValueError, match="HTML"):
        snapshot(
            tmp_path,
            entry,
            b"<!DOCTYPE html><html>403</html>",
            final_url=entry["url"],
            acquisition="fixture",
        )


def test_imrp_split_prices_and_missing_years():
    body = b"IMRP_Date,Settlement_Period,IMRP_Amount\n2017-01-01 00:00:00,1,-2\n2019-01-01 00:00:00,1,not-inspected\n"
    report = audit_imrp(body, [2013, 2017])
    assert report["training_years"]["2013"]["absent_dates"] == 365
    assert report["training_negative_prices_retained"] == 1
    assert report["training_invalid_prices"] == 0
    assert not report["later_year_prices_inspected"]
    assert report["target_substitution"].startswith("none")


def test_imrp_duplicate_and_nonfinite_are_not_hidden():
    body = b"IMRP_Date,Settlement_Period,IMRP_Amount\n2017-01-01,1,nan\n2017-01-01,1,2\n"
    report = audit_imrp(body, [2017])
    assert report["duplicate_native_keys"] == 1
    assert report["training_invalid_prices"] == 1
    assert report["training_years"]["2017"]["noncontiguous_period_days"] == 1


def test_csv_extraction_preserves_quoted_newline(tmp_path, entry):
    raw, out = tmp_path / "raw", tmp_path / "out"
    record = snapshot(
        raw, entry, b'a,b\n1,"two\nlines"\n', final_url=entry["url"], acquisition="fixture"
    )
    result = extractor.extract_one(record, raw, out)
    target = out / entry["id"] / record["sha256"] / result["outputs"][0]["file"]
    assert json.loads(target.read_text())["rows"][1][1] == "two\nlines"
    assert extractor.extract_one(record, raw, out) == result
    target.write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        extractor.extract_one(record, raw, out)


def test_html_spans_are_retained():
    parser = extractor.Tables()
    parser.feed('<table><tr><th colspan="2">Unit</th></tr><tr><td>A</td><td>1</td></tr></table>')
    assert parser.tables[0][0][0]["attributes"]["colspan"] == "2"
    assert parser.tables[0][1][1]["text"] == "1"


def test_reviewed_byte_limits(tmp_path, entry):
    assert byte_limit(entry) == 100_000_000
    assert byte_limit({**entry, "max_bytes": 300_000_000}) == 300_000_000
    for invalid in [True, 0, -1, "300000000", 350_000_001]:
        with pytest.raises(ValueError, match="byte limit"):
            byte_limit({**entry, "max_bytes": invalid})
    with pytest.raises(ValueError, match="oversized"):
        snapshot(
            tmp_path,
            {**entry, "max_bytes": 1},
            b"abc",
            final_url=entry["url"],
            acquisition="fixture",
        )


def test_large_csv_row_stream(tmp_path, entry, monkeypatch):
    monkeypatch.setattr(extractor, "LARGE_CSV_BYTES", 1)
    raw, out = tmp_path / "raw", tmp_path / "out"
    record = snapshot(
        raw,
        entry,
        b'a,b\n1,"two\nlines"\n',
        final_url=entry["url"],
        acquisition="fixture",
    )
    result = extractor.extract_one(record, raw, out)
    target = out / entry["id"] / record["sha256"] / result["outputs"][0]["file"]
    rows = [json.loads(line) for line in target.read_text().splitlines()]
    assert rows == [
        {"row": 1, "values": ["a", "b"]},
        {"row": 2, "values": ["1", "two\nlines"]},
    ]
    assert result["summary"]["rows_including_header"] == 2
    assert result["summary"]["row_widths"] == [2]
    assert result["summary"]["storage"] == "row-indexed JSONL"


def test_pdf_without_content_stream(tmp_path, entry):
    writer, memory = pytest.importorskip("pypdf").PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=100, height=100)
    writer.write(memory)
    raw, out = tmp_path / "raw", tmp_path / "out"
    record = snapshot(
        raw,
        {**entry, "format": "pdf"},
        memory.getvalue(),
        final_url=entry["url"],
        acquisition="fixture",
    )
    result = extractor.extract_one(record, raw, out)
    assert result["summary"]["pages"] == 1
    assert result["summary"]["empty_text_pages"] == 1


def test_xlsx_formula_and_cell_identity(tmp_path):
    # Minimal authored OOXML fixture, not a user workbook or inferred numeric data.
    memory = io.BytesIO()
    with ZipFile(memory, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="1"/><sheets><sheet name="Inputs" r:id="r1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="B2"><f>1+2</f><v>3</v></c></row></sheetData></worksheet>',
        )
    source, target = tmp_path / "fixture.xlsx", tmp_path / "cells.jsonl"
    source.write_bytes(memory.getvalue())
    report = extractor.extract_xlsx(source, target)
    row = json.loads(target.read_text())
    assert report["date1904"]
    assert row["cells"][0] == {
        "cell": "B2",
        "type": "n",
        "style_index": None,
        "value": "3",
        "formula": "1+2",
        "formula_attributes": {},
    }


def test_catalog_unique_and_public():
    catalog = json.loads(
        (
            Path(__file__).resolve().parents[1] / "studies/historical-v1/public-sources.json"
        ).read_text()
    )
    sources = catalog["sources"]
    assert len({s["id"] for s in sources}) == len(sources)
    for source in sources:
        checked_id(source["id"])
        check_url(source["url"])
        assert source["license_status"]
        assert "raw_reference_only" in source["use_status"]


def test_published_inventory_matches_catalogue():
    root = Path(__file__).resolve().parents[1]
    catalogue = (root / "studies/historical-v1/public-sources.json").read_bytes()
    inventory = json.loads((root / "docs/reference/public-inputs-inventory.json").read_bytes())
    assert inventory["catalogue_sha256"] == hashlib.sha256(catalogue).hexdigest()
    sources = {entry["id"]: entry for entry in json.loads(catalogue)["sources"]}
    assert inventory["counts"]["catalogue_entries"] == len(sources)
    assert inventory["counts"]["acquired_snapshots"] == len(inventory["sources"])
    assert inventory["counts"]["raw_bytes"] == sum(s["bytes"] for s in inventory["sources"])
    assert inventory["model_ready"] is False
    for record in inventory["sources"]:
        assert record["url"] == sources[record["id"]]["url"]
        assert record["extraction"]["source_sha256"] == record["sha256"]
        assert record["extraction"]["status"] == "mechanical_extraction_only"
