"""SROIE-v2 dataset loader.

Handles the format variation across the public SROIE bundles:
  - Original ICDAR 2019 layout: `img/` + `box/` + `entities/` (JSON)
  - Common Kaggle re-bundle:    `img/` + `key/`  (tab-separated `key\\tvalue`)
  - Some packs also use:        `images/` + `labels/` (JSON or txt)

The loader auto-detects which is which so the same eval script works on
whatever shape the user downloads. Mapping from SROIE fields to our
internal schema:

    SROIE                Our schema
    ---------------      ----------------
    company         →    vendor_name
    date            →    date
    total           →    total_amount
    address         →    (no equivalent — skipped)

Subtotal/tax/invoice_number aren't in SROIE — we leave them as None on the
ground-truth side so the eval doesn't punish the model for fields we have
no truth for.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# SROIE → our schema. Other SROIE keys are silently ignored.
_FIELD_MAP = {
    "company": "vendor_name",
    "date": "date",
    "total": "total_amount",
}


# Candidate folder names — we'll discover whichever pair exists.
_IMAGE_DIRS = ("img", "images", "image")
_LABEL_DIRS = ("key", "entities", "labels", "label", "txt")


@dataclass(frozen=True)
class SroieSample:
    image_path: Path
    label_path: Path
    ground_truth: dict[str, str | None]   # keyed by OUR schema field names
    raw_label: dict[str, str | None]      # keyed by SROIE original keys


def parse_label_file(path: Path) -> dict[str, str | None]:
    """Parse one SROIE label file. Tries JSON, then tab-separated, then
    colon-separated. Returns SROIE-native keys (caller maps to our schema).
    """
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return {}

    # Try JSON
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return {k.lower().strip(): _normalize_value(v) for k, v in obj.items()}
    except json.JSONDecodeError:
        pass

    # Try tab- or colon-separated. Tab takes priority because some Kaggle
    # bundles include colons inside values (e.g. addresses).
    out: dict[str, str | None] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if "\t" in line:
            key, _, value = line.partition("\t")
        elif ":" in line:
            key, _, value = line.partition(":")
        else:
            continue
        key = key.strip().lower()
        value = value.strip()
        out[key] = value if value else None
    return out


def _normalize_value(v) -> str | None:
    """Coerce JSON values to clean strings; None stays None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).strip()
    return s if s else None


def map_to_schema(raw_label: dict[str, str | None]) -> dict[str, str | None]:
    """Map SROIE keys to our extraction schema. Unknown keys are dropped;
    fields we extract but SROIE doesn't supply are filled with None."""
    out = {
        "invoice_number": None,
        "date": None,
        "vendor_name": None,
        "subtotal": None,
        "tax": None,
        "total_amount": None,
    }
    for sroie_key, our_key in _FIELD_MAP.items():
        if sroie_key in raw_label:
            out[our_key] = raw_label[sroie_key]
    return out


def _find_dir(root: Path, candidates: tuple[str, ...]) -> Path | None:
    """Return the first existing subdirectory matching one of `candidates`,
    case-insensitive. Returns None if none found."""
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name.lower() in candidates:
            return child
    return None


def discover_dataset(root: Path) -> tuple[Path, Path]:
    """Locate the image and label directories under `root`.

    Returns (image_dir, label_dir). Raises FileNotFoundError if either is
    missing — gives a specific message naming what was searched for.
    """
    if not root.exists():
        raise FileNotFoundError(f"SROIE root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"SROIE root is not a directory: {root}")

    # Some downloads have a single nested top-level folder (e.g.
    # `SROIE2019/` inside the bundle). If so, descend into it.
    if not any(c.name.lower() in _IMAGE_DIRS + _LABEL_DIRS for c in root.iterdir() if c.is_dir()):
        nested = [c for c in root.iterdir() if c.is_dir()]
        if len(nested) == 1:
            root = nested[0]

    img_dir = _find_dir(root, _IMAGE_DIRS)
    lbl_dir = _find_dir(root, _LABEL_DIRS)
    if img_dir is None:
        raise FileNotFoundError(
            f"No image directory found under {root}. Looked for: {_IMAGE_DIRS}"
        )
    if lbl_dir is None:
        raise FileNotFoundError(
            f"No label directory found under {root}. Looked for: {_LABEL_DIRS}"
        )
    return img_dir, lbl_dir


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_LABEL_EXTS = {".txt", ".json"}


def iter_samples(root: Path) -> Iterator[SroieSample]:
    """Iterate matched (image, label) pairs from a discovered SROIE root.

    Pairing is by stem: `img/X1234.jpg` matches `key/X1234.txt`. Images
    without a corresponding label (or vice versa) are skipped with a
    debug log entry — common on partial Kaggle re-uploads where some
    annotation files are missing.
    """
    img_dir, lbl_dir = discover_dataset(root)

    labels_by_stem: dict[str, Path] = {}
    for p in lbl_dir.iterdir():
        if p.is_file() and p.suffix.lower() in _LABEL_EXTS:
            labels_by_stem[p.stem] = p

    for img_path in sorted(img_dir.iterdir()):
        if not img_path.is_file():
            continue
        if img_path.suffix.lower() not in _IMAGE_EXTS:
            continue
        lbl = labels_by_stem.get(img_path.stem)
        if lbl is None:
            logger.debug("no label for image %s; skipping", img_path.name)
            continue
        try:
            raw = parse_label_file(lbl)
        except Exception as e:
            logger.warning("failed to parse label %s: %s", lbl, e)
            continue
        yield SroieSample(
            image_path=img_path,
            label_path=lbl,
            ground_truth=map_to_schema(raw),
            raw_label=raw,
        )


def field_coverage(samples: list[SroieSample]) -> dict[str, int]:
    """Report how many samples have a non-null value for each schema field.
    Useful to know which fields the eval can actually score on this dataset."""
    counts: dict[str, int] = {}
    for s in samples:
        for k, v in s.ground_truth.items():
            if v:
                counts[k] = counts.get(k, 0) + 1
    return counts
