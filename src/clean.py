"""Turn the raw downloads into tidy tables in data/processed/.

Run: python -I src/clean.py   (after src/download.py)

Outputs
  prices_monthly.parquet      every WFP price row, one per month x market x commodity x pricetype,
                              price in BDT per kg / litre / piece, with an outlier flag
  division_prices.parquet     core-basket retail prices, median across markets, per legacy division x month
  national_prices.parquet     core-basket retail prices, mean of division medians, per month
  covariates_monthly.parquet  official CPI, exchange rate, world prices, rainfall, flood and Ramadan flags
  rain_division_monthly.parquet  rainfall and flood flag per division x month
  outputs/tables/cleaning_log.csv, outputs/tables/outliers.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, TAB = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs" / "tables"

# Unit -> (multiplier to reach the standard unit, standard unit)
UNIT = {"KG": (1, "kg"), "100 KG": (0.01, "kg"), "12 KG": (1 / 12, "kg"), "500 G": (2, "kg"),
        "L": (1, "L"), "1 piece": (1, "piece"), "10 pcs": (0.1, "piece"), "1 Roll": (1, "piece")}

# Core basket: short name -> WFP commodity. "long" items have division prices from 2006.
CORE = {
    "rice_coarse": ("Rice (coarse)", "long"),
    "atta": ("Wheat flour", "long"),
    "lentil_masur": ("Lentils (masur)", "long"),
    "palm_oil": ("Oil (palm)", "long"),
    "soybean_oil": ("Oil (soybean, fortified)", "short"),
    "sugar": ("Sugar", "short"),
    "egg": ("Eggs (brown)", "short"),
    "chicken_broiler": ("Meat (chicken, broiler)", "short"),
    "onion": ("Onions (imported, China)", "short"),
    "potato": ("Potatoes (Holland, white)", "short"),
    "chili_green": ("Chili (green)", "short"),
}

# Mymensingh (split from Dhaka in 2015) and Rangpur (split from Rajshahi in 2010) are folded back
# so that the 2006-2020 "X Division" markets and the 2020+ district markets line up.
LEGACY_DIV = {"Barisal": "Barishal", "Chittagong": "Chattogram", "Dhaka": "Dhaka", "Khulna": "Khulna",
              "Rajshahi": "Rajshahi", "Sylhet": "Sylhet", "Mymensingh": "Dhaka", "Rangpur": "Rajshahi"}
DIV_NAME = {"Barisal": "Barishal", "Chittagong": "Chattogram"}  # current official spelling

Z_CUT = 5.0  # robust z threshold for outliers
XS_CUT = 0.4  # cross-division log-deviation threshold (division-month dropped)
MAX_LINK = 3  # national chain links across gaps of up to this many months
log = []


def step(name, n_before, n_after, note):
    log.append({"step": name, "rows_before": n_before, "rows_after": n_after, "note": note})
    print(f"{name:32s} {n_before:>7} -> {n_after:>7}  {note}")


def prices():
    df = pd.read_csv(RAW / "wfp_food_prices_bgd.csv", skiprows=[1])  # skip HXL tag row
    n0 = len(df)
    step("load", n0, n0, "WFP HDX csv, retail and wholesale, BDT")
    df = df[df.currency == "BDT"].copy()
    df["date"] = pd.to_datetime(df.date).dt.to_period("M").dt.to_timestamp()
    mult = df.unit.map(lambda u: UNIT[u][0])
    df["unit_std"] = df.unit.map(lambda u: UNIT[u][1])
    df["price_bdt"] = df.price * mult
    df["usdprice_std"] = df.usdprice * mult
    df["fx_implied"] = df.price / df.usdprice
    step("standardise_units", n0, len(df), "100 KG, 12 KG -> per kg; 500 G -> per kg; 10 pcs -> per piece")
    # Two WFP labels for coarse rice at the Dhaka city market are kept separate from "Rice (coarse)".
    n1 = len(df)
    key = ["date", "market", "commodity", "pricetype", "unit_std"]
    df = (df.sort_values("priceflag")  # "actual" sorts before "aggregate"
            .groupby(key, as_index=False)
            .agg(division=("admin1", "first"), district=("admin2", "first"), market_id=("market_id", "first"),
                 lat=("latitude", "first"), lon=("longitude", "first"), category=("category", "first"),
                 unit_raw=("unit", "first"), priceflag=("priceflag", "first"),
                 price_bdt=("price_bdt", "mean"), usdprice=("usdprice_std", "mean"), fx_implied=("fx_implied", "median")))
    step("deduplicate", n1, len(df), "mean of rows sharing month x market x commodity x pricetype x unit")
    n2 = len(df)
    df = df[df.price_bdt > 0]
    step("drop_nonpositive", n2, len(df), "price <= 0")
    df["market_level"] = np.where(df.market.str.endswith(" Division"), "division", "market")
    df["division_legacy"] = df.division.map(LEGACY_DIV)
    df["division"] = df.division.replace(DIV_NAME)
    inv = {v[0]: k for k, v in CORE.items()}
    df["item"] = df.commodity.map(inv)

    # Outliers: log price minus the centred 7-month rolling median of the same commodity-market series,
    # scaled by 1.4826 x MAD of those deviations within the commodity (all markets), with the scale floored
    # at 0.05 log points so that sticky prices (tiny MAD) do not flag ordinary 10% moves. |z| > 5 is flagged.
    df = df.sort_values(["commodity", "pricetype", "market", "date"])
    lp = np.log(df.price_bdt)
    med = lp.groupby([df.commodity, df.pricetype, df.market]).transform(
        lambda s: s.rolling(7, center=True, min_periods=3).median())
    dev = lp - med
    mad = dev.groupby([df.commodity, df.pricetype]).transform(lambda s: (s - s.median()).abs().median())
    df["robust_z"] = (dev - dev.groupby([df.commodity, df.pricetype]).transform("median")) / np.maximum(1.4826 * mad, 0.05)
    df["outlier"] = df.robust_z.abs() > Z_CUT
    step("flag_outliers", len(df), len(df), f"{int(df.outlier.sum())} rows flagged (|robust z| > {Z_CUT}); kept, not dropped")
    df[df.outlier].to_csv(TAB / "outliers.csv", index=False)
    cols = ["date", "division", "division_legacy", "district", "market", "market_id", "market_level", "lat", "lon",
            "category", "commodity", "item", "unit_raw", "unit_std", "pricetype", "priceflag",
            "price_bdt", "usdprice", "fx_implied", "robust_z", "outlier"]
    df = df[cols].sort_values(["date", "market", "commodity"]).reset_index(drop=True)
    df.to_parquet(PROC / "prices_monthly.parquet", index=False)
    return df


def core_panels(df):
    c = df[(df.pricetype == "Retail") & df.item.notna() & ~df.outlier].copy()
    step("core_basket_retail", len(df), len(c), f"{c.item.nunique()} core items, retail, outliers removed")
    div = (c.groupby(["date", "division_legacy", "item"])
             .agg(price_bdt=("price_bdt", "median"), n_markets=("market", "nunique")).reset_index()
             .rename(columns={"division_legacy": "division"}))
    div["basket"] = div.item.map(lambda i: CORE[i][1])
    step("division_panel", len(c), len(div), "median across markets in each legacy division (6 divisions)")

    # Cross-sectional rule: a division-month more than XS_CUT log points from the median of all
    # divisions for that item and month is dropped (needs >= 3 divisions that month). The rolling-median
    # rule above cannot see a level shift that lasts a year, such as Khulna coarse rice in 2007.
    lp = np.log(div.price_bdt)
    div["xs_dev"] = lp - lp.groupby([div.date, div.item]).transform("median")
    div["xs_n"] = div.groupby(["date", "item"]).division.transform("nunique")
    far = (div.xs_dev.abs() > XS_CUT) & (div.xs_n >= 3)
    # If the flagged divisions are fewer than half of those reporting, only they are dropped. If half or
    # more are flagged (say a 2-2 split), there is no consensus price, so the whole item-month is dropped
    # and the national gap is later filled by interpolation like any other missing month.
    n_far = far.groupby([div.date, div.item]).transform("sum")
    bad_one = far & (n_far < div.xs_n / 2)
    bad_all = (n_far > 0) & (n_far >= div.xs_n / 2)
    bad = bad_one | bad_all
    rule = np.where(bad_one, f"cross_section_abs_log_dev_gt_{XS_CUT}", "cross_section_no_consensus")
    div.assign(rule=rule)[bad].to_csv(TAB / "outliers_cross_section.csv", index=False)
    n3 = len(div)
    div = div[~bad].drop(columns=["xs_dev", "xs_n"]).reset_index(drop=True)
    step("cross_section_outliers", n3, len(div),
         f"rule cross_section: dropped {int(bad_one.sum())} division-months more than {XS_CUT} log points from "
         f"the cross-division median, plus {int(bad_all.sum())} rows in item-months where half or more divisions "
         "were that far (no consensus); all listed in outliers_cross_section.csv")
    div.to_parquet(PROC / "division_prices.parquet", index=False)

    nat = (div.groupby(["date", "item"])
              .agg(price_mean_bdt=("price_bdt", "mean"), n_divisions=("division", "nunique"),
                   n_markets=("n_markets", "sum")).reset_index())
    nat = nat[nat.n_divisions >= 3]
    nat = nat.merge(matched_chain(div, nat), on=["date", "item"], how="left")
    nat["basket"] = nat.item.map(lambda i: CORE[i][1])
    nat.to_parquet(PROC / "national_prices.parquet", index=False)
    step("national_panel", len(div), len(nat),
         "matched-sample chain over divisions reporting in both months, level set to the plain mean in the "
         "latest 12 full-coverage months; months with >= 3 divisions")


def matched_chain(div, nat):
    """National price that ignores divisions entering or leaving.

    For each month t, the national change is the ratio of mean prices at t and at the previous national
    month (at most MAX_LINK months earlier), both means taken over the divisions observed in both months.
    When the same divisions report in both months, this equals the change in the plain mean. The chained
    log level is then shifted so that, over the latest 12 months where all divisions report, its mean
    equals the log of the plain mean of division medians. Index numbers only use ratios, so this choice
    sets BDT levels but does not change any index. A month with no matched division (or a gap longer
    than MAX_LINK) starts a new segment, anchored the same way on its own months.
    """
    rows = []
    for item, n in nat.groupby("item"):
        n = n.sort_values("date").reset_index(drop=True)
        w = div[div.item == item].pivot_table(index="date", columns="division", values="price_bdt")
        lw = np.log(w.loc[n.date])
        lev, seg_id, seg = [0.0], [0], 0
        for a, b in zip(n.date[:-1], n.date[1:]):
            both = lw.loc[[a, b]].dropna(axis=1).columns
            gap = (b.year - a.year) * 12 + b.month - a.month
            if len(both) == 0 or gap > MAX_LINK:
                seg += 1
                lev.append(0.0)
            else:
                lev.append(lev[-1] + np.log(np.exp(lw.loc[b, both]).mean() / np.exp(lw.loc[a, both]).mean()))
            seg_id.append(seg)
        n["lev"], n["seg"] = lev, seg_id
        full = n.n_divisions == n.n_divisions.max()
        for k, gs in n.groupby("seg"):
            ref = (gs[full[gs.index]] if full[gs.index].any() else gs).tail(12)
            off = (np.log(ref.price_mean_bdt) - ref.lev).mean()
            n.loc[gs.index, "price_bdt"] = np.exp(gs.lev + off)
        rows.append(n[["date", "item", "price_bdt"]])
    return pd.concat(rows)


def covariates(df):
    f = pd.read_csv(RAW / "faostat_cpi_bgd.csv")
    f["date"] = pd.to_datetime(f.Year.astype(str) + "-" + f.Months, format="%Y-%B")
    f = f.pivot_table(index="date", columns="Item", values="Value")
    f.columns = [{"Consumer Prices, Food Indices (2015 = 100)": "cpi_food_2015",
                  "Consumer Prices, General Indices (2015 = 100)": "cpi_general_2015",
                  "Food price inflation": "food_inflation_fao"}[c] for c in f.columns]
    cov = f
    fx = pd.read_csv(RAW / "imf_bdt_usd_monthly.csv", parse_dates=["date"]).set_index("date")
    cov = cov.join(fx, how="outer")
    imp = df[df.pricetype == "Retail"].groupby("date").fx_implied.median().rename("bdt_per_usd_wfp")
    cov = cov.join(imp, how="outer")
    wp = pd.read_csv(RAW / "world_prices_monthly.csv", parse_dates=["date"]).set_index("date")
    cov = cov.join(wp.add_prefix("world_"), how="outer")

    rain = pd.read_csv(RAW / "nasa_power_rain_monthly.csv", parse_dates=["date"])
    rain["month"] = rain.date.dt.month
    rain["p90"] = rain.groupby(["division", "month"]).precip_mm_month.transform(lambda s: s.quantile(0.9))
    clim = rain.groupby(["division", "month"]).precip_mm_month.transform("mean")
    rain["rain_anom_pct"] = 100 * (rain.precip_mm_month / clim - 1)
    rain["heavy_rain"] = rain.precip_mm_month > rain.p90
    # Major flood months, one row per event with its source (data/raw/flood_events.csv, see SOURCES.md).
    ev = pd.read_csv(RAW / "flood_events.csv")
    floods = {}
    for _, e in ev.iterrows():
        divs = None if e.divisions_affected == "national" else e.divisions_affected.split(";")
        for m in pd.date_range(e.start_month + "-01", e.end_month + "-01", freq="MS"):
            floods[m.strftime("%Y-%m")] = divs
    rain["flood_known"] = False
    for m, divs in floods.items():
        sel = rain.date == pd.Timestamp(m + "-01")
        if divs:
            sel &= rain.division.isin(divs)
        rain.loc[sel, "flood_known"] = True
    rain.drop(columns="month").to_parquet(PROC / "rain_division_monthly.parquet", index=False)
    nat = rain.groupby("date").agg(rain_mm_national=("precip_mm_month", "mean"),
                                   heavy_rain_divisions=("heavy_rain", "sum"),
                                   flood_known=("flood_known", "max"))
    cov = cov.join(nat, how="outer")

    ram = pd.read_csv(RAW / "ramadan_dates.csv", parse_dates=["ramadan_start", "ramadan_end"])
    days = pd.Series(0.0, index=pd.date_range("1999-01-01", "2027-12-31", freq="D"))
    for _, r in ram.iterrows():
        days[r.ramadan_start:r.ramadan_end] = 1
    rshare = days.resample("MS").mean().rename("ramadan_share")
    cov = cov.join(rshare, how="outer")
    cov["ramadan_month"] = cov.ramadan_share >= 0.5
    cov.index.name = "date"
    cov = cov[(cov.index >= "2000-01-01") & (cov.index <= "2026-12-01")]
    cov.reset_index().to_parquet(PROC / "covariates_monthly.parquet", index=False)
    step("covariates", 0, len(cov), "FAOSTAT CPI, IMF FX, WFP-implied FX, Pink Sheet, NASA rain, floods, Ramadan")


if __name__ == "__main__":
    PROC.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    df = prices()
    core_panels(df)
    covariates(df)
    pd.DataFrame(log).to_csv(TAB / "cleaning_log.csv", index=False)
