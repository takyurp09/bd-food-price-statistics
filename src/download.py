"""Download every raw input into data/raw/ and write small tidy CSVs next to them.

Run: python -I src/download.py   (about 1 minute; needs internet)

Sources (details, licences and access date in data/raw/SOURCES.md):
  a. WFP food prices for Bangladesh (HDX)          -> wfp_food_prices_bgd.csv, wfp_markets_bgd.csv
  b. FAOSTAT Consumer Price Indices (Bangladesh)    -> faostat_cpi_bgd.csv
  c. IMF exchange rates (BDT per USD, monthly)      -> imf_bdt_usd_monthly.csv
     fallback: rate implied by WFP price/usdprice    (built in src/clean.py)
  d. NASA POWER monthly rainfall at 8 division HQs  -> nasa_power_rain_monthly.csv
  e. World Bank Pink Sheet monthly prices           -> CMO-Historical-Data-Monthly.xlsx, world_prices_monthly.csv
  f. Ramadan dates (Umm al-Qura via hijridate)      -> ramadan_dates.csv
Each step is wrapped so one failed source does not stop the others.
"""
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (research; bd-food-price-statistics)"}

HDX_API = "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-bangladesh"
FAOSTAT_ZIP = "https://bulks-faostat.fao.org/production/ConsumerPriceIndices_E_All_Data_(Normalized).zip"
IMF_ER = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,ER/BGD.XDC_USD.PA_RT.M"
POWER = ("https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=PRECTOTCORR"
         "&community=AG&longitude={lon}&latitude={lat}&start=2000&end=2025&format=JSON")
PINK = ("https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/"
        "related/CMO-Historical-Data-Monthly.xlsx")

# Division headquarters (approximate city-centre coordinates).
DIV_HQ = {
    "Dhaka": (23.81, 90.41), "Chattogram": (22.36, 91.78), "Rajshahi": (24.37, 88.60),
    "Khulna": (22.85, 89.54), "Barishal": (22.70, 90.35), "Sylhet": (24.89, 91.87),
    "Rangpur": (25.74, 89.25), "Mymensingh": (24.75, 90.41),
}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=180, **kw)
    r.raise_for_status()
    return r


def wfp():
    meta = get(HDX_API).json()["result"]
    for res in meta["resources"]:
        name = res["url"].rsplit("/", 1)[-1]
        if name.endswith(".csv"):
            (RAW / name).write_bytes(get(res["url"]).content)
            print("  saved", name)
    df = pd.read_csv(RAW / "wfp_food_prices_bgd.csv", skiprows=[1])  # row 2 is an HXL tag row
    df["date"] = pd.to_datetime(df["date"])
    cov = (df.groupby(["commodity", "market", "pricetype", "unit"])
             .agg(first=("date", "min"), last=("date", "max"), n_obs=("price", "size"),
                  n_months=("date", lambda s: s.dt.to_period("M").nunique()))
             .reset_index().sort_values(["commodity", "market"]))
    cov.to_csv(ROOT / "outputs" / "tables" / "wfp_coverage.csv", index=False)
    print(f"  WFP rows {len(df)}, {df.commodity.nunique()} commodities, {df.market.nunique()} markets, "
          f"{df.date.min().date()} to {df.date.max().date()}")


def faostat():
    z = zipfile.ZipFile(io.BytesIO(get(FAOSTAT_ZIP).content))
    name = [n for n in z.namelist() if n.endswith(".csv") and "All_Data" in n][0]
    df = pd.read_csv(z.open(name), encoding="latin-1", low_memory=False)
    bd = df[df["Area"] == "Bangladesh"].copy()
    bd.to_csv(RAW / "faostat_cpi_bgd.csv", index=False)
    print("  FAOSTAT items:", sorted(bd["Item"].unique()), "rows", len(bd))


def imf_fx():
    xml = get(IMF_ER).text
    (RAW / "imf_er_bgd.xml").write_text(xml)
    obs = re.findall(r'TIME_PERIOD="(\d{4})-M(\d{2})" OBS_VALUE="([0-9.Ee+-]+)"', xml)
    if not obs:  # attribute order can differ
        obs = [(y, m, v) for v, y, m in re.findall(r'OBS_VALUE="([0-9.Ee+-]+)"[^>]*TIME_PERIOD="(\d{4})-M(\d{2})"', xml)]
    fx = pd.DataFrame(obs, columns=["y", "m", "bdt_per_usd"])
    fx["date"] = pd.to_datetime(fx.y + "-" + fx.m + "-01")
    fx["bdt_per_usd"] = fx.bdt_per_usd.astype(float)
    fx[["date", "bdt_per_usd"]].sort_values("date").to_csv(RAW / "imf_bdt_usd_monthly.csv", index=False)
    print(f"  IMF FX {len(fx)} months, {fx.date.min().date()} to {fx.date.max().date()}")


