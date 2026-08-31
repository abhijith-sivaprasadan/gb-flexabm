"""Local, loss-aware source extraction; outputs are NOT normalized model inputs.

XLSX cells preserve row/column identity, raw OOXML type, cached value and formula.
CSV parsing preserves strings. PDF text is page-indexed and requires visual/table review.
Nothing here changes the historical study's split or fits a model.
"""

import argparse
import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from zipfile import ZipFile

from gb_flexabm.public_inputs import checked_id, exclusive_json

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
LARGE_CSV_BYTES = 50_000_000


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = {"text": "", "attributes": dict(attrs)}

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def decode(body):
    try:
        return body.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return body.decode("cp1252"), "cp1252"


def extract_xlsx(source, destination):
    sheet_counts = []
    with ZipFile(source) as archive, destination.open("x", encoding="utf-8") as output:
        if sum(i.file_size for i in archive.infolist()) > 1_000_000_000:
            raise ValueError("XLSX inflated-size limit exceeded")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            with archive.open("xl/sharedStrings.xml") as stream:
                for _, element in ET.iterparse(stream, events=("end",)):
                    if element.tag == "{" + NS["s"] + "}si":
                        strings.append("".join(t.text or "" for t in element.findall(".//s:t", NS)))
                        element.clear()
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {e.attrib["Id"]: e.attrib["Target"] for e in relations}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        properties = workbook.find("s:workbookPr", NS)
        date1904 = properties is not None and properties.get("date1904") in {"1", "true"}
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            rel = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            target = targets[rel]
            member = target.lstrip("/") if target.startswith("/") else "xl/" + target
            count = formulas = 0
            with archive.open(member) as stream:
                for _, element in ET.iterparse(stream, events=("end",)):
                    if element.tag != "{" + NS["s"] + "}row":
                        continue
                    cells = []
                    for cell in element.findall("s:c", NS):
                        kind = cell.get("t", "n")
                        value = cell.findtext("s:v", default=None, namespaces=NS)
                        formula = cell.find("s:f", NS)
                        if kind == "s" and value is not None:
                            value = strings[int(value)]
                        elif kind == "inlineStr":
                            value = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                        if value is None and formula is None:
                            continue
                        record = {
                            "cell": cell.get("r"),
                            "type": kind,
                            "style_index": cell.get("s"),
                            "value": value,
                        }
                        if formula is not None:
                            record["formula"] = formula.text
                            record["formula_attributes"] = formula.attrib
                            formulas += 1
                        cells.append(record)
                    if cells:
                        output.write(
                            json.dumps(
                                {
                                    "sheet": sheet.get("name"),
                                    "row": element.get("r"),
                                    "cells": cells,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        count += 1
                    element.clear()
            sheet_counts.append(
                {"sheet": sheet.get("name"), "nonempty_rows": count, "formula_cells": formulas}
            )
    return {
        "sheets": sheet_counts,
        "date1904": date1904,
        "warning": "Numeric/date cached values retain raw OOXML strings; resolve styles/units/merged headers in original workbook. Formulas not recalculated.",
    }


def extract_one(record, raw_root, output_root):
    ident = checked_id(record["id"])
    digest = record["sha256"]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid source digest")
    source = raw_root / ident / digest / ("source." + record["format"])
    body = source.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Raw source hash mismatch")
    directory = output_root / ident / digest
    directory.mkdir(parents=True, exist_ok=True)
    receipt = directory / "extraction.json"
    if receipt.exists():
        result = json.loads(receipt.read_text(encoding="utf-8"))
        for item in result["outputs"]:
            path = directory / item["file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Extracted output hash mismatch")
        return result
    fmt = record["format"]
    large_csv = fmt == "csv" and len(body) > LARGE_CSV_BYTES
    extension = "jsonl" if fmt in {"xlsx", "pdf"} or large_csv else "json"
    target = directory / ("extracted." + extension)
    if target.exists():
        raise ValueError("Unfinished extraction exists; inspect before retrying")
    summary = {}
    if fmt == "xlsx":
        summary = extract_xlsx(source, target)
    elif fmt == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(source)
        empty = 0
        with target.open("x", encoding="utf-8") as output:
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() if page.get("/Contents") is not None else ""
                empty += not bool(text.strip())
                output.write(json.dumps({"page": number, "text": text}, ensure_ascii=False) + "\n")
        summary = {
            "pages": len(reader.pages),
            "empty_text_pages": empty,
            "warning": "Text extraction only; table alignment and scanned figures not certified",
        }
    elif fmt == "csv":
        text, encoding = decode(body)
        if large_csv:
            count, widths = 0, set()
            with target.open("x", encoding="utf-8") as output:
                for count, row in enumerate(csv.reader(io.StringIO(text)), 1):
                    widths.add(len(row))
                    output.write(
                        json.dumps({"row": count, "values": row}, ensure_ascii=False) + "\n"
                    )
            summary = {
                "rows_including_header": count,
                "row_widths": sorted(widths),
                "encoding": encoding,
                "storage": "row-indexed JSONL",
            }
        else:
            rows = list(csv.reader(io.StringIO(text)))
            summary = {
                "rows_including_header": len(rows),
                "row_widths": sorted(set(map(len, rows))),
                "encoding": encoding,
            }
            exclusive_json(
                target,
                {"rows": rows, "warning": "Original strings, no type/unit/period conversion"},
            )
    elif fmt == "html":
        text, encoding = decode(body)
        parser = Tables()
        parser.feed(text)
        summary = {"tables": len(parser.tables), "encoding": encoding}
        exclusive_json(
            target,
            {
                "tables": parser.tables,
                "warning": "rowspan/colspan preserved as attributes, not expanded",
            },
        )
    elif fmt == "json":
        exclusive_json(target, json.loads(body))
    else:
        raise ValueError("Extraction not implemented for " + fmt)
    result = {
        "id": ident,
        "source_sha256": digest,
        "source_url": record["url"],
        "status": "mechanical_extraction_only",
        "summary": summary,
        "outputs": [
            {"file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        ],
    }
    exclusive_json(receipt, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/public-inputs"))
    parser.add_argument("--output-root", type=Path, default=Path("data/processed/public-inputs-v2"))
    parser.add_argument(
        "--catalog", type=Path, default=Path("studies/historical-v1/public-sources.json")
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report path must be new")
    report = {"extractions": [], "failures": [], "model_ready": False}
    selected = {e["id"]: e for e in json.loads(args.catalog.read_text(encoding="utf-8"))["sources"]}
    for manifest in sorted(args.raw_root.glob("*/*/manifest.json")):
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if record["id"] not in selected or record["url"] != selected[record["id"]]["url"]:
            continue
        try:
            result = extract_one(record, args.raw_root, args.output_root)
            report["extractions"].append(result)
            print(json.dumps({"id": record["id"], **result["summary"]}), flush=True)
        except Exception as error:
            report["failures"].append({"id": record["id"], "error": str(error)})
            print(json.dumps(report["failures"][-1]), flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    exclusive_json(args.report, report)
    return 2 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
