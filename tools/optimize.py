"""Shrink image-heavy PDFs for printing: images above 300 dpi -> 220 dpi, JPEG q80.

usage: python optimize.py in.pdf out.pdf        (needs: pip install pymupdf)
"""
import sys, pymupdf

d = pymupdf.open(sys.argv[1])
d.rewrite_images(dpi_threshold=300, dpi_target=220, quality=80)
d.ez_save(sys.argv[2], garbage=4)
