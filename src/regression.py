"""Data assembly and model helpers for notebook 04 (correlation and regression).

Everything is monthly. Changes are 100 x log differences, so a coefficient of 0.3 on the world price
means a 10% world rise goes with a 3% domestic rise. World prices (World Bank Pink Sheet) end in Dec 2025,
so every model that uses them stops there.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

STAPLES = ["rice_coarse", "atta", "lentil_masur", "palm_oil"]
# domestic item -> Pink Sheet series (lentils have no Pink Sheet match)
WORLD_FOR = {"rice_coarse": "world_rice_thai5", "atta": "world_wheat_us_hrw", "palm_oil": "world_palm_oil",
             "lentil_masur": None}
WORLD = ["world_rice_thai5", "world_wheat_us_hrw", "world_palm_oil", "world_soybean_oil", "world_sugar_world"]
WORLD_LABEL = {"world_rice_thai5": "World rice (Thai 5%)", "world_wheat_us_hrw": "World wheat (US HRW)",
               "world_palm_oil": "World palm oil", "world_soybean_oil": "World soybean oil",
               "world_sugar_world": "World sugar", "bdt_per_usd": "BDT per USD", "rain_anom": "Rain anomaly (%)"}
DESIGN_BREAK = "2020-07-01"   # WFP moved from division series to district markets
DEPRECIATION = "2022-05-01"   # start of the 2022-23 taka depreciation
WORLD_END = "2025-12-01"      # last Pink Sheet month
NLAGS = 3


def hac_lags(n):
    """Newey-West rule of thumb: floor(4 (n/100)^(2/9))."""
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def load_monthly():
    """One row per month: log levels and 100 x dlog changes of staples, world prices (USD and BDT), FX,
    plus rain anomaly, flood, Ramadan and design-break dummies."""
    nat = pd.read_parquet(PROC / "national_prices.parquet")
    cov = pd.read_parquet(PROC / "covariates_monthly.parquet")
    rain = pd.read_parquet(PROC / "rain_division_monthly.parquet")
    dom = nat[nat.item.isin(STAPLES)].pivot(index="date", columns="item", values="price_bdt")
    idx = pd.date_range("2006-01-01", WORLD_END, freq="MS")
    df = cov.set_index("date").reindex(idx).join(dom.reindex(idx))
    df["rain_anom"] = rain.groupby("date").rain_anom_pct.mean().reindex(idx)
    df["flood"] = df.flood_known.map(lambda v: 1 if v is True or v == 1 else 0).astype(int)
    df["ramadan"] = df.ramadan_share.fillna(0)
    df["break2020"] = (df.index == DESIGN_BREAK).astype(int)
    df["post2022"] = (df.index >= DEPRECIATION).astype(int)
    df["month"] = df.index.month
    for c in STAPLES + WORLD + ["bdt_per_usd"]:
        df[f"l_{c}"] = np.log(df[c])
        df[f"d_{c}"] = 100 * df[f"l_{c}"].diff()      # NaN after any missing month
    for w in WORLD:
        df[f"l_{w}_bdt"] = df[f"l_{w}"] + df.l_bdt_per_usd
        df[f"d_{w}_bdt"] = df[f"d_{w}"] + df.d_bdt_per_usd
    df.index.name = "date"
    return df


def fisher_ci(r, n, level=0.95):
    z, se = np.arctanh(r), 1 / np.sqrt(n - 3)
    q = stats.norm.ppf(0.5 + level / 2)
    return np.tanh(z - q * se), np.tanh(z + q * se)


def corr_table(df, cols, labels):
    """Long table of pairwise Pearson and Spearman correlations with p-values and Fisher-z 95% CIs."""
    rows = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            x = df[[a, b]].dropna()
            n = len(x)
            pr, pp = stats.pearsonr(x[a], x[b])
            sr, sp = stats.spearmanr(x[a], x[b])
            lo, hi = fisher_ci(pr, n)
            slo, shi = fisher_ci(sr, n)
            rows.append({"var1": labels[a], "var2": labels[b], "n": n, "pearson": pr, "pearson_p": pp,
                         "pearson_ci_low": lo, "pearson_ci_high": hi, "spearman": sr, "spearman_p": sp,
                         "spearman_ci_low": slo, "spearman_ci_high": shi})
    return pd.DataFrame(rows)


def lag_names(var, nlags=NLAGS):
    return [f"{var}_L{k}" for k in range(nlags + 1)]


def design(df, item, world="bdt", nlags=NLAGS, fx=True, interact=False):
    """Build y and X for the pass-through model of one staple.

    world="bdt": world price converted to taka (headline 'taka terms' pass-through); world="usd": world price
    in dollars, with the exchange rate entered separately. Lentils get no world price.
    """
    y = df[f"d_{item}"].rename("dy")
    X = pd.DataFrame(index=df.index)
    w = WORLD_FOR[item]
    if w is not None and world is not None:
        src = f"d_{w}_bdt" if world == "bdt" else f"d_{w}"
        for k in range(nlags + 1):
            X[f"world_L{k}"] = df[src].shift(k)
    if fx and (world == "usd" or w is None):
        for k in range(nlags + 1):
            X[f"fx_L{k}"] = df.d_bdt_per_usd.shift(k)
            if interact:
                X[f"fx_L{k}_x_post2022"] = X[f"fx_L{k}"] * df.post2022
    X["rain_anom"] = df.rain_anom
    X["flood"] = df.flood
    X["ramadan"] = df.ramadan
    X["break2020"] = df.break2020
    if interact:
        X["post2022"] = df.post2022
    md = pd.get_dummies(df.month, prefix="m", drop_first=True).astype(float).set_index(df.index)
    X = X.join(md)
    d = pd.concat([y, X], axis=1).dropna()
    d = d.loc[:, (d != 0).any() | (d.columns == "dy")]   # drop a dummy that is all zero in the sample
    return d.dy, sm.add_constant(d.drop(columns="dy"))


def fit(y, X, hac=True):
    ols = sm.OLS(y, X).fit()
    if not hac:
        return ols, ols
    return ols, sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags(len(y))})


def coef_table(res, model, item):
    ci = res.conf_int()
    return pd.DataFrame({"model": model, "item": item, "term": res.params.index, "coef": res.params.values,
                         "se": res.bse.values, "t": res.tvalues.values, "p": res.pvalues.values,
                         "ci_low": ci[0].values, "ci_high": ci[1].values, "n": int(res.nobs)})


def sum_test(res, names, value=0.0):
    """Long-run (cumulative) coefficient: sum of the named coefficients, its SE, 95% CI and Wald test of sum = value."""
    r = np.zeros(len(res.params))
    for n in names:
        r[list(res.params.index).index(n)] = 1
    t = res.t_test((r, value))
    est = float(r @ res.params.values)
    se = float(np.sqrt(r @ res.cov_params().values @ r))
    lo, hi = np.asarray(t.conf_int()).ravel()
    return {"sum": est, "se": se, "ci_low": lo, "ci_high": hi, "wald_value": value,
            "wald_stat": float(np.asarray(t.tvalue).ravel()[0]) ** 2, "wald_p": float(t.pvalue)}


def joint_f(res, names):
    """Wald F-test that all named coefficients are zero (uses the model's own covariance, HAC if fitted so)."""
    hyp = ", ".join(f"{n} = 0" for n in names)
    t = res.f_test(hyp)
    return float(np.asarray(t.fvalue).ravel()[0]), float(t.pvalue), int(t.df_num)


def diagnostics(ols, X):
    """Classical residual tests on the OLS fit (the HAC fit has the same residuals)."""
    bp = het_breuschpagan(ols.resid, X)
    bg = acorr_breusch_godfrey(ols, nlags=12)
    jb = jarque_bera(ols.resid)
    cols = [c for c in X.columns if c != "const" and not c.startswith("m_")]
    vif = {c: variance_inflation_factor(X.values, list(X.columns).index(c)) for c in cols}
    return {"n": int(ols.nobs), "r2": ols.rsquared, "adj_r2": ols.rsquared_adj,
            "breusch_pagan_lm": bp[0], "breusch_pagan_p": bp[1], "breusch_godfrey_lm12": bg[0],
            "breusch_godfrey_p": bg[1], "jarque_bera": jb[0], "jarque_bera_p": jb[1], "skew": jb[2],
            "kurtosis": jb[3], "durbin_watson": durbin_watson(ols.resid), "max_vif": max(vif.values()),
            "max_vif_term": max(vif, key=vif.get)}, vif


def chow(y, X, split):
    """Classic Chow F-test for a break at `split` (homoskedastic errors), on the same regressors.
    Dummies that are constant in either subsample are dropped from all three fits."""
    pre, post = y.index < split, y.index >= split
    keep = [c for c in X.columns if c == "const" or (X.loc[pre, c].std() > 0 and X.loc[post, c].std() > 0)]
    X = X[keep]
    rss = sm.OLS(y, X).fit().ssr
    r1, r2 = sm.OLS(y[pre], X[pre]).fit().ssr, sm.OLS(y[post], X[post]).fit().ssr
    k, n = X.shape[1], len(y)
    f = ((rss - r1 - r2) / k) / ((r1 + r2) / (n - 2 * k))
    return f, 1 - stats.f.cdf(f, k, n - 2 * k), k, n - 2 * k, int(post.sum())
