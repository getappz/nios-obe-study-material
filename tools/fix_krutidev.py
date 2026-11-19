"""Embed the Kruti Dev TrueType font into PDFs that reference it without embedding it.

Those PDFs show Latin junk (e.g. 'ifjp; izLrqfr') on machines without the font. The text is legacy-encoded, so the
fix is simply to attach the real font file to the existing font descriptor -- no text conversion.
usage: python fix_krutidev.py in.pdf out.pdf <dir-with-K010.TTF-and-Bold/Italic-ttfs>
"""
import sys, pymupdf

FILES = {(False, False): "K010.TTF", (True, False): "Kruti Dev 010 Bold.ttf",
         (False, True): "Kruti Dev 010 Italic.ttf", (True, True): "Kruti Dev 010 Bold Italic.ttf"}


def fix(d, fdir):
    """Attach the font to each non-embedded Kruti Dev font object; returns number of fonts patched."""
    streams, n = {}, 0
    for xref in range(1, d.xref_length()):
        try:
            if d.xref_get_key(xref, "Type")[1] != "/Font" or "Kruti" not in d.xref_get_key(xref, "BaseFont")[1]:
                continue
        except Exception:  # free/damaged xref entry
            continue
        k, v = d.xref_get_key(xref, "FontDescriptor")
        if k != "xref":
            continue
        desc = int(v.split()[0])
        if d.xref_get_key(desc, "FontFile2")[0] != "null":
            continue  # already embedded
        name = d.xref_get_key(xref, "BaseFont")[1].lower()
        key = ("bold" in name, "italic" in name)
        if key not in streams:
            sx = d.get_new_xref()
            d.update_object(sx, "<<>>")
            d.update_stream(sx, open(f"{fdir}/{FILES[key]}", "rb").read())
            streams[key] = sx
        d.xref_set_key(desc, "FontFile2", f"{streams[key]} 0 R")
        n += 1
    return n


if __name__ == "__main__":
    d = pymupdf.open(sys.argv[1])
    print(fix(d, sys.argv[3]), "fonts embedded")
    d.ez_save(sys.argv[2], garbage=4)
