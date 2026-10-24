"""Time-series helpers for notebook 05: series prep, seasonal indices, trend fits, tests, backtests."""
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller, kpss

from plot_utils import PROC


def monthly_series(item=None, index_col=None, start="2007-01-01", max_gap=3):
    """National price of one item, or one column of indices_long, on a full monthly grid.
    Gaps of up to max_gap months are filled by linear interpolation in logs; returns (series, n_filled)."""
    if item is not None:
        nat = pd.read_parquet(PROC / "national_prices.parquet")
        s = nat[nat.item == item].set_index("date").price_bdt
    else:
        s = pd.read_parquet(PROC / "indices_long.parquet").set_index("date")[index_col]
    s = s.dropna()
    s = s[s.index >= start]
    full = pd.date_range(s.index.min(), s.index.max(), freq="MS")
    s = s.reindex(full)
    n_missing = int(s.isna().sum())
    s = np.exp(np.log(s).interpolate(limit=max_gap, limit_area="inside"))
    s = s.dropna()
    s.index.freq = "MS"
    return s, n_missing


def seasonal_index_ratio_ma(s):
    """Classical ratio-to-moving-average seasonal index (multiplicative), normalised to average 100."""
    ma = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)  # 2x12 centred MA
    ratio = (s / ma).dropna()
    raw = ratio.groupby(ratio.index.month).mean()
    idx = 100 * raw / raw.mean()
    n = ratio.groupby(ratio.index.month).size()
    sd = ratio.groupby(ratio.index.month).std() * 100 / raw.mean()
    return pd.DataFrame({"seasonal_index": idx, "sd": sd, "n_years": n}).rename_axis("month"), ma


def trend_fit(s, log=False):
    """OLS trend on t = 0,1,2,...; returns fitted model and frame with fit and 95% CI (in levels)."""
    t = np.arange(len(s))
    X = sm.add_constant(t)
    y = np.log(s.values) if log else s.values
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 12})
    pr = m.get_prediction(X).summary_frame(alpha=0.05)
    f = pr[["mean", "mean_ci_lower", "mean_ci_upper"]]
    if log:
        f = np.exp(f)
    f.index = s.index
    return m, f


def stationarity(s, name):
    """ADF (H0 unit root) and KPSS (H0 level stationary) for one series."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = adfuller(s.dropna(), autolag="AIC")
        k = kpss(s.dropna(), regression="c", nlags="auto")
    return {"series": name, "n": int(s.notna().sum()), "adf_stat": a[0], "adf_p": a[1], "adf_lags": a[2],
            "kpss_stat": k[0], "kpss_p": k[1],
            "verdict": ("stationary" if a[1] < 0.05 and k[1] > 0.05 else
                        "non-stationary" if a[1] >= 0.05 and k[1] <= 0.05 else "mixed")}


SARIMA_ORDER, SARIMA_SEASONAL = (1, 1, 1), (0, 0, 1, 12)


def fc_snaive(train, h):
    last = train.iloc[-12:].values
    return np.array([last[i % 12] for i in range(h)])


def fc_ets(train, h, return_model=False):
    """Additive-trend (damped) ETS with multiplicative-in-levels seasonality, fitted on logs."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = ExponentialSmoothing(np.log(train), trend="add", damped_trend=True, seasonal="add",
                                 seasonal_periods=12, initialization_method="estimated").fit()
    f = np.exp(m.forecast(h).values)
    return (f, m) if return_model else f


def fc_sarima(train, h, return_model=False):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = SARIMAX(np.log(train), order=SARIMA_ORDER, seasonal_order=SARIMA_SEASONAL,
                    trend="t").fit(disp=False)
    f = np.exp(m.get_forecast(h).predicted_mean.values)
    return (f, m) if return_model else f


METHODS = {"seasonal_naive": fc_snaive, "ets": fc_ets, "sarima": fc_sarima}


def backtest(s, origins, h=12):
    """Rolling-origin backtest. For each origin, fit on data up to origin and forecast h months.
    Returns long frame of errors; MASE scaled by in-sample seasonal-naive MAE of each training set."""
    rows = []
    for o in origins:
        train = s[s.index <= o]
        test = s[(s.index > o)].iloc[:h]
        scale = np.mean(np.abs(train.values[12:] - train.values[:-12]))
        for name, fn in METHODS.items():
            f = fn(train, len(test))
            for k, (d, a, p) in enumerate(zip(test.index, test.values, f), 1):
                rows.append({"origin": o, "method": name, "horizon": k, "date": d, "actual": a, "forecast": p,
                             "ape": abs(a - p) / a * 100, "ase": abs(a - p) / scale})
    return pd.DataFrame(rows)
