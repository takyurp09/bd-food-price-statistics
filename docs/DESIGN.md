# Design: BUS173 Applied Statistics on Bangladesh food prices

This file is for whoever builds notebooks 02 to 06. It lists the tables that exist after `src/clean.py` and `src/indices.py`, then the planned analyses, one per BUS173 topic, with the exact variables to use.

## 1. Data after cleaning (`data/processed/`)

| Table | Grain | Columns | Coverage |
|---|---|---|---|
| `prices_monthly.parquet` | month x market x commodity x pricetype | date (month start), division (current name), division_legacy (6 old divisions), district, market, market_id, market_level ("division" for the pre-2020 "X Division" series, else "market"), lat, lon, category, commodity, item (short name for the 11 core items, else null), unit_raw, unit_std (kg, L, piece), pricetype (Retail, Wholesale), priceflag, price_bdt, usdprice, fx_implied, robust_z, outlier | Jul 1998 to Aug 2026, 34,467 rows, 73 commodities, 110 markets |
| `division_prices.parquet` | month x legacy division x core item | date, division, item, price_bdt (median across markets, outliers removed), n_markets, basket ("long" or "short") | Long items from 2006, short items from Feb 2024. Division-months more than 0.4 log points from the cross-division median are dropped (see below) |
| `national_prices.parquet` | month x core item | date, item, price_bdt (matched-sample chain, see below), price_mean_bdt (plain mean of division medians), n_divisions, n_markets, basket | as above; months with fewer than 3 divisions are dropped |
| `covariates_monthly.parquet` | month | cpi_food_2015, cpi_general_2015, food_inflation_fao, bdt_per_usd (IMF), bdt_per_usd_wfp, world_rice_thai5, world_wheat_us_hrw, world_palm_oil, world_soybean_oil, world_sugar_world, world_crude_oil_avg, world_wb_food_index, rain_mm_national, heavy_rain_divisions, flood_known, ramadan_share, ramadan_month | Jan 2000 to Dec 2026 (CPI to Jun 2026, FX to Aug 2026, world prices and rain to Dec 2025) |
| `rain_division_monthly.parquet` | month x division (8) | division, date, precip_mm_day, precip_mm_month, p90, rain_anom_pct, heavy_rain, flood_known | Jan 2000 to Dec 2025 |
| `indices_long.parquet` | month | laspeyres, paasche, fisher, chain_laspeyres (2016 = 100), FAOSTAT CPI columns, *_yoy | Sep 2006 to Jul 2026 |
| `indices_short.parquet` | month | same formulas for the 11-item basket (2025 = 100) | Sep 2024 to Mar 2026 |
| `indices_division.parquet` | month x legacy division | laspeyres_natbase, laspeyres_ownbase | 2006 to 2026 |

Core items: `rice_coarse`, `atta` (wheat flour), `lentil_masur`, `palm_oil` (the long basket, monthly since 2006 in six divisions), and `soybean_oil`, `sugar`, `egg`, `chicken_broiler`, `onion` (imported, China), `potato`, `chili_green` (only from 2024, but in 30 to 90 district markets).

Things to know:

- WFP changed design in mid-2020, from one series per division to district markets. Any test that compares before and after 2020 must allow for that break.
- Wholesale prices exist only for the Dhaka city market (rice, wheat, wheat flour; Jul 1998 to May 2021; 867 rows), so retail vs wholesale margins can only be studied there.
- Index weights are per-person quantities from BBS HIES Table 5.2 (2016 for the long basket, 2022 for the short one), with oil density, egg weight and the palm/soybean split assumed (`src/indices.py`, `outputs/tables/index_weights.csv`). Notebook 01 shows that the main results barely move when they are perturbed by +/-50%.
- Outliers are flagged, not dropped, in `prices_monthly`. Drop `outlier == True` for tests unless the test is about extremes.
- **Cross-division outlier rule** (`clean.core_panels`). The rolling-median rule cannot catch an error that lasts a year, such as Khulna coarse rice at 32 to 45 BDT/kg in February to December 2007 while the other divisions were at 18 to 26. A division-month is dropped when its log price is more than 0.4 from the median across divisions for that item and month (at least 3 divisions reporting). If half or more of the divisions are that far out, there is no consensus price and the whole item-month is dropped. The rule drops 29 rows: the 11 Khulna rice months, 11 single potato and onion prices in 2025-2026, and 7 rows in two split potato months. All are listed in `outputs/tables/outliers_cross_section.csv` with the rule name. Normal regional gaps (at most about 7% to 8%) are well inside the cut.
- **National price: matched-sample chain** (`clean.matched_chain`). The plain mean of division medians jumps when a division enters or leaves (rice has 67 months with fewer than six divisions). The national change from one month to the next is therefore the ratio of mean prices over the divisions that report in both months (gaps up to 3 months are bridged). When the same divisions report in both months this equals the change in the plain mean. The chained level is set equal to the plain mean over the latest 12 months with full coverage, so recent BDT prices match the simple average; index numbers depend only on ratios and are unaffected by that choice. A balanced panel was the alternative, but no long-basket item has all six divisions in every month, so it would have meant dropping divisions or months. The cost of the chain is that a division's price change while it is absent is lost. Notebook 01 (fig02b) compares the two series for rice: monthly changes correlate at about 0.96, levels differ by up to 6.7%, and the July 2026 Laspeyres staple index (2016 = 100) falls from 172.6 to 164.5.

