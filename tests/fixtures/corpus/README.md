# Private compatibility corpus

Keep real-world test documents outside Git. This directory is intentionally
empty except for this policy.

Recommended private categories:

- normal, encrypted, damaged, scanned, form, annotated, bookmarked, and very
  large PDFs;
- DOCX files with tables, headers, footnotes, tracked changes, and images;
- XLSX files with formulas, merged cells, charts, images, and many sheets;
- PPTX files with masters, themes, tables, charts, SmartArt, and grouped shapes;
- images with unusual dimensions, profiles, transparency, and metadata.

Run `python scripts/verify_corpus.py /private/path`. Never commit customer,
school, government, medical, financial, or otherwise sensitive documents.
