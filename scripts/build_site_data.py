"""Turn the output tables into compact JSON for the web dashboard.

Usage: python -I scripts/build_site_data.py
Writes site/data/{overview,prices,tests,regression,timeseries,bayes}.json. Headline numbers come from
outputs/tables/*.csv, so the page shows the same figures as the notebooks. The price explorer reads
data/processed/division_prices.parquet and national_prices.parquet. The Bayes calculator needs the mean
price paths after spike and no-spike months, which are recomputed here with src/bayes_decision.py exactly
as notebook 06 does, and checked against bayes_payoff_table.csv. Rerun after the notebooks change.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "outputs" / "tables"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "site" / "data"
sys.path.insert(0, str(ROOT / "src"))

ITEMS = {"rice_coarse": "Rice (coarse)", "atta": "Wheat flour (atta)", "lentil_masur": "Lentils (masur)",
         "palm_oil": "Palm oil", "soybean_oil": "Soybean oil", "sugar": "Sugar", "egg": "Egg",
         "chicken_broiler": "Chicken (broiler)", "onion": "Onion", "potato": "Potato", "chili_green": "Green chili"}
UNITS = {"palm_oil": "BDT per litre", "soybean_oil": "BDT per litre", "egg": "BDT per piece"}


def r(x, nd=0):
    if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
        return None
    return round(float(x), nd)


def dump(name, obj):
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"{p.relative_to(ROOT)}: {p.stat().st_size:,} bytes")


def facts(name):
    return pd.read_csv(TAB / f"key_facts_{name}.csv").set_index("fact")["value"]


def num(s, k):
    return float(s[k])


def ym(d):
    return pd.to_datetime(d).strftime("%Y-%m")


def rng(s):
    """'0.52 to 0.80' -> [0.52, 0.80]"""
    a, b = str(s).split(" to ")
    return [float(a), float(b)]


def tests_rows(df, nb):
    out = []
    for x in df.itertuples(index=False):
        out.append([nb, x.section, x.test, x.data, None if pd.isna(x.n) else int(x.n), r(x.statistic, 3), r(x.p, 4),
                    r(x.p_holm, 4), None if pd.isna(x.effect_name) else x.effect_name, r(x.effect, 3),
                    None if pd.isna(x.conclusion) else str(x.conclusion)])
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fi, ft, fr, fs, fb = facts("indices"), facts("tests"), facts("regression"), facts("timeseries"), facts("bayes")
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    idx = pd.read_csv(TAB / "indices_long_monthly.csv", parse_dates=["date"])

    # ---------- Overview ----------
    cmp_ = idx.dropna(subset=["fisher"])
    dump("overview", dict(
        generated=gen,
        months=[ym(d) for d in cmp_.date], fisher=[r(v, 2) for v in cmp_.fisher],
        cpi_food=[r(v, 2) for v in cmp_.cpi_food_2016],
        kpi=dict(
            fisher_last=r(num(fi, "long_fisher_last"), 1), last_month=str(fi["long_index_last_month"]),
            rice_share=r(num(fi, "rice_share_of_change"), 3),
            contrib={k: r(num(fi, f"contrib_{k}_pts"), 1) for k in ["rice_coarse", "palm_oil", "atta", "lentil_masur"]},
            sd_ratio=r(num(ft, "sd_ratio_staples_vs_cpi"), 2), sd_ratio_ci=rng(ft["sd_ratio_block_ci"]),
            sd_yoy_fisher=r(num(fi, "sd_yoy_fisher"), 2), sd_yoy_cpi=r(num(fi, "sd_yoy_cpi_food"), 2),
            palm_pt=r(num(fr, "lr_passthrough_palm_oil"), 3), palm_pt_ci=rng(fr["lr_passthrough_palm_oil_ci"]),
            palm_10=r(num(fr, "palm_oil_10pct_shock_effect_pct"), 1),
            ram_palm=r(num(ft, "ramadan_excess_palm_oil"), 2), ram_palm_p=r(num(ft, "ramadan_excess_p_palm_oil"), 3),
            ram_or=r(num(ft, "spike_or_ramadan"), 2), ram_or_p=r(num(ft, "spike_p_fisher_ramadan"), 3),
            ram_min_p=r(min(num(ft, f"ramadan_excess_p_{k}") for k in ["rice_coarse", "atta", "lentil_masur", "palm_oil"]), 3),
            bayes_pct=r(num(fb, "test_bayes_vs_monthly_pct"), 2), bayes_bdt_l=r(num(fb, "test_bayes_saving_bdt_per_litre"), 2),
            oracle_pct=r(num(fb, "test_oracle_vs_monthly_pct"), 2), fwd_pct=r(num(fb, "test_forward_vs_monthly_pct"), 2),
            corr_levels=r(num(fi, "corr_levels_fisher_cpi_food"), 3), corr_yoy=r(num(fi, "corr_yoy_fisher_cpi_food"), 3),
            gap_last=r(num(fi, "gap_levels_last_pct"), 1), cmp_last=str(fi["cmp_last_month"]),
            lead=int(num(fi, "best_lead_months")), lead_corr=r(num(fi, "best_lead_corr"), 3),
            wfp_rows=int(num(fi, "wfp_rows")), wfp_markets=int(num(fi, "wfp_markets")),
            wfp_commodities=int(num(fi, "wfp_commodities")))))

    # ---------- Prices & index numbers ----------
    dv = pd.read_parquet(PROC / "division_prices.parquet")
    na = pd.read_parquet(PROC / "national_prices.parquet")
    expl = {}
    for it, lab in ITEMS.items():
        n = na[na.item == it].sort_values("date")
        d = dv[dv.item == it]
        if n.empty:
            continue
        months = pd.date_range(min(n.date.min(), d.date.min()), max(n.date.max(), d.date.max()), freq="MS")
        piv = d.pivot_table(index="date", columns="division", values="price_bdt").reindex(months)
        nat = n.set_index("date").price_bdt.reindex(months)
        expl[it] = dict(label=lab, unit=UNITS.get(it, "BDT per kg"), basket=str(n.basket.iloc[0]),
                        months=[ym(m) for m in months], national=[r(v, 2) for v in nat],
                        divisions={c: [r(v, 2) for v in piv[c]] for c in sorted(piv.columns)})
    w = pd.read_csv(TAB / "index_weights.csv")
    ix = idx.dropna(subset=["laspeyres"])
    ann = pd.read_csv(TAB / "annual_inflation_staples_vs_cpi.csv")
    yy = idx.dropna(subset=["fisher_yoy", "cpi_food_2016_yoy"])
    sh = pd.read_parquet(PROC / "indices_short.parquet")
    dump("prices", dict(
        explorer=expl,
        index=dict(months=[ym(d) for d in ix.date], laspeyres=[r(v, 2) for v in ix.laspeyres], paasche=[r(v, 2) for v in ix.paasche],
                   fisher=[r(v, 2) for v in ix.fisher], chain=[r(v, 2) for v in ix.chain_laspeyres]),
        index_facts=dict(las=r(num(fi, "long_laspeyres_last"), 1), paa=r(num(fi, "long_paasche_last"), 1),
                         fis=r(num(fi, "long_fisher_last"), 1), chain=r(num(fi, "long_chain_laspeyres_last"), 1),
                         gap_max=r(num(fi, "long_laspeyres_paasche_gap_max_pct"), 2), gap_max_month=str(fi["long_laspeyres_paasche_gap_max_month"]),
                         sens_lo=r(num(fi, "sens_last_laspeyres_p05"), 1), sens_hi=r(num(fi, "sens_last_laspeyres_p95"), 1),
                         wide_gap=r(num(fi, "wide_lp_gap_mean_pct"), 2), long_gap_same=r(num(fi, "long_lp_gap_mean_pct_same_months"), 2),
                         wide_first=str(fi["wide_first_month"]), wide_last=str(fi["wide_last_month"]),
                         last=str(fi["long_index_last_month"])),
        short=dict(months=[ym(d) for d in sh.date], laspeyres=[r(v, 2) for v in sh.laspeyres], paasche=[r(v, 2) for v in sh.paasche],
                   fisher=[r(v, 2) for v in sh.fisher]),
        weights=[[x.basket, x.item, ITEMS.get(x.item, x.item), r(x.q0_per_person_month, 3), r(x.p0_bdt, 2), r(x.share, 4), x.source]
                 for x in w.itertuples()],
        annual=dict(years=[int(y) for y in ann.date], staple=[r(v, 1) for v in ann.staple_fisher], cpi=[r(v, 1) for v in ann.cpi_food]),
        yoy=dict(months=[ym(d) for d in yy.date], fisher=[r(v, 2) for v in yy.fisher_yoy], cpi=[r(v, 2) for v in yy.cpi_food_2016_yoy]),
        yoy_facts=dict(corr=r(num(fi, "corr_yoy_fisher_cpi_food"), 3), corr_annual=r(num(fi, "corr_annual_inflation"), 3),
                       sd_f=r(num(fi, "sd_yoy_fisher"), 2), sd_c=r(num(fi, "sd_yoy_cpi_food"), 2))))

    # ---------- Tests & tables ----------
    h2 = pd.read_csv(TAB / "tests_02_hypothesis.csv")
    h3 = pd.read_csv(TAB / "tests_03_contingency_gof.csv")
    ct = pd.read_csv(TAB / "tests_03_crosstabs.csv")
    keymap = {"Flood month (same month)": "flood", "Flood month (prices one month later)": "flood_lag1",
              "Ramadan month": "ramadan", "Month before Ramadan": "pre_ramadan",
              "Heavy-rain month, same division": "heavy_rain", "Heavy-rain month, prices one month later": "heavy_rain_lag1"}
    cross = []
    for ev, g in ct.groupby("event", sort=False):
        c = {(bool(a), bool(b)): int(n) for a, b, n in zip(g.event_month, g.spike, g["count"])}
        k = keymap.get(ev)
        orr = ft.get(f"spike_or_{k}") if k else None
        ci = None
        if k:
            how = pd.read_csv(TAB / "key_facts_tests.csv").set_index("fact").loc[f"spike_or_{k}", "how_computed"]
            ci = rng(how.split("95% CI ")[1])
        cross.append(dict(event=ev, ev_spike=c.get((True, True), 0), ev_none=c.get((True, False), 0),
                          oth_spike=c.get((False, True), 0), oth_none=c.get((False, False), 0),
                          odds=r(float(orr), 2) if orr is not None else None, ci=ci,
                          p_fisher=r(num(ft, f"spike_p_fisher_{k}"), 3) if k else None,
                          p_perm=r(num(ft, f"spike_p_perm_{k}"), 3) if k else None))
    dist = pd.read_csv(TAB / "tests_03_distribution_fit.csv")
    staples = ["rice_coarse", "atta", "lentil_masur", "palm_oil"]
    # division relative price level, 2025 average, % of national (from processed prices)
    d25 = dv[(dv.date.dt.year == 2025) & dv.item.isin(staples)]
    n25 = na[(na.date.dt.year == 2025) & na.item.isin(staples)][["date", "item", "price_bdt"]].rename(columns={"price_bdt": "nat"})
    m = d25.merge(n25, on=["date", "item"])
    m["rel"] = 100 * (m.price_bdt / m.nat - 1)
    lv = m.groupby(["division", "item"]).rel.mean().unstack()
    eta = {k: r(num(ft, f"anova_rel_eta2_{k}"), 3) for k in staples}
    dump("tests", dict(
        rows=tests_rows(h2, "02") + tests_rows(h3, "03"),
        counts=dict(t02=int(num(ft, "tests_02_total")), t02_raw=int(num(ft, "tests_02_reject_raw")), t02_holm=int(num(ft, "tests_02_reject_holm")),
                    t03=int(num(ft, "tests_03_total")), t03_raw=int(num(ft, "tests_03_reject_raw")), t03_holm=int(num(ft, "tests_03_reject_holm"))),
        ramadan=[[k, ITEMS[k], r(num(ft, f"ramadan_excess_{k}"), 2), r(num(ft, f"ramadan_excess_p_{k}"), 3)] for k in staples],
        ramadan_market=[[k, ITEMS.get(k, k), r(num(ft, f"ramadan_market_{k}"), 2)] for k in
                        ["sugar", "onion", "soybean_oil", "chicken_broiler", "egg", "lentil_masur", "palm_oil"]],
        levels=dict(divisions=list(lv.index), items=[ITEMS[k] for k in staples],
                    values=[[r(lv.loc[dname, k], 2) for k in staples] for dname in lv.index]),
        eta=eta, tukey_sig=int(num(ft, "tukey_rel_sig_pairs")), infl_any_sig=int(num(ft, "anova_infl_any_sig")),
        dearest=str(fi["division_dearest_2025"]), cheapest=str(fi["division_cheapest_2025"]),
        cross=cross,
        dist=[[x.item, ITEMS[x.item], int(x.n), r(x.sd, 2), r(x.skew, 2), r(x.excess_kurtosis, 2), r(x.shapiro_p, 4), r(x.jb_p, 4),
               r(x.t_df, 1), r(x.aic_normal - x.aic_t, 1), r(x.share_beyond_3sd, 4), r(x.normal_share_beyond_3sd, 4)] for x in dist.itertuples()],
        dir_season=dict(chi2=r(num(ft, "dir_season_chi2"), 1), p=r(num(ft, "dir_season_p_perm"), 3), v=r(num(ft, "dir_season_cramers_v"), 3)),
        gof=dict(chi2=r(num(ft, "gof_calendar_chi2"), 1), p=r(num(ft, "gof_calendar_p"), 3), peak=str(ft["gof_calendar_peak_month"]))))

    # ---------- Regression ----------
    cr = pd.read_csv(TAB / "regression_correlations.csv")
    vars_ = list(dict.fromkeys(list(cr.var1) + list(cr.var2)))
    heat = []
    for x in cr.itertuples():
        i, j = vars_.index(x.var1), vars_.index(x.var2)
        heat += [[i, j, r(x.pearson, 3), r(x.pearson_p, 4), int(x.n)], [j, i, r(x.pearson, 3), r(x.pearson_p, 4), int(x.n)]]
    heat += [[i, i, 1.0, None, None] for i in range(len(vars_))]
    sp = pd.read_csv(TAB / "regression_spurious_demo.csv")
    lr = pd.read_csv(TAB / "regression_longrun_passthrough.csv")
    lr = lr[lr.model.isin(["main_bdt", "main_fx_only"])]
    oos = pd.read_csv(TAB / "regression_out_of_sample.csv")
    simp = pd.read_csv(TAB / "regression_simple.csv")
    dump("regression", dict(
        vars=vars_, heat=heat,
        spurious=[[x.domestic, x.other, r(x.r_levels, 3), r(x.r_changes, 3), int(x.n_changes)] for x in sp.itertuples()],
        rw=dict(levels=r(num(fr, "spurious_rw_share_significant"), 3), diff=r(num(fr, "spurious_diff_share_significant"), 3)),
        simple=[[x.item, ITEMS[x.item], x.form, r(x.slope, 3), r(x.ci_low, 3), r(x.ci_high, 3), r(x.r2, 3), r(x.durbin_watson, 2), int(x.n)]
                for x in simp.itertuples()],
        passthrough=[[x.item, ITEMS[x.item], x.driver, r(x.sum, 3), r(x.ci_low, 3), r(x.ci_high, 3), r(x.wald_p, 4), r(x.wald_full_passthrough_p, 4), int(x.n),
                      r(num(fr, f"adj_r2_{x.item}"), 3)] for x in lr.itertuples()],
        oos=[[x.item, ITEMS[x.item], int(x.n_train), int(x.n_test), r(x.rmse_model, 3), r(x.rmse_mean_benchmark, 3), r(x.rmse_ratio, 3),
              r(x.oos_r2, 3), r(x.corr_pred_actual, 3)] for x in oos.itertuples()],
        diag=dict(bg=int(num(fr, "bg_reject_count")), bp=int(num(fr, "bp_reject_count")), jb=int(num(fr, "jb_reject_count")),
                  vif=r(num(fr, "max_vif_all_main_models"), 2)),
        panel=dict(lr=r(num(fr, "panel_palm_oil_lr"), 3), ci=rng(fr["panel_palm_oil_lr_ci"]), n=int(num(fr, "panel_palm_oil_n")),
                   fe_p=r(num(fr, "panel_division_fe_p"), 4)),
        fx_palm=dict(v=r(num(fr, "fx_passthrough_palm_oil"), 3), ci=rng(fr["fx_passthrough_palm_oil_ci"])),
        chow_min=r(min(num(fr, f"chow_2022_{k}_p") for k in staples), 3)))

    # ---------- Time series ----------
    si = pd.read_csv(TAB / "ts_seasonal_indices.csv")
    bt = pd.read_csv(TAB / "ts_backtest_summary.csv")
    fc = pd.read_csv(TAB / "ts_forecast_6m.csv")
    vol = pd.read_csv(TAB / "ts_volatility.csv")
    tf = pd.read_csv(TAB / "ts_trend_fits.csv").set_index("series")
    rv = pd.read_csv(TAB / "ts_rolling_volatility.csv").dropna(how="all", subset=staples)
    hist = {}
    rice = na[na.item == "rice_coarse"].set_index("date").price_bdt
    fis = idx.set_index("date").fisher.dropna()
    for key, s in [("rice_coarse", rice), ("staple_index", fis)]:
        s = s[s.index >= "2007-01-01"]
        ma = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)  # centred 2x12 moving average
        hist[key] = dict(months=[ym(d) for d in s.index], values=[r(v, 2) for v in s], trend=[r(v, 2) for v in ma])
    fcs = {}
    for key, g in fc.groupby("series"):
        fcs[key] = dict(months=[ym(d) for d in g.date], f=[r(v, 2) for v in g.forecast], lo80=[r(v, 2) for v in g.lo80], hi80=[r(v, 2) for v in g.hi80],
                        lo95=[r(v, 2) for v in g.lo95], hi95=[r(v, 2) for v in g.hi95], method=str(g.method.iloc[0]),
                        last_month=ym(g.last_actual_month.iloc[0]), last=r(g.last_actual.iloc[0], 2))
    dump("timeseries", dict(
        seasonal=dict(month=[int(x) for x in si.month], rice=[r(v, 2) for v in si.rice_coarse_seasonal_index],
                      lentil=[r(v, 2) for v in si.lentil_masur_seasonal_index], index=[r(v, 2) for v in si.staple_index_seasonal_index]),
        strength={k: [r(num(fs, f"stl_seasonal_strength_{k}"), 3), r(num(fs, f"stl_trend_strength_{k}"), 3)] for k in ["rice_coarse", "lentil_masur", "staple_index"]},
        trend={k: [r(tf.loc[k, "loglin_growth_pct_per_year"], 2), r(tf.loc[k, "loglin_ci_low"], 2), r(tf.loc[k, "loglin_ci_high"], 2)] for k in tf.index},
        hist=hist, forecast=fcs,
        backtest=[[x.series, x.method, r(x._3, 2), r(x._4, 2), r(x._5, 3), r(x._6, 3), int(x._7)] for x in bt.itertuples()],
        volatility=[[x.item, ITEMS[x.item], r(x.sd_mm_pct_short_window, 2), int(x.n_changes_short), r(x.max_rise_pct_short, 1), r(x.max_fall_pct_short, 1),
                     r(x.sd_mm_pct_2007_2026, 2)] for x in vol.itertuples()],
        rolling=dict(months=[ym(d) for d in rv.date], series={k: [r(v, 2) for v in rv[k]] for k in staples}),
        peak_rolling=str(fs["peak_rolling_vol"]),
        stationarity=pd.read_csv(TAB / "ts_stationarity.csv")[["series", "adf_p", "kpss_p", "verdict"]].round(3).values.tolist()))

    # ---------- Bayesian decision ----------
    import bayes_decision as bd
    raw = bd.load_data()
    THR = raw.loc["2007":"2019", "dlog"].quantile(0.90)
    df = bd.add_states(raw, THR, 5.0)
    tr = df.loc["2007":"2019"].dropna(subset=["spike_next", "sig_world", "ratio_3"])
    growth = {"spike next month": [tr.loc[tr.spike_next == 1, f"ratio_{k}"].mean() for k in (1, 2, 3)],
              "no spike": [tr.loc[tr.spike_next == 0, f"ratio_{k}"].mean() for k in (1, 2, 3)]}
    P0 = float(df.price.iloc[-1])
    R_LEND, S_MONTH = 0.1186, 0.005
    pay = bd.payoff_table(P0, growth, R_LEND, S_MONTH)
    pub = pd.read_csv(TAB / "bayes_payoff_table.csv").set_index("state")
    assert np.allclose(pay.round(0)[["cost_forward", "cost_monthly"]].values, pub[["cost_forward", "cost_monthly"]].values, atol=1), "payoff mismatch"
    n_sp, n_tr = int(tr.spike_next.sum()), len(tr)
    assert abs(n_sp / n_tr - num(fb, "prior_p_spike")) < 5e-4
    sig = pd.read_csv(TAB / "bayes_sensitivity_signal.csv")
    voi = pd.read_csv(TAB / "bayes_value_of_information.csv").iloc[0]
    emvt = pd.read_csv(TAB / "bayes_emv.csv", index_col=0)
    bts = pd.read_csv(TAB / "bayes_backtest_summary.csv")
    btm = pd.read_csv(TAB / "bayes_backtest_monthly.csv", index_col=0)
    bb = pd.read_csv(TAB / "bayes_beta_binomial.csv")
    th = np.linspace(0, 0.4, 161)
    dens = [[r(v, 3) for v in stats.beta.pdf(th, a, b)] for a, b in zip(bb.a[1:], bb.b[1:])]
    sav = (btm.cost_monthly - btm.bayes).cumsum() / 1e6
    savf = (btm.cost_monthly - btm.cost_forward).cumsum() / 1e6
    savo = (btm.cost_monthly - btm.oracle).cumsum() / 1e6
    sens = pd.read_csv(TAB / "bayes_sensitivity_rates.csv")
    dump("bayes", dict(
        P0=P0, growth_spike=growth["spike next month"], growth_none=growth["no spike"], qty=bd.QTY, H=bd.H,
        n_spike=n_sp, n_train=n_tr, threshold=r(THR, 2),
        base=dict(r=R_LEND, s=S_MONTH, m=1.0, x=5.0),
        signals=[dict(x=r(x.X_pct, 1), l1=float(x.p_sig_given_spike), l0=float(x.p_sig_given_none), post_on=r(x.posterior_on, 4),
                      evsi=r(x.evsi_bdt, 2), test_months=int(x.test_signal_months), test_pct=r(x.test_vs_monthly_pct, 2)) for x in sig.itertuples()],
        published=dict(prior=r(num(fb, "prior_p_spike"), 3), post_on=r(num(fb, "posterior_spike_signal_on"), 3), post_off=r(num(fb, "posterior_spike_signal_off"), 3),
                       breakeven=r(voi.breakeven_p, 4), evpi=r(voi.evpi_bdt, 2), evsi=r(voi.evsi_bdt, 2), p_signal=r(voi.p_signal, 4),
                       sav_spike=r(num(fb, "saving_forward_if_spike_bdt")), sav_none=r(num(fb, "saving_forward_if_no_spike_bdt")),
                       flip_rate=r(num(fb, "lending_rate_where_decision_flips_pct"), 1),
                       emv=[[i, r(x["P(spike)"], 3), r(x.cost_forward), r(x.cost_monthly), x.best_action] for i, x in emvt.iterrows()]),
        sens=[[r(x.lending_rate, 4), r(x.storage_loss_per_month, 4), r(x.breakeven_p, 3), bool(x.forward_if_signal_on)] for x in sens.itertuples()],
        backtest=[[x.strategy, r(x.total_cost_bdt), r(x.vs_monthly_bdt), r(x.vs_monthly_pct, 2), r(x.per_decision_bdt_per_litre, 2)] for x in bts.itertuples()],
        bt_facts=dict(n=int(num(fb, "n_test_decisions")), spike_rate=r(num(fb, "test_spike_rate"), 3), signal_months=int(num(fb, "test_signal_months")),
                      fwd_months=int(num(fb, "test_bayes_forward_months")), fwd_note=str(pd.read_csv(TAB / "key_facts_bayes.csv").set_index("fact").loc["test_bayes_forward_months", "how_computed"])),
        cum=dict(months=[ym(d) for d in btm.index], bayes=[r(v, 3) for v in sav], forward=[r(v, 3) for v in savf], oracle=[r(v, 3) for v in savo],
                 signal=[bool(v) for v in btm.signal], spike=[bool(v) for v in btm.spike_next]),
        beta=dict(theta=[r(v, 4) for v in th], dens=dens,
                  stages=[[x.stage, int(x.a), int(x.b), r(x["mean"], 4), r(x.lo, 4), r(x.hi, 4)] for _, x in bb.iterrows()])))

    # node-free check of the base case with the exported values
    ev, p_sig, post_on, post_off = bd.evsi(pay, n_sp / n_tr, *sig.loc[sig.X_pct == 5.0, ["p_sig_given_spike", "p_sig_given_none"]].values[0])
    print(f"check: prior={n_sp / n_tr:.3f} post_on={post_on:.3f} breakeven={bd.breakeven_p(pay):.3f} "
          f"EVPI={bd.evpi(pay, n_sp / n_tr):.0f} EVSI={ev:.0f} (published {voi.evpi_bdt:.0f}, {voi.evsi_bdt:.0f})")


if __name__ == "__main__":
    main()
