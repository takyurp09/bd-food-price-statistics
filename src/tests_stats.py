"""Helpers for notebooks 02 (estimation and hypothesis tests) and 03 (contingency tables and goodness of fit).

Every test result is stored as one row with the same columns, so the notebooks can stack them into
outputs/tables/tests_*.csv and apply a Holm correction across a family of tests.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TAB = ROOT / "outputs" / "tables"

LONG = ["rice_coarse", "atta", "lentil_masur", "palm_oil"]
COLS = ["section", "test", "data", "n", "statistic", "df", "p", "effect_name", "effect", "ci_low", "ci_high",
        "conclusion"]
RNG_SEED = 173


# ---------- data ----------

def national_wide(items=None):
    """Month x item matrix of national prices (mean of division medians), regular monthly index."""
    n = pd.read_parquet(PROC / "national_prices.parquet")
    w = n.pivot(index="date", columns="item", values="price_bdt").asfreq("MS")
    return w if items is None else w[items]


def division_wide(item):
    d = pd.read_parquet(PROC / "division_prices.parquet")
    return d[d.item == item].pivot(index="date", columns="division", values="price_bdt").asfreq("MS")


def covariates():
    return pd.read_parquet(PROC / "covariates_monthly.parquet").set_index("date").asfreq("MS")


def dlog(w, lag=1):
    """100 x log change over `lag` months. A missing month gives NaN, never a change over a gap."""
    return 100 * (np.log(w) - np.log(w.shift(lag)))


# ---------- result rows ----------

def row(section, test, data, n, statistic, df, p, effect_name, effect, ci=(np.nan, np.nan), conclusion=""):
    return dict(zip(COLS, [section, test, data, n, statistic, df, p, effect_name, effect, ci[0], ci[1], conclusion]))


def holm(df, col="p", family=None):
    """Add p_holm. With `family` (a column name), Holm is applied within each family."""
    df = df.copy()
    df["p_holm"] = np.nan
    groups = [df.index] if family is None else [g.index for _, g in df.groupby(family)]
    for idx in groups:
        ok = df.loc[idx, col].notna()
        if ok.sum():
            df.loc[idx[ok.values], "p_holm"] = multipletests(df.loc[idx, col][ok], method="holm")[1]
    return df


def write_facts(facts, notebook):
    """Merge this notebook's facts into key_facts_tests.csv, replacing its earlier rows."""
    path = TAB / "key_facts_tests.csv"
    new = pd.DataFrame(facts).assign(notebook=notebook)
    if path.exists():
        old = pd.read_csv(path, dtype={"notebook": str})
        new = pd.concat([old[old.notebook != notebook], new], ignore_index=True)
        new = new.sort_values("notebook", kind="stable").reset_index(drop=True)  # same row order on every rerun
    new.to_csv(path, index=False)
    return new


# ---------- intervals ----------

def t_ci(x, level=0.95):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    h = stats.t.ppf(0.5 + level / 2, len(x) - 1) * se
    return m, m - h, m + h


