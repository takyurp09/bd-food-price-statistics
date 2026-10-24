"""Helpers for notebook 06: a forward-buy decision for palm oil solved with Bayes' rule.

Set-up. At the end of month t a buyer needs 1,000 litres of palm oil in each of months t+1, t+2, t+3.
  Action A1 "forward": buy all 3,000 L now at P_t and hold them; the litre used in month t+k carries
            k months of financing (r/12) and storage plus loss (s per month).
  Action A2 "monthly": buy 1,000 L each month at that month's price P_{t+k}.
State of nature: spike next month (palm oil m/m log change in t+1 above the 90th percentile of
2007-2019 changes) or no spike. Signal: world palm oil price in taka rose more than X% in month t,
or a flood was on record in month t.
"""
import numpy as np
import pandas as pd
from scipy import stats

from plot_utils import PROC
import timeseries as tsr

QTY = 1000.0     # litres per month
H = 3            # months covered by a forward buy


def load_data():
    """Monthly frame: palm oil national price, world palm oil in BDT per tonne, flood flag, plus derived columns."""
    p, _ = tsr.monthly_series(item="palm_oil")
    cov = pd.read_parquet(PROC / "covariates_monthly.parquet").set_index("date")
    df = pd.DataFrame({"price": p})
    df["world_bdt"] = (cov.world_palm_oil * cov.bdt_per_usd).reindex(df.index)
    df["flood"] = cov.flood_known.reindex(df.index).astype("boolean").fillna(False).astype(bool)
    df["dlog"] = 100 * np.log(df.price).diff()
    df["world_dlog"] = 100 * np.log(df.world_bdt).diff()
    for k in range(1, H + 1):
        df[f"ratio_{k}"] = df.price.shift(-k) / df.price
    df["next_dlog"] = df.dlog.shift(-1)
    return df


def add_states(df, threshold, world_x):
    """Add spike_next (state) and the signals, all known at the end of month t."""
    df = df.copy()
    df["spike_next"] = (df.next_dlog > threshold).where(df.next_dlog.notna())
    df["sig_world"] = (df.world_dlog > world_x).where(df.world_dlog.notna())
    df["sig_flood"] = df.flood
    df["sig_any"] = (df.sig_world.astype("boolean").fillna(False).astype(bool) | df.flood).where(df.world_dlog.notna())
    return df


def bayes_table(prior, lik_spike, lik_none, signal_on=True):
    """Textbook table: state, prior, likelihood of the observed signal, joint, posterior."""
    l1 = lik_spike if signal_on else 1 - lik_spike
    l0 = lik_none if signal_on else 1 - lik_none
    t = pd.DataFrame({"state": ["spike next month", "no spike"], "prior": [prior, 1 - prior],
                      "likelihood": [l1, l0]})
    t["joint"] = t.prior * t.likelihood
    t["posterior"] = t.joint / t.joint.sum()
    return t


def carry_per_month(r_annual, s_month):
    return r_annual / 12 + s_month


def payoff_table(P0, growth, r_annual, s_month):
    """Cost in BDT of covering 3 x 1,000 L under each action and state.
    growth: dict state -> list of mean P_{t+k}/P_t for k = 1..H."""
    c = carry_per_month(r_annual, s_month)
    rows = []
    for state, g in growth.items():
        monthly = sum(QTY * P0 * g[k - 1] for k in range(1, H + 1))
        forward = sum(QTY * P0 * (1 + k * c) for k in range(1, H + 1))
        rows.append({"state": state, "cost_forward": forward, "cost_monthly": monthly,
                     "saving_forward": monthly - forward})
    return pd.DataFrame(rows).set_index("state")


def emv(pay, p_spike):
    """Expected cost of each action for P(spike) = p_spike; lower is better."""
    w = pd.Series({"spike next month": p_spike, "no spike": 1 - p_spike})
    return pd.Series({"forward": (pay.cost_forward * w).sum(), "monthly": (pay.cost_monthly * w).sum()})


def evpi(pay, p_spike):
    w = pd.Series({"spike next month": p_spike, "no spike": 1 - p_spike})
    best_each = pay[["cost_forward", "cost_monthly"]].min(axis=1)
    return emv(pay, p_spike).min() - (best_each * w).sum()


def evsi(pay, prior, l1, l0):
    """Expected value of the signal: expected cost acting on the prior minus expected cost acting on the posterior."""
    p_sig = prior * l1 + (1 - prior) * l0
    post_on = prior * l1 / p_sig
    post_off = prior * (1 - l1) / (1 - p_sig)
    with_info = p_sig * emv(pay, post_on).min() + (1 - p_sig) * emv(pay, post_off).min()
    return emv(pay, prior).min() - with_info, p_sig, post_on, post_off


def breakeven_p(pay):
    """P(spike) at which the two actions cost the same."""
    d_spike = pay.loc["spike next month", "saving_forward"]
    d_none = pay.loc["no spike", "saving_forward"]
    if d_spike == d_none:
        return np.nan
    return -d_none / (d_spike - d_none)


def realized_costs(df, r_annual, s_month):
    """Realized cost of each action for each decision month, from actual prices."""
    c = carry_per_month(r_annual, s_month)
    fwd = sum(QTY * df.price * (1 + k * c) for k in range(1, H + 1))
    mon = sum(QTY * df.price.shift(-k) for k in range(1, H + 1))
    return pd.DataFrame({"cost_forward": fwd, "cost_monthly": mon}, index=df.index)


def beta_posterior(a, b, k, n, level=0.95):
    a2, b2 = a + k, b + n - k
    lo, hi = stats.beta.ppf([(1 - level) / 2, (1 + level) / 2], a2, b2)
    return {"a": a2, "b": b2, "mean": a2 / (a2 + b2), "lo": lo, "hi": hi}