## 2. Planned analyses

### 02 Estimation and hypothesis tests

Data: `prices_monthly` (retail), `division_prices`, `covariates_monthly`.

1. **Confidence intervals for mean prices.** 95% t-intervals for the mean retail price of each core item across markets in a given month (for example Jul 2026); bootstrap intervals for the median as a check.
2. **Ramadan effect.** H0: the mean month-on-month log change of a price is the same in Ramadan months and other months. Variables: `d log price_bdt` per item per division from `division_prices`, `ramadan_month`. Welch two-sample t-test and Mann-Whitney. Items likely to react: lentils, sugar, soybean oil, onion, chicken, egg. Bonferroni or Holm across items.
3. **Dhaka vs other divisions.** Paired t-test on the monthly price gap, Dhaka minus each other division, for the long-basket items (`division_prices`).
4. **Before and after the 2022 to 2023 taka depreciation.** Two-sample tests on monthly inflation of import-heavy items (palm oil, soybean oil, lentils, sugar) before and after Jun 2022, with `bdt_per_usd` showing the break.
5. **Variance test.** F-test / Levene test that staple y/y inflation (`indices_long.fisher_yoy`) has a larger variance than official food inflation (`cpi_food_2016_yoy`).

### 03 Contingency tables and goodness of fit

1. **Price direction by season.** Classify each division x item x month as up / flat / down (more than +/-2%). Cross-tabulate against season (pre-monsoon Mar-May, monsoon Jun-Sep, post-monsoon Oct-Nov, winter Dec-Feb) and against `ramadan_month`. Chi-square test of independence, Cramer's V, standardised residuals.
2. **Price direction vs heavy rain.** Same direction variable against `heavy_rain` from `rain_division_monthly` (division names match after mapping Rangpur and Mymensingh to their legacy divisions or using current `division` in `prices_monthly`).
3. **Outlier counts by division.** Chi-square test that `outlier` flags are spread across divisions in proportion to rows.
4. **Goodness of fit.** (a) Benford first-digit test on all retail `price_bdt`. (b) Normality of monthly log returns per item: chi-square GOF on binned returns, Jarque-Bera, Q-Q plots. (c) Uniformity of the month in which each item's annual peak falls.

### 04 Correlation and regression

1. **Correlation matrix** of monthly log changes across the four staples and world prices (`world_rice_thai5`, `world_wheat_us_hrw`, `world_palm_oil`) and `bdt_per_usd`. Pearson and Spearman with significance.
2. **Simple regression.** Log domestic palm oil price on log (world palm oil price x `bdt_per_usd`): pass-through elasticity. Same for atta on wheat and rice on Thai rice (expect weaker pass-through for rice, which is mostly home-grown).
3. **Multiple regression of monthly inflation.** `d log national price` on `d log world price` (lags 0 to 3), `d log bdt_per_usd`, `ramadan_share`, `heavy_rain_divisions` or `flood_known`, and month dummies, Newey-West errors. Check VIF, residual plots, Durbin-Watson.
4. **Cross-section regression (2024 to 2026 markets).** Market price level of each item on distance to Dhaka (from `lat`, `lon`), division dummies and Cox's Bazar camp markets (Ukhia, Teknaf, Bhashan Char) dummy.

### 05 Time series

1. **Decomposition.** STL on log national rice and onion prices; seasonal factors by month.
2. **Stationarity.** ADF and KPSS on log levels and differences of the staple index and food CPI.
3. **Forecasting.** Seasonal naive, ETS and SARIMA for the long-basket Fisher index and for rice; rolling-origin evaluation over the last 24 months (MAPE, MASE).
4. **Cointegration.** Engle-Granger between log domestic palm oil and log world palm oil in BDT; error-correction model for the speed of adjustment.
5. **Granger causality.** Does staple inflation lead food CPI inflation? (Notebook 01 finds the highest correlation at a 1-month lead, r = 0.44.)

### 06 Bayesian decision theory

A business question: a Dhaka wholesaler or a government buyer (for example the TCB open-market sales) must decide each month whether to buy and store rice or lentils now or buy next month.

1. **States of nature:** next month's price goes up (> +3%), stays, or goes down (< -3%). Priors from the historical frequency of each state by calendar month (`national_prices`).
2. **Evidence:** a signal such as the world price rising last month, a Ramadan month ahead, or a heavy-rain month. Likelihoods P(signal | state) from the data; posteriors by Bayes' rule.
3. **Payoff table:** cost saved per tonne by buying early minus storage cost (assumed BDT per kg per month, state the source or assumption).
4. **Decision rules:** maximum expected monetary value with prior vs posterior, expected value of perfect information (EVPI) and of sample information (EVSI). A sensitivity chart over storage cost.

## 3. Repo layout to keep

Notebooks are written by `src/build_notebook_0X.py` and executed with nbconvert by `scripts/run_all.py`. Figures go to `outputs/figures/figNN_name.png` with a source note via `plot_utils.save`. Each notebook writes its README numbers to `outputs/tables/key_facts_<topic>.csv`.