def boot_ci(x, stat=np.mean, B=4000, block=None, level=0.95, seed=RNG_SEED):
    """Percentile bootstrap. block=None resamples single values (iid); block=L uses the moving block
    bootstrap, which keeps runs of L consecutive months together and so respects autocorrelation."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n, rng = len(x), np.random.default_rng(seed)
    if block is None:
        draws = stat(x[rng.integers(0, n, (B, n))], axis=1)
    else:
        k = int(np.ceil(n / block))
        starts = rng.integers(0, n - block + 1, (B, k))
        idx = (starts[:, :, None] + np.arange(block)).reshape(B, -1)[:, :n]
        draws = stat(x[idx], axis=1)
    a = (1 - level) / 2
    return stat(x), np.quantile(draws, a), np.quantile(draws, 1 - a)


def nw_lags(n):
    """Newey-West rule of thumb, floor(4 (n/100)^(2/9))."""
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def hac_ols(y, X, lags=None):
    """OLS with Newey-West (HAC) standard errors. X should already include a constant."""
    lags = nw_lags(len(y)) if lags is None else lags
    return sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def hac_mean(x, lags=None):
    """Mean of a series with a Newey-West 95% CI (regression on a constant)."""
    x = pd.Series(np.asarray(x, float)).dropna().reset_index(drop=True)
    r = hac_ols(x, np.ones((len(x), 1)), lags)
    lo, hi = r.conf_int().iloc[0]
    return r.params.iloc[0], lo, hi, r.tvalues.iloc[0], r.pvalues.iloc[0]


def block_boot_diff(a, b, B=4000, block=6, seed=RNG_SEED):
    """Difference in means b - a, each period resampled with the moving block bootstrap.
    Returns diff, CI and a two-sided p-value from the bootstrap distribution of the centred difference."""
    rng = np.random.default_rng(seed)

    def draw(x):
        x = np.asarray(x, float)
        x = x[~np.isnan(x)]
        n = len(x)
        k = int(np.ceil(n / block))
        starts = rng.integers(0, n - block + 1, (B, k))
        idx = (starts[:, :, None] + np.arange(block)).reshape(B, -1)[:, :n]
        return x[idx].mean(axis=1), x.mean()

    da, ma = draw(a)
    db, mb = draw(b)
    d = db - da
    obs = mb - ma
    p = np.mean(np.abs(d - obs) >= abs(obs))
    return obs, np.quantile(d, 0.025), np.quantile(d, 0.975), max(p, 1 / B)


# ---------- 2 x 2 tables ----------

def table2x2(x, y):
    """Counts with rows x = (False, True) and columns y = (False, True)."""
    t = pd.crosstab(pd.Series(x, name="x").astype(bool), pd.Series(y, name="y").astype(bool))
    return t.reindex(index=[False, True], columns=[False, True], fill_value=0)


def odds_ratio(t):
    """Odds ratio for a 2x2 table [[a, b], [c, d]] with Woolf 95% CI (0.5 added to every cell if any is 0)."""
    a, b, c, d = np.asarray(t, float).ravel()
    if min(a, b, c, d) == 0:
        a, b, c, d = a + .5, b + .5, c + .5, d + .5
    orr = (a * d) / (b * c)
    se = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return orr, np.exp(np.log(orr) - 1.96 * se), np.exp(np.log(orr) + 1.96 * se)


def cramers_v(t):
    t = np.asarray(t, float)
    chi2 = stats.chi2_contingency(t, correction=False)[0]
    return np.sqrt(chi2 / (t.sum() * (min(t.shape) - 1)))


def circular_shift_test(spikes, events, min_shift=12):
    """Block permutation test for association between two monthly 0/1 series (or T x M panels).

    The event series is rotated in time by every shift s (min_shift <= s <= T - min_shift) while the
    spike series stays fixed. Rotation keeps the run structure and autocorrelation of both series,
    which an ordinary chi-square test ignores. Statistic: spike rate in event months minus spike
    rate in other months. Returns observed statistic, p-value (two-sided) and the null draws.
    """
    S = np.asarray(spikes, float)
    E = np.asarray(events, float)
    if S.ndim == 1:
        S, E = S[:, None], E[:, None]
    T = S.shape[0]

    def stat(e):
        ok = ~np.isnan(S) & ~np.isnan(e)
        s, ev = S[ok], e[ok].astype(bool)
        if ev.sum() == 0 or (~ev).sum() == 0:
            return np.nan
        return s[ev].mean() - s[~ev].mean()

    obs = stat(E)
    null = np.array([stat(np.roll(E, k, axis=0)) for k in range(min_shift, T - min_shift + 1)])
    null = null[~np.isnan(null)]
    p = (1 + np.sum(np.abs(null) >= abs(obs) - 1e-12)) / (1 + len(null))
    return obs, p, null


def tests_2x2(x, y, section, label, block_x=None, block_y=None):
    """Chi-square, Fisher exact and odds ratio for event x vs spike y, plus the circular-shift
    permutation test when time-ordered arrays (T x M) are given in block_x / block_y."""
    t = table2x2(x, y)
    chi2, p_chi, dof, exp = stats.chi2_contingency(t.values, correction=False)
    orr, lo, hi = odds_ratio(t.values)
    _, p_f = stats.fisher_exact(t.values)
    v = cramers_v(t.values)
    rate_e = t.loc[True, True] / t.loc[True].sum() if t.loc[True].sum() else np.nan
    rate_n = t.loc[False, True] / t.loc[False].sum()
    n = int(t.values.sum())
    out = [
        row(section, "Chi-square independence", label, n, chi2, dof, p_chi, "Cramer's V", v,
            conclusion=f"min expected count {exp.min():.1f}"),
        row(section, "Fisher exact", label, n, np.nan, np.nan, p_f, "odds ratio", orr, (lo, hi),
            conclusion=f"spike rate {100 * rate_e:.1f}% in event months vs {100 * rate_n:.1f}% otherwise"),
    ]
    if block_x is not None:
        obs, p_perm, _ = circular_shift_test(block_y, block_x)
        out.append(row(section, "Circular-shift permutation", label, n, obs, np.nan, p_perm,
                       "rate difference (pp)", 100 * obs,
                       conclusion="event series rotated in time; keeps autocorrelation"))
    return t, out


# ---------- small helpers for tests of means ----------

def cohen_dz(diff):
    diff = np.asarray(diff, float)
    diff = diff[~np.isnan(diff)]
    return diff.mean() / diff.std(ddof=1)


def hedges_g(a, b):
    a, b = (np.asarray(v, float) for v in (a, b))
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    j = 1 - 3 / (4 * (na + nb) - 9)
    return j * (b.mean() - a.mean()) / sp


def lag1_autocorr(x):
    x = pd.Series(np.asarray(x, float)).dropna()
    return x.autocorr(1)


def welch_df(a, b):
    va, vb = np.var(a, ddof=1) / len(a), np.var(b, ddof=1) / len(b)
    return (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))


def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"
