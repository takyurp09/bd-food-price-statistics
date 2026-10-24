"""Rebuild every output from data/raw/, in order, and print run times.

Run from anywhere:  python -I scripts/run_all.py
Needs the raw files made by src/download.py (run that first if data/raw/ is empty).
Notebooks run with the current Python's Jupyter kernel and are saved in place with their outputs.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "wfp_food_prices_bgd.csv"

STEPS = [
    ["src/clean.py"],
    ["src/indices.py"],
    ["src/build_notebook_01.py"],
    ["nb", "notebooks/01_data_and_indices.ipynb"],
    ["src/build_notebook_02.py"],
    ["nb", "notebooks/02_hypothesis_tests.ipynb"],
    ["src/build_notebook_03.py"],
    ["nb", "notebooks/03_contingency_tables.ipynb"],
    ["src/build_notebook_04.py"],
    ["nb", "notebooks/04_regression_correlation.ipynb"],
    ["src/build_notebook_05.py"],
    ["nb", "notebooks/05_time_series.ipynb"],
    ["src/build_notebook_06.py"],
    ["nb", "notebooks/06_bayesian_decision.ipynb"],
]


def main():
    if not RAW.exists():
        sys.exit(f"missing {RAW}; run python -I src/download.py first")
    times = []
    for step in STEPS:
        if step[0] == "nb":
            nb = ROOT / step[1]
            cmd = [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
                   "--ExecutePreprocessor.timeout=1800", str(nb)]
            cwd, name = nb.parent, step[1]
        else:
            cmd, cwd, name = [sys.executable, "-I", str(ROOT / step[0])], ROOT, step[0]
        t0 = time.time()
        print(f"== {name}", flush=True)
        subprocess.run(cmd, cwd=cwd, check=True)
        times.append((name, time.time() - t0))
    print("\nRun times")
    for name, s in times:
        print(f"  {name:45s} {s:7.1f} s")
    print(f"  {'total':45s} {sum(s for _, s in times):7.1f} s")


if __name__ == "__main__":
    main()
