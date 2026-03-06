reports/
========

Generated analysis outputs — HTML reports, PDFs, slide decks, and similar
artefacts that are intended for sharing with stakeholders.

Subdirectories
--------------
figures/  - Static image files (PNG, SVG, PDF) produced by the notebooks or
            src/ scripts.  These are referenced by reports and the README.

Workflow
--------
1. Run notebooks or `uv run python src/car_theft/main.py` to generate figures.
2. Figures are saved to reports/figures/.
3. Incorporate figures into your report template as needed.
