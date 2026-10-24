"""Food price index numbers for the core basket: Laspeyres, Paasche, Fisher and a chain-linked Laspeyres.

Run: python -I src/indices.py   (after src/clean.py). Writes data/processed/indices_*.parquet.

Weights
-------
WFP gives prices, not quantities. The base quantities q0 below are per-person daily intakes from
the BBS HIES 2022 Final Report, Table 5.2 (HIES 2016 column for the long basket, 2022 for the
short one), turned into monthly amounts. Three conversions are assumptions: oil density, egg
weight and the palm/soybean split.
docs/DESIGN.md lists them and a sensitivity check is in notebooks/01.

Paasche needs current quantities, which nobody publishes monthly. We assume households keep
their base-period budget shares (Cobb-Douglas demand: q_it = w_i0 * E_t / p_it). Then
    Laspeyres L_t = sum_i w_i0 * (p_it / p_i0)              (arithmetic mean of price relatives)
    Paasche   P_t = 1 / sum_i w_i0 * (p_i0 / p_it)          (harmonic mean of price relatives)
    Fisher    F_t = sqrt(L_t * P_t)
where w_i0 = p_i0 q_i0 / sum_j p_j0 q_j0 are base expenditure shares. L >= F >= P always holds,
and the L - P spread shows how much substitution away from items that got dearer could matter.

Chain-linked Laspeyres: the base shares are re-applied every January and each year's index is
linked to the previous December, so items that rose fast do not keep a growing weight.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

# Monthly quantity per person (kg, litre or piece), from BBS HIES Final Report (Dec 2023), Table 5.2
# "Average Per Capita Daily Food Intake (Grams) by Food Items and Locality", national columns.
# Long basket (2016 base) uses the HIES 2016 column; short basket (2025 base) uses HIES 2022.
# Conversion: kg/month = g/day * 30.4 / 1000. Oil: litres = kg / 0.92 (density of vegetable oil).
# Eggs: pieces = grams / 50 (assumed edible weight of one egg). Documented in data/raw/SOURCES.md.
G2KG = 30.4 / 1000
OIL_DENSITY = 0.92
EGG_G = 50.0
Q_LONG = {"rice_coarse": 367.2 * G2KG,                   # Rice, 2016
          "atta": 19.8 * G2KG,                          # Wheat, 2016 (all wheat taken as atta)
          "lentil_masur": 9.8 * G2KG,                   # Masoor, 2016
          "palm_oil": 26.8 * G2KG / OIL_DENSITY}        # Edible oils total, 2016 (palm stands in for all loose oil)
_OIL22 = 30.85 * G2KG / OIL_DENSITY                     # Edible oils total, 2022
Q_SHORT = {"rice_coarse": 328.92 * G2KG,                # Rice, 2022
           "atta": 22.92 * G2KG,                        # Wheat, 2022
           "lentil_masur": 11.88 * G2KG,                # Masoor, 2022
           "palm_oil": 0.5 * _OIL22,                    # assumption: HIES does not split palm from soybean, 50/50
           "soybean_oil": 0.5 * _OIL22,
           "sugar": 15.12 * G2KG,                       # Sugar (excl. gur), 2022
           "egg": 12.73 / EGG_G * 30.4,                 # Eggs, 2022, pieces
           "chicken_broiler": 26.17 * G2KG,             # Chicken/Duck, 2022 (all taken as broiler)
           "onion": 30.16 * G2KG,                       # Onion, 2022
           "potato": 69.70 * G2KG,                      # Potato, 2022
           "chili_green": 3.57 * G2KG}                  # Chillies, 2022 (green and dry not split)
Q_SOURCE = {"rice_coarse": "HIES Table 5.2: Rice", "atta": "HIES Table 5.2: Wheat",
            "lentil_masur": "HIES Table 5.2: Masoor", "palm_oil": "HIES Table 5.2: Edible oils / 0.92 kg/L",
            "soybean_oil": "HIES 2022 Table 5.2: Edible oils / 0.92 kg/L; 50/50 palm-soybean split assumed",
            "sugar": "HIES 2022 Table 5.2: Sugar", "egg": "HIES 2022 Table 5.2: Eggs / 50 g per egg (assumed)",
            "chicken_broiler": "HIES 2022 Table 5.2: Chicken/Duck", "onion": "HIES 2022 Table 5.2: Onion",
            "potato": "HIES 2022 Table 5.2: Potato", "chili_green": "HIES 2022 Table 5.2: Chillies"}
BASE_LONG = ("2016-01-01", "2016-12-01")   # HIES 2016 year
BASE_SHORT = ("2025-01-01", "2025-12-01")  # first full year of the wide basket
MAX_GAP = 3  # months of missing data filled by log-linear interpolation


def price_matrix(prices, items, start=None, end=None):
    """Wide month x item table; interior gaps up to MAX_GAP months filled in logs."""
    p = prices[prices.item.isin(items)].pivot_table(index="date", columns="item", values="price_bdt")
    idx = pd.date_range(p.index.min(), p.index.max(), freq="MS")
    p = p.reindex(idx)
    p = np.exp(np.log(p).interpolate(limit=MAX_GAP, limit_area="inside"))
    p = p.loc[start:end, list(items)]
    p.index.name = "date"
    return p


def shares(p0, q0):
    v = pd.Series({k: p0[k] * q for k, q in q0.items()})
    return v / v.sum()


def lpf(p, q0, base):
    """Laspeyres, Paasche, Fisher (base = 100) from a month x item price table."""
    p0 = p.loc[base[0]:base[1]].mean()
    w = shares(p0, q0)
    rel = p[w.index] / p0[w.index]
    ok = rel.notna().all(axis=1)
    L = (rel * w).sum(axis=1).where(ok) * 100
    P = (1 / (w / rel).sum(axis=1)).where(ok) * 100
    out = pd.DataFrame({"laspeyres": L, "paasche": P})
    out["fisher"] = np.sqrt(out.laspeyres * out.paasche)
    out["chain_laspeyres"] = chain(rel, w, ok)
    # rebase the chain index so its base-year mean is 100 like the others
    out["chain_laspeyres"] *= 100 / out.chain_laspeyres.loc[base[0]:base[1]].mean()
    return out, w, p0


def chain(rel, w, ok):
    """Annual chain Laspeyres: shares reset each January, linked through December."""
    lev = pd.Series(np.nan, index=rel.index)
    prev_dec, link_level = None, 1.0
    for t in rel.index:
        if not ok[t]:
            continue
        if prev_dec is None:
            prev_dec, link_level = t, float((rel.loc[t] * w).sum())
            lev[t] = link_level
            continue
        anchor = prev_dec
        lev[t] = link_level * float((w * rel.loc[t] / rel.loc[anchor]).sum())
        if t.month == 12:
            prev_dec, link_level = t, lev[t]
    return lev


def yoy(s):
    return 100 * (s / s.shift(12) - 1)


def build():
    nat = pd.read_parquet(PROC / "national_prices.parquet")
    div = pd.read_parquet(PROC / "division_prices.parquet")
    p_long = price_matrix(nat, Q_LONG, "2006-01-01")
    long_idx, w_long, p0_long = lpf(p_long, Q_LONG, BASE_LONG)
    p_short = price_matrix(nat, Q_SHORT, "2024-09-01")
    short_idx, w_short, p0_short = lpf(p_short, Q_SHORT, BASE_SHORT)

    rows = []
    for d, g in div.groupby("division"):
        pdv = price_matrix(g, Q_LONG, "2006-01-01")
        # national base prices, so a division's level also shows its price level relative to the country
        rel = pdv / p0_long
        ok = rel.notna().all(axis=1)
        L = (rel * w_long).sum(axis=1).where(ok) * 100
        rows.append(pd.DataFrame({"date": L.index, "division": d, "laspeyres_natbase": L.values}))
    div_idx = pd.concat(rows)
    own = div_idx.groupby("division").apply(
        lambda g: g.set_index("date").laspeyres_natbase
        / g.set_index("date").laspeyres_natbase.loc[BASE_LONG[0]:BASE_LONG[1]].mean() * 100,
        include_groups=False)
    div_idx = div_idx.merge(own.rename("laspeyres_ownbase").reset_index(), on=["division", "date"])

    cov = pd.read_parquet(PROC / "covariates_monthly.parquet").set_index("date")
    fao = cov[["cpi_food_2015", "cpi_general_2015", "food_inflation_fao"]].copy()
    fao["cpi_food_2016"] = fao.cpi_food_2015 / fao.cpi_food_2015.loc["2016"].mean() * 100
    fao["cpi_general_2016"] = fao.cpi_general_2015 / fao.cpi_general_2015.loc["2016"].mean() * 100

    long_idx = long_idx.join(fao, how="left")
    for c in ["laspeyres", "paasche", "fisher", "chain_laspeyres", "cpi_food_2016", "cpi_general_2016"]:
        long_idx[f"{c}_yoy"] = yoy(long_idx[c])
    short_idx = short_idx.join(fao, how="left")

    long_idx.reset_index().to_parquet(PROC / "indices_long.parquet", index=False)
    short_idx.reset_index().to_parquet(PROC / "indices_short.parquet", index=False)
    div_idx.to_parquet(PROC / "indices_division.parquet", index=False)
    wt = pd.concat([
        pd.DataFrame({"basket": "long", "item": w_long.index, "q0_per_person_month": [Q_LONG[i] for i in w_long.index],
                      "p0_bdt": p0_long[w_long.index].values, "share": w_long.values,
                      "source": ["BBS HIES 2016 (Table 5.2 of HIES 2022 Final Report): " + Q_SOURCE[i].split(": ")[1] for i in w_long.index]}),
        pd.DataFrame({"basket": "short", "item": w_short.index, "q0_per_person_month": [Q_SHORT[i] for i in w_short.index],
                      "p0_bdt": p0_short[w_short.index].values, "share": w_short.values,
                      "source": ["BBS HIES 2022 Final Report " + Q_SOURCE[i].replace("HIES 2022 ", "").replace("HIES ", "") for i in w_short.index]})])
    wt.to_csv(ROOT / "outputs" / "tables" / "index_weights.csv", index=False)
    return long_idx, short_idx, div_idx, wt


if __name__ == "__main__":
    L, S, D, W = build()
    print(W.round(3).to_string())
    print(L.dropna(subset=["laspeyres"]).iloc[[0, -1]].round(1).T)
    print(S.dropna(subset=["laspeyres"]).iloc[[0, -1]].round(1).T)
