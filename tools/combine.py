"""Combine chapter-split PDFs under indian-knowledge-tradition/ into single book PDFs.

Outputs to combined/<level>/<subject>-<medium>.pdf with PDF outline bookmarks
for Pre-Pages, each Chapter (in numeric order), and Question Paper Design /
Marking Scheme (when present). Unrelated circulars are excluded.

Usage:
    python tools/combine.py [--dry-run] [--out combined]
"""
import argparse
import os
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent.parent
IKT_DIR = ROOT / "indian-knowledge-tradition"

PRE_RE = re.compile(r"(?i)(pre[_-]?pages?|prepage|initial[_-]?pages?|cover[_-]?page)")
QPD_RE = re.compile(r"(?i)(qpd|marking[_-]?scheme|paper[_-]?design|sample[_-]?question)")
CHAP_RE = re.compile(r"(?i)(?:chap|ch)[_-]?(?:hindi[_-])?(\d+)")


def classify_pdf(filename: str) -> tuple[int, int, str] | None:
    """Return (group_order, item_order, bookmark_label) or None to skip."""
    if PRE_RE.search(filename):
        return (0, 0, "Pre-Pages")
    m = CHAP_RE.search(filename)
    if m:
        num = int(m.group(1))
        return (1, num, f"Chapter {num}")
    if QPD_RE.search(filename):
        return (2, 0, "Question Paper Design & Sample Paper")
    return None


def collect_books(ikt_dir: Path) -> list[tuple[Path, list[tuple[Path, str]]]]:
    """Find all subject/medium directories and return ordered (pdf_path, bookmark) lists."""
    books = []
    for dirpath, _, filenames in sorted(os.walk(ikt_dir)):
        pdfs = [f for f in filenames if f.lower().endswith(".pdf")]
        if not pdfs:
            continue
        items = []
        skipped = []
        for f in pdfs:
            cls = classify_pdf(f)
            if cls is None:
                skipped.append(f)
            else:
                items.append((cls[0], cls[1], cls[2], Path(dirpath) / f))
        items.sort(key=lambda x: (x[0], x[1], x[3].name))
        books.append((Path(dirpath), [(p, lbl) for _, _, lbl, p in items], skipped))
    return books


def combine_book(parts: list[tuple[Path, str]], out_path: Path) -> tuple[int, int]:
    """Merge parts into out_path with outline bookmarks. Returns (total_pages, bytes)."""
    writer = PdfWriter()
    for pdf_path, label in parts:
        reader = PdfReader(str(pdf_path))
        start_page = len(writer.pages)
        for page in reader.pages:
            writer.add_page(page)
        writer.add_outline_item(label, start_page)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return len(writer.pages), out_path.stat().st_size


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print merge plan without writing files")
    ap.add_argument("--out", default="combined", help="Output directory relative to repo root")
    args = ap.parse_args()

    out_root = ROOT / args.out
    books = collect_books(IKT_DIR)
    print(f"Found {len(books)} chapter-split books under {IKT_DIR.name}/")

    total_files = 0
    total_pages = 0
    for book_dir, parts, skipped in books:
        rel_parts = book_dir.relative_to(IKT_DIR).parts  # (level, subject, medium)
        level, subject, medium = rel_parts[0], rel_parts[1], rel_parts[2]
        out_path = out_root / level / f"{subject}-{medium}.pdf"
        if args.dry_run:
            skip_note = f" | skipped: {skipped}" if skipped else ""
            labels = ", ".join(lbl for _, lbl in parts)
            print(f"  {out_path.relative_to(ROOT)} <- {len(parts)} files [{labels}]{skip_note}")
        else:
            pages, size = combine_book(parts, out_path)
            total_files += 1
            total_pages += pages
            mb = size / (1024 * 1024)
            print(f"  ✓ {out_path.relative_to(ROOT)} ({len(parts)} files, {pages} pages, {mb:.2f} MB)")

    if not args.dry_run:
        print(f"\nDone: {total_files} combined PDFs, {total_pages} total pages -> {out_root.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
