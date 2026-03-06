src/
====

Python source code for the project, organised as an installable package
(src/car_theft/).

Structure
---------
car_theft/
  __init__.py   - Package initialisation.
  main.py       - Entry point: sets random seeds, loads the raw CSV, and
                  prints summary statistics to stdout.

Adding new modules
------------------
Place new Python modules inside src/car_theft/.  They can then be imported
from notebooks and scripts via `from car_theft import <module>`.

Running the main script
-----------------------
    uv run python src/car_theft/main.py
