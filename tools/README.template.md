# NIOS Open Basic Education (OBE) — study material, print-ready

Unofficial, organised mirror of the **National Institute of Open Schooling (NIOS)** Open Basic Education
study material — {{COUNT}} PDFs, laid out the same way as the NIOS page
[Open Basic Education → Study Material]({{SRC}}):
**Medium → Level (A / B / C) → Subject**, plus *Indian Knowledge Tradition* and sample question papers.

> **This is NIOS material, not ours.** © The National Institute of Open Schooling. Every row below links back to the
> original on nios.ac.in. Check the NIOS site for the latest official editions.

> 🕒 **Last checked against NIOS: {{CHECKED}}** · **Newest file change: {{UPDATED}}**  
> If the check date is recent, this mirror matches the NIOS page. It is refreshed by a manually run [workflow](../../actions/workflows/sync.yml) — always compare with the official NIOS site for the latest edition.

**Quick jump:** [English Medium](#english-medium) · [Hindi Medium](#hindi-medium) ·
[Indian Knowledge Tradition](#indian-knowledge-tradition-भारतीय-ज्ञान-परम्परा) ·
[Question papers](#sample-question-papers--question-paper-design) · [What was changed](#what-was-changed-from-the-nios-originals) ·
[Copyright](#copyright-and-reuse)

**⬇ = large file (10 MB+), hosted as a [GitHub Release asset](../../releases/tag/{{TAG}})** so the repository stays light to clone; everything else is stored in the repository folders.

Level guide (NIOS equivalence): **A** = Class 1–3 · **B** = Class 4–5 · **C** = Class 6–8.

{{TABLES}}

## What was changed from the NIOS originals

| Change | Where | Detail |
|---|---|---|
| **Kruti Dev font embedded** | Files whose headings / Sanskrit verses referenced the Kruti Dev font without embedding it | On computers without that font those lines showed as Latin junk (`ifjp; izLrqfr`). The real Kruti Dev font (published by NIOS itself on the page above) was embedded into the PDF, so the text now renders exactly as intended (`परिचय प्रस्तुति`). No text was retyped or converted. |
| **Smaller for printing** | Image-heavy PDFs | Images above 300 dpi were reduced to 220 dpi (JPEG q80) so files print sharply but are lighter. Text and layout unchanged. |

Content is otherwise unchanged. Scanned books (Science/Social Science, English medium) have no text layer. Two NIOS links were
dead (HTTP 404) when this was collected: Vijnana B English chapter 11 and Veda C Sanskrit chapter 6. Found an error? Please [open an issue](../../issues).

## Printing tips

- Print at **actual size / 100 %**, not "fit to page".
- Send the PDF as-is to a print shop — fonts for corrected headings are embedded.

## Repository layout

```
open-basic-education/{english,hindi}-medium/level-{a,b,c}/<subject>/…
open-basic-education/sample-question-papers/level-{a,b,c}/…
indian-knowledge-tradition/level-{a,b,c}/<course>-<code>/{hindi,sanskrit,english,common}/…
tools/    scripts used to prepare the PDFs (font embedding, image shrink)
```

## Tools

```
pip install pymupdf curl_cffi
python tools/fix_krutidev.py in.pdf out.pdf <font-dir>   # embed Kruti Dev (font-dir: unzip NIOS's hindi_font_krutidev.zip)
python tools/optimize.py in.pdf out.pdf                  # shrink images for print
python tools/sync.py --repo . --work /tmp/work           # the full pipeline (what the workflow runs)
```

Scripts are MIT-licensed; **the PDFs are not** (see below).

## Copyright and reuse

NIOS's [Terms & Conditions](https://nios.ac.in/terms-conditions.aspx) state:

> Material featured on this site may be reproduced free of charge in any format or media without requiring specific
> permission. This is subject to the material being reproduced accurately and not being used in a derogatory manner
> or in a misleading context. Where the material is being published or issued to others, the source must be
> prominently acknowledged. However, the permission to reproduce this material does not extend to any material on this
> site, which is explicitly identified as being the copyright of a third party.

This repository follows those terms: the source is acknowledged above, content is reproduced accurately (changes are
listed), and the PDFs are **not** relicensed. Third-party material inside the books remains with its owners. This is an
unofficial mirror, not affiliated with or endorsed by NIOS. If NIOS or a rights holder asks for removal, the affected
files will be removed.
