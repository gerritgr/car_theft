notebooks/
==========

Jupyter notebooks used for exploratory data analysis (EDA), prototyping, and
communicating results.

Naming convention
-----------------
Notebooks are prefixed with a two-digit number to indicate the intended order
of execution:

  01_eda.ipynb          - Initial exploration and data quality checks.
  02_feature_eng.ipynb  - Feature engineering experiments.
  03_modelling.ipynb    - Model training and evaluation prototypes.

Usage
-----
Start JupyterLab with:

    uv run jupyter lab

Then open the desired notebook from the file browser.

Important
---------
Keep notebooks focused on exploration and communication.  Reusable logic
should be refactored into src/car_theft/ modules.
