# AGENTS.md

## Cursor Cloud specific instructions

### Overview

ABU (阿布量化) is a Python quantitative trading / algorithmic trading system (v0.4.0). It supports backtesting, ML-driven strategy optimization, and technical analysis across US/CN/HK stocks, futures, options, and crypto.

### Python Version Requirement

This codebase **requires Python 3.8** (installed from `ppa:deadsnakes/ppa`). Python 3.10+ will fail due to `collections.Iterable` removal and other breaking changes. A virtualenv at `/workspace/.venv` is set up with Python 3.8.

Always activate the venv before any Python commands:
```
source /workspace/.venv/bin/activate
```

### Pinned Dependency Versions (Critical)

The codebase requires specific older versions of core libraries. Using newer versions will cause runtime errors:

- `pandas==0.25.3` — newer pandas breaks `df.loc[index]` alignment in `ABuSymbolPd._benchmark()`
- `numpy==1.19.5` — must be compatible with pandas 0.25.3
- `scipy<1.8` — `scipy.interp` was removed in scipy 1.11+; `ABuMLExecute.py` imports it
- `scikit-learn<1.1` — API compatibility with the codebase's sklearn usage
- `matplotlib<3.6` — compatible with numpy 1.19.5

### Running the Application

There is no standalone server. The system runs via Python scripts or Jupyter notebooks.

**Sandbox/example mode** (uses bundled CSV data, no network required):
```python
import matplotlib; matplotlib.use('Agg')
from abupy import env
env.enable_example_env_ipython()
```

**Lint**: `flake8 abupy/ --select=E9,F63,F7,F82` (pre-existing errors in bundled `ExtBu/six.py` are expected)

**No automated test suite** exists in this project. The "test" per the README is `import abupy`.

### Key Gotchas

- When running headless (no display), set `matplotlib.use('Agg')` **before** any other matplotlib/abupy imports.
- The project has no `setup.py`, `requirements.txt`, or formal dependency management.
- Tutorial notebooks are in `abupy_lecture/`, UI widgets in `abupy_ui/`, book examples in `ipython/` and `python/`.
- The bundled test data is in `abupy/RomDataBu/csv.zip` and is auto-extracted on first `enable_example_env_ipython()` call.
