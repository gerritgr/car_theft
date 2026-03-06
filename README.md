# car_theft

Spatio-temporal analysis of the **NYC Vehicle Collisions** dataset, following a
minimal [Cookiecutter Data Science (CCDS)](https://drivendata.github.io/cookiecutter-data-science/)
project structure.

---

## Project layout

```
car_theft/
├── data/
│   ├── raw/                  <- Original, immutable data (not in git)
│   ├── processed/            <- Cleaned / transformed data (not in git)
│   ├── download_data.py      <- Script to fetch the dataset
│   └── README.txt
├── notebooks/
│   ├── 01_eda.ipynb          <- Exploratory data analysis
│   └── README.txt
├── references/               <- Data dictionaries, papers, etc.
├── reports/
│   └── figures/              <- Generated plots
├── src/
│   └── car_theft/
│       ├── __init__.py
│       └── main.py           <- Entry-point script
├── pyproject.toml            <- Project metadata & dependencies (uv)
└── README.md
```

---

## Dataset

**NYC Vehicle Collisions** – published by the NYPD  
https://www.kaggle.com/datasets/nypd/vehicle-collisions

---

## Prerequisites

| Tool | Notes |
|------|-------|
| [uv](https://docs.astral.sh/uv/) | Fast Python package & project manager |
| Python ≥ 3.10 | Managed automatically by uv |
| Kaggle API token | Required to download the dataset; see [Kaggle docs](https://www.kaggle.com/docs/api) |

Install **uv** (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Installation

Clone the repository and let uv create a virtual environment with all
dependencies in one step:

```bash
git clone https://github.com/gerritgr/car_theft.git
cd car_theft

# Create .venv and install all dependencies (including PyTorch, TSL, etc.)
uv sync
```

> `uv sync` reads `pyproject.toml`, resolves the dependency graph, and
> installs everything into `.venv` automatically.  No manual `pip install`
> is needed.

### Installing extra tools (optional)

```bash
# Add kaggle SDK (needed for the download script)
uv pip install kaggle
```

---

## Downloading the data

```bash
# Place your Kaggle API token at ~/.kaggle/kaggle.json first, then:
uv run python data/download_data.py
```

The script downloads the dataset to `data/raw/vehicle_collisions.csv` and is
idempotent – running it again when the file already exists does nothing.

---

## Running the main script

The main script sets random seeds, loads the raw CSV, and prints summary
statistics:

```bash
uv run python src/car_theft/main.py
```

Expected output (abbreviated):

```
[main] Random seeds set to 42.
[main] Loading data from '.../data/raw/vehicle_collisions.csv' …
[main] Loaded 1,900,000 rows × 29 columns.

============================================================
DATASET SUMMARY
============================================================
Shape : 1,900,000 rows × 29 columns
...
```

---

## Exploratory notebooks

Start JupyterLab and open `notebooks/01_eda.ipynb`:

```bash
uv run jupyter lab
```

---

## Dependencies

Declared in `pyproject.toml` and managed by **uv**:

| Package | Purpose |
|---------|---------|
| pandas | Tabular data manipulation |
| matplotlib | Plotting |
| seaborn | Statistical visualisation |
| torch (PyTorch) | Deep learning |
| scikit-learn | Classical ML |
| jupyterlab | Interactive notebooks |
| [tsl](https://github.com/TorchSpatiotemporal/tsl) | Spatio-temporal learning with PyTorch |

