"""Tests for sroie_loader — covers all three label formats and the
auto-discovery of folder layouts (so the user doesn't have to rename
their downloaded dataset).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.backend.utils.sroie_loader import (
    discover_dataset,
    field_coverage,
    iter_samples,
    map_to_schema,
    parse_label_file,
)


# ─── Label format parsing ─────────────────────────────────────────────────

def test_parse_tab_separated(tmp_path):
    p = tmp_path / "X1234.txt"
    p.write_text("company\tACME LIMITED\ndate\t2019-03-15\ntotal\t12.50\n")
    out = parse_label_file(p)
    assert out["company"] == "ACME LIMITED"
    assert out["date"] == "2019-03-15"
    assert out["total"] == "12.50"


def test_parse_colon_separated(tmp_path):
    p = tmp_path / "X1234.txt"
    p.write_text("company:ACME LIMITED\ndate:2019-03-15\ntotal:12.50\n")
    out = parse_label_file(p)
    assert out["company"] == "ACME LIMITED"
    assert out["date"] == "2019-03-15"


def test_parse_json(tmp_path):
    p = tmp_path / "X1234.json"
    p.write_text(json.dumps({
        "company": "ACME LIMITED",
        "date": "2019-03-15",
        "total": "12.50",
        "address": "123 Main St",
    }))
    out = parse_label_file(p)
    assert out["company"] == "ACME LIMITED"
    assert out["address"] == "123 Main St"


def test_parse_json_handles_numeric_values(tmp_path):
    """SROIE total is sometimes serialized as a number, not a string."""
    p = tmp_path / "X1234.json"
    p.write_text(json.dumps({"total": 12.50, "company": "X"}))
    out = parse_label_file(p)
    assert out["total"] == "12.5"   # str() of float


def test_parse_empty_file_returns_empty_dict(tmp_path):
    p = tmp_path / "X1234.txt"
    p.write_text("")
    assert parse_label_file(p) == {}


def test_parse_unrecognized_lines_are_skipped(tmp_path):
    p = tmp_path / "X1234.txt"
    p.write_text("just a header line\ncompany\tX\nanother orphan line\n")
    out = parse_label_file(p)
    assert out == {"company": "X"}


def test_parse_handles_colon_inside_value(tmp_path):
    """Tab-separator must take priority — addresses commonly have colons."""
    p = tmp_path / "X1234.txt"
    p.write_text("address\t123 Main St: Suite A\n")
    out = parse_label_file(p)
    assert out["address"] == "123 Main St: Suite A"


# ─── Schema mapping ───────────────────────────────────────────────────────

def test_map_to_schema_renames_known_keys():
    raw = {"company": "ACME", "date": "2019-01-01", "total": "10",
           "address": "ignored"}
    out = map_to_schema(raw)
    assert out["vendor_name"] == "ACME"
    assert out["date"] == "2019-01-01"
    assert out["total_amount"] == "10"
    # Fields SROIE doesn't supply must be present and None — eval skips them
    assert out["invoice_number"] is None
    assert out["subtotal"] is None
    assert out["tax"] is None
    # SROIE-only keys (address) are dropped — we don't extract those
    assert "address" not in out


def test_map_to_schema_handles_missing_keys():
    out = map_to_schema({"company": "X"})
    assert out["vendor_name"] == "X"
    assert out["total_amount"] is None
    assert out["date"] is None


# ─── Dataset discovery ────────────────────────────────────────────────────

def _make_sroie_layout(root: Path, *, img_dir: str, lbl_dir: str) -> None:
    (root / img_dir).mkdir(parents=True)
    (root / lbl_dir).mkdir(parents=True)
    (root / img_dir / "X001.jpg").write_bytes(b"\xff\xd8")  # fake JPEG header
    (root / lbl_dir / "X001.txt").write_text("company\tACME\ntotal\t10\n")


def test_discover_dataset_finds_img_key(tmp_path):
    _make_sroie_layout(tmp_path, img_dir="img", lbl_dir="key")
    img_dir, lbl_dir = discover_dataset(tmp_path)
    assert img_dir.name == "img"
    assert lbl_dir.name == "key"


def test_discover_dataset_finds_images_labels(tmp_path):
    _make_sroie_layout(tmp_path, img_dir="images", lbl_dir="labels")
    img_dir, lbl_dir = discover_dataset(tmp_path)
    assert img_dir.name == "images"
    assert lbl_dir.name == "labels"


def test_discover_dataset_descends_into_single_nested_root(tmp_path):
    """Some downloads have one nested wrapper folder — auto-descend."""
    nested = tmp_path / "SROIE2019"
    _make_sroie_layout(nested, img_dir="img", lbl_dir="key")
    img_dir, lbl_dir = discover_dataset(tmp_path)
    assert img_dir.parent == nested
    assert lbl_dir.parent == nested


def test_discover_dataset_raises_when_missing(tmp_path):
    (tmp_path / "img").mkdir()
    # No label dir
    with pytest.raises(FileNotFoundError, match="label directory"):
        discover_dataset(tmp_path)


# ─── Iteration + pairing ──────────────────────────────────────────────────

def test_iter_samples_pairs_by_stem(tmp_path):
    _make_sroie_layout(tmp_path, img_dir="img", lbl_dir="key")
    samples = list(iter_samples(tmp_path))
    assert len(samples) == 1
    assert samples[0].image_path.name == "X001.jpg"
    assert samples[0].ground_truth["vendor_name"] == "ACME"
    assert samples[0].ground_truth["total_amount"] == "10"


def test_iter_samples_skips_unpaired_images(tmp_path):
    """Image without a label is silently skipped — common on partial uploads."""
    _make_sroie_layout(tmp_path, img_dir="img", lbl_dir="key")
    # Add an orphan image
    (tmp_path / "img" / "ORPHAN.jpg").write_bytes(b"\xff\xd8")
    samples = list(iter_samples(tmp_path))
    assert len(samples) == 1   # X001 still scored, ORPHAN skipped


def test_field_coverage_counts_non_null_per_field(tmp_path):
    img_dir = tmp_path / "img"
    lbl_dir = tmp_path / "key"
    img_dir.mkdir()
    lbl_dir.mkdir()
    (img_dir / "A.jpg").write_bytes(b"\xff\xd8")
    (img_dir / "B.jpg").write_bytes(b"\xff\xd8")
    (lbl_dir / "A.txt").write_text("company\tACME\ntotal\t10\n")
    (lbl_dir / "B.txt").write_text("company\tBETA\n")  # no total
    samples = list(iter_samples(tmp_path))
    cov = field_coverage(samples)
    assert cov["vendor_name"] == 2
    assert cov["total_amount"] == 1