def rain():
    rows = []
    for div, (lat, lon) in DIV_HQ.items():
        js = get(POWER.format(lat=lat, lon=lon)).json()
        (RAW / f"nasa_power_{div.lower()}.json").write_text(json.dumps(js))
        for k, v in js["properties"]["parameter"]["PRECTOTCORR"].items():
            if k[4:] == "13" or v < 0:  # 13 = annual mean; -999 = missing
                continue
            rows.append({"division": div, "date": pd.Timestamp(f"{k[:4]}-{k[4:]}-01"), "precip_mm_day": v})
    df = pd.DataFrame(rows)
    df["precip_mm_month"] = df.precip_mm_day * df.date.dt.days_in_month
    df.to_csv(RAW / "nasa_power_rain_monthly.csv", index=False)
    print(f"  NASA POWER {len(df)} division-months, {df.date.min().date()} to {df.date.max().date()}")


def pink():
    (RAW / "CMO-Historical-Data-Monthly.xlsx").write_bytes(get(PINK).content)
    x = pd.read_excel(RAW / "CMO-Historical-Data-Monthly.xlsx", sheet_name="Monthly Prices", header=None)
    hdr = x.index[x.iloc[:, 0].astype(str).str.strip().eq("")].min()
    names = x.iloc[4].astype(str).str.strip()  # row 5 holds the series names
    data = x.iloc[6:].copy()
    data.columns = names
    data = data.rename(columns={names.iloc[0]: "period"})
    keep = {"Rice, Thai 5% ": "rice_thai5", "Rice, Thai 5%": "rice_thai5",
            "Wheat, US HRW": "wheat_us_hrw", "Soybean oil": "soybean_oil", "Palm oil": "palm_oil",
            "Sugar, world": "sugar_world", "Crude oil, average": "crude_oil_avg"}
    cols = [c for c in data.columns if c in keep]
    out = data[["period"] + cols].rename(columns=keep)
    out = out[out.period.astype(str).str.match(r"^\d{4}M\d{2}$")]
    out["date"] = pd.to_datetime(out.period.str.replace("M", "-") + "-01")
    out = out.drop(columns="period").set_index("date").apply(pd.to_numeric, errors="coerce").reset_index()
    # Food price index from the "Monthly Indices" sheet (2010 = 100).
    xi = pd.read_excel(RAW / "CMO-Historical-Data-Monthly.xlsx", sheet_name="Monthly Indices", header=None)
    lab = xi.iloc[:9].astype(str).apply(lambda c: " ".join(c), axis=0)
    food_col = [i for i, s in enumerate(lab) if re.search(r"\bFood\b", s)][0]
    idx = xi.iloc[9:, [0, food_col]].copy()
    idx.columns = ["period", "wb_food_index"]
    idx = idx[idx.period.astype(str).str.match(r"^\d{4}M\d{2}$")]
    idx["date"] = pd.to_datetime(idx.period.str.replace("M", "-") + "-01")
    out = out.merge(idx[["date", "wb_food_index"]].astype({"wb_food_index": float}), on="date", how="left")
    out.to_csv(RAW / "world_prices_monthly.csv", index=False)
    print(f"  Pink Sheet {list(out.columns)}, {out.date.min().date()} to {out.date.max().date()}")


def ramadan():
    from hijridate import Hijri
    rows = []
    for hy in range(1420, 1449):
        start = Hijri(hy, 9, 1).to_gregorian()
        end = Hijri(hy, 10, 1).to_gregorian()  # Eid al-Fitr; Ramadan ends the day before
        rows.append({"hijri_year": hy, "ramadan_start": start.isoformat(),
                     "ramadan_end": pd.Timestamp(end.isoformat()) - pd.Timedelta(days=1),
                     "eid_al_fitr": end.isoformat()})
    df = pd.DataFrame(rows)
    df["ramadan_end"] = df.ramadan_end.dt.date
    df.to_csv(RAW / "ramadan_dates.csv", index=False)
    print(f"  Ramadan {len(df)} years, {df.ramadan_start.iloc[0]} to {df.ramadan_start.iloc[-1]}")


if __name__ == "__main__":
    failed = []
    for f in [wfp, faostat, imf_fx, rain, pink, ramadan]:
        print("==", f.__name__)
        try:
            f()
        except Exception as e:  # keep going; report at the end
            print("  FAILED:", repr(e)[:300])
            failed.append(f.__name__)
    print("failed:", failed or "none")
    sys.exit(1 if failed else 0)
