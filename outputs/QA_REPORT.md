# QA report

Review date: 24 October 2026. Scope: `src/`, `scripts/run_all.py`, the six notebooks, `outputs/tables`, `outputs/figures`, `docs/DESIGN.md`, `data/raw/SOURCES.md`. The dashboard files (`site/`, `scripts/build_site_data.py`, `assets/`) were not reviewed.

## Reproducibility

`python -I scripts/run_all.py` (conda env `crop_env`) runs clean.py, indices.py and the six builder + notebook pairs in order, with no downloads. It finished without errors twice, in 104 s each time. All 46 tables in `outputs/tables` came out byte-identical between the two runs. Before the fix below, `key_facts_tests.csv` changed its row order from run to run; the contents were the same.

Repo size is 17 MB. No file is over 10 MB.

## Checks that passed

- **Index formulas.** Recomputed June 2023 by hand from `national_prices.parquet` and the HIES quantities: Laspeyres 159.47 (the same value whether computed from shares or from quantities), Paasche 155.01, Fisher 157.22. All three match `indices_long.parquet` to machine precision. The chain index's June 2023 / December 2022 ratio equals the share-weighted mean of price relatives to December 2022 (0.9873), so the December link works as described. Note that the chain re-applies the same 2016 expenditure shares each year rather than price-updated shares. That fits the Cobb-Douglas assumption already used for Paasche, and the docstring says so.
- **HIES conversions.** g/day x 30.4 / 1000 to kg/month, oil divided by 0.92 kg/L, eggs at 50 g. The code matches the table in SOURCES.md, and the long-basket shares (rice 0.746, oil 0.139, lentils 0.071, atta 0.043) follow from them.
- **Division mapping.** In `prices_monthly`, Mymensingh maps only to Dhaka and Rangpur only to Rajshahi, and every other division maps to itself. Rain stays on the eight current divisions. The heavy-rain test matches legacy Dhaka and Rajshahi prices to rain at Dhaka and Rajshahi only, which is a reasonable choice.
- **WFP 2020 design change.** The national log changes show no jump at July 2020, and all six divisions report through the switch. The regressions carry a July 2020 dummy.
- **Tests.** The Dhaka gaps are paired (a HAC mean of the gap series) and Holm runs across the 20 pairs. The before/after-2022 comparisons are Welch tests plus a moving-block bootstrap. Newey-West lags follow floor(4(n/100)^(2/9)). Holm is applied within sections, and the notebook text says so.
- **Contingency tables.** Expected counts are reported, Fisher exact runs next to chi-square, odds-ratio CIs use Woolf with a 0.5 correction for zero cells, and the circular-shift permutation keeps the autocorrelation of both series.
- **Regression.** Lags 0 to 3 with HAC errors. The long-run pass-through is a linear sum of coefficients with its SE from the HAC covariance, so no delta method is needed. I recomputed the Chow F as an F-test on a fully interacted model and got the same values (for example palm oil F = 0.339, df 23 and 171). The F values all sit well below 1 because the pre-2022 sample has the heavier tails, and the notebook already warns that power is low. In the out-of-sample check, every coefficient comes from 2006-2019 data only.
- **Time series.** ADF and KPSS are read jointly. The SARIMA order is fixed in code, and the model-selection rule (lowest MASE at horizons 1-6) is stated before the backtest. MASE scales by each training window's own seasonal-naive error.
- **Bayes.** The spike threshold (4.22%), likelihoods and price paths come from 2007-2019 only. The arithmetic checks out: carry is 11.86/12 + 0.5 = 1.49% a month; break-even is 18,564 / (36,930 + 18,564) = 0.335; EVPI is about 0.106 x 36,930 = 3,913 BDT; the Beta posteriors are 17/153 = 0.111 and 31/225 = 0.138. The 9% lending-rate cap (2020 to mid-2023) is stated as a caveat.
- **Numbers in text.** Spot-checked against `key_facts_*`: the 2-month lead r = 0.44 in DESIGN.md, 14 of 20 Dhaka pairs, 69/152 and 62 after Holm in notebook 02, 14/38 and 12 in notebook 03, 14 of 72 test spikes and the 12.5% flip rate in notebook 06. All match.

## Fixes made

| Severity | Issue | Fix |
|---|---|---|
| Medium | No LICENSE file | Added `LICENSE` (MIT, Muhammad Taky Tahmid), with a line saying the data keep their own licences |
| Medium | SOURCES.md had a licence column but no project licence, no note on the flood list or the quoted lending rate | Added a "Licences" section to `data/raw/SOURCES.md` |
| Low | `key_facts_tests.csv` row order depended on which notebook ran last | `tests_stats.write_facts` now sorts by notebook |
| Low | fig09: black labels on the darkest cells (Sylhet atta -7.1) were unreadable | Labels switch to white on dark cells (`build_notebook_02.py`) |
| Low | fig20: the source note overlapped the rotated tick labels | Note moved below the labels (`build_notebook_04.py`) |
| Low | `requirements.txt` lacked a version note for ipykernel and did not list nbclient | Added both, with crop_env versions |

None of these changed a headline number. Both figures were regenerated by a full rerun.

## Remaining issues

**High: Khulna coarse rice, January to December 2007.** The Khulna Division series reads 32 to 45 BDT/kg in February to December 2007, while the other five divisions read 18 to 26 BDT/kg. It then drops back to 28 in January 2008, in line with everyone else. This looks like a different variety or a recording error. The outlier rule compares each point with its own 7-month rolling median, so it cannot catch a level shift that lasts a year (all robust z values are under 1). Because the national price is a mean over 4 to 6 division medians in 2007, the error raises national rice by roughly 3 to 4 BDT (about 15%) for most of 2007. That shifts the start of the long index, creates spurious rice spike months in February 2007 and January 2008, and puts the odd 2007 hump on Khulna's line in fig05. Suggested fix: add a cross-sectional flag in `clean.core_panels`, dropping a division-month whose median is more than 40% (in logs) away from the median across divisions for that item and month. Then rerun everything and refresh the hard-coded numbers in the notebook markdown, since the thresholds, spike counts and regression samples that start in 2006-2007 will all move. I left this for the author because it changes results in all six notebooks.

**Medium: composition changes in the national mean.** The national price is a plain mean of division medians, and division count is allowed to drop to 3 (rice has 56 months with fewer than 6 divisions). A month-on-month change can then partly reflect a division entering or leaving. A fixed-panel chain (the change computed over divisions present in both months) or division fixed effects would remove this.

**Low:**
- The SARIMA order and the ETS form were picked after looking at full-sample ACF/PACF plots. The backtest is otherwise clean. A sentence in notebook 05 saying so would answer the obvious examiner question.
- Gap filling (up to 3 months, log-linear) uses the observation after the gap. That is fine for the indices but a mild look-ahead for the notebook 05 and 06 backtests. Only 3 to 5 months are filled per series.
- The notebook 03 spike threshold is the 90th percentile over 2007-2026. That is fine for a descriptive test, but it differs from the training-only threshold in notebook 06 (4.74% vs 4.22% for palm oil). The text should say which is which.
- Notebook 06 uses a single June 2026 financing rate for the whole backtest. The cap is mentioned, but the backtest is not rerun at 9% for 2020-2023.
- fig42: the "breakeven 0.33" label sits on the forward-buy line. fig12: the legend overlaps the 2008 lines. Both are readable.
- FAOSTAT is given as CC BY 4.0, which matches FAO's statistical database terms. The IMF entry says "free reuse with attribution", which is a summary; the IMF's own terms page should be linked.

## Fixes after review

All the remaining issues above were fixed on 24 October 2026. `scripts/run_all.py` was rerun end to end (104 s, no errors), the typed numbers in the builders, `docs/DESIGN.md` and `README.md` were updated to the new `key_facts_*`, the notebooks were re-executed, and `scripts/build_site_data.py` was run to refresh `site/data/` (its own check reports prior 0.099, posterior 0.345, breakeven 0.329, EVPI 3,705, EVSI 170).

**High: Khulna 2007.** `clean.core_panels` has a second outlier rule. A division-month is dropped when its log price is more than 0.4 from the median across divisions for that item and month, with at least 3 divisions reporting. If half or more of the divisions are that far out, the whole item-month is dropped, since there is no consensus price to compare against. Rows go to `outputs/tables/outliers_cross_section.csv` with the rule name, and the step is in `cleaning_log.csv`. The rule drops 29 rows:

| Rule | Item, division | Rows | Months |
|---|---|---|---|
| \|log dev\| > 0.4 | rice, Khulna | 11 | Feb to Dec 2007 |
| \|log dev\| > 0.4 | potato, Rajshahi | 6 | Apr 2025 to May 2026 (the same 62.5 BDT/kg every month, one market) |
| \|log dev\| > 0.4 | potato, Dhaka; potato, Sylhet | 1 each | Mar 2025; Apr 2025 |
| \|log dev\| > 0.4 | onion, Sylhet | 3 | May to Jul 2026 (29 to 38 BDT/kg against about 65 elsewhere) |
| no consensus | potato, 5 divisions | 7 | Feb 2025 (2-2 split), Jun 2026 (3 far apart) |

No long-basket row is dropped other than the Khulna error. Real regional gaps are much smaller than the cut: the largest Dhaka gap is 7.1% and the 2025 spread of division indices is 7.8%. A side effect: with Rajshahi and Sylhet removed, potato and onion fall below 3 divisions in Apr to Jul 2026, so the wide basket now ends in Mar 2026 (19 months, was 22 to Jun 2026).

**Medium: changing division count.** The national price is now a matched-sample chain (`clean.matched_chain`). The month-on-month change is the ratio of mean prices over the divisions that report in both months, bridging gaps of up to 3 months. The level is set to the plain mean over the latest 12 full-coverage months, so current BDT prices match the simple average, and index numbers (which use ratios only) do not depend on that choice. The plain mean stays in `national_prices.price_mean_bdt`. A balanced panel was rejected because no long-basket item has all six divisions throughout (rice has 67 months with fewer). The choice is documented in `docs/DESIGN.md` and in a new notebook 01 section with fig02b. For rice, monthly changes on the two methods correlate at 0.96 and levels differ by at most 6.7%. The gap builds up from 2006 to 2011 and closes from 2019 to 2023, so 2016 rice is 31.1 BDT/kg on the chain against 29.3 on the plain mean. Nearly all of the change in the index level comes from the chain, not the Khulna fix. With the Khulna fix alone, the July 2026 Laspeyres stays at 172.6.

**Low items.**
- Notebooks 03 and 06 now both state that the spike thresholds differ on purpose: 4.74% for palm oil in notebook 03 (full sample, descriptive) and 4.22% in notebook 06 (2007 to 2019 only, for the backtest).
- Notebook 06 has a backtest variant that charges the 9% lending-rate cap for decisions from Apr 2020 to Jun 2023 (Bangladesh Bank BRPD Circular No. 03 of 24 Feb 2020; cap replaced by SMART from 1 Jul 2023 under the Jul-Dec 2023 monetary policy announced on 18 Jun 2023; both dates checked against news reports, see SOURCES.md). Output: `bayes_backtest_summary_rate_cap.csv` and `test_cap_*` facts. The circular and MPS are cited by name with Bangladesh Bank's index pages, not deep links, so the URLs should be checked before submission.
- The notebook 05 and 06 limits now say that gap filling uses the observation after the gap (a mild look-ahead), and notebook 05 says the SARIMA and ETS forms were picked after the full-sample ACF/PACF.
- fig42: the breakeven label sits at the top of the plot, left of the line, on a white box, and the legend is in the lower right. fig12: the legend is below the plot in one row.
- `data/raw/SOURCES.md` links the IMF Copyright and Usage page, https://www.imf.org/en/About/copyright-and-terms.

**Headline numbers, before and after.**

| Number | Before | After |
|---|---|---|
| Long staple index, Jul 2026 (2016 = 100): Laspeyres / Paasche / Fisher / chain | 172.6 / 164.2 / 168.3 / 176.5 | 164.5 / 155.9 / 160.2 / 167.5 |
| Laspeyres, Sep 2006 | 59.0 | 55.1 |
| Rice share of the 2016 to Jul 2026 rise | 0.691 | 0.672 |
| Rice contribution, index points | 50.2 | 43.4 |
| SD of staple y/y vs food CPI y/y (ratio, block-bootstrap CI) | 6.76 (4.4 to 10.5) | 6.93 (4.4 to 10.8) |
| Staple vs food CPI y/y correlation; best lead | 0.422; 2 months (r = 0.443) | 0.429; 1 month (r = 0.438) |
| Long-run pass-through, palm oil (95% CI) | 0.662 (0.52 to 0.80) | 0.664 (0.53 to 0.80) |
| Long-run pass-through, atta | 0.363 (0.19 to 0.53) | 0.364 (0.19 to 0.54) |
| Long-run pass-through, rice | 0.152 (0.02 to 0.28) | 0.156 (0.02 to 0.30) |
| Long-run pass-through, lentils (exchange rate) | -0.319 (-0.96 to 0.33) | -0.280 (-0.91 to 0.35) |
| Out-of-sample RMSE ratio, rice | 0.984 | 1.111 (now worse than the constant) |
| Ramadan, lentils drift-adjusted excess (one-sided p) | +0.51% (0.257) | +0.52% (0.247) |
| Ramadan regression, lentils pre-Ramadan month (p) | +1.98 pp | +1.91 pp (0.091) |
| Ramadan regression, palm oil Ramadan month (p) | -1.84 pp (0.050) | -1.94 pp (0.060) |
| Spikes in Ramadan months, permutation p | 0.117 | 0.093 |
| Bayes prior P(spike) | 0.106 (16/151) | 0.099 (15/151) |
| P(signal given spike) / P(signal given no spike) | 0.625 / 0.141 | 0.667 / 0.140 |
| Posterior, signal on / off | 0.345 / 0.049 | 0.345 / 0.041 |
| Breakeven P(spike) | 0.335 | 0.329 |
| EVPI / EVSI, BDT per 3,000 L | 3,913 / 110 | 3,705 / 170 |
| Backtest, Bayes rule vs always monthly | -0.72%, BDT 0.92 per litre | -0.72%, BDT 0.92 per litre |
| Backtest at the 9% cap, Apr 2020 to Jun 2023 | not run | Bayes -0.79%, forward +0.95%, oracle -1.88%; same 19 forward months |
| Forecast Jan 2027, rice (95% interval) | 49.8 (39.2 to 63.2), SARIMA | 48.5 (37.8 to 62.2), SARIMA |
| Forecast Jan 2027, staple index | 170.2 (140.0 to 207.0), SARIMA | 160.9 (132.8 to 199.6), ETS |
| Tests, notebook 02: p < 0.05 raw / after Holm | 69 / 62 | 70 / 66 |
| Dhaka pairs significant after Holm | 14 of 20 | 15 of 20 |

Other changes that the text now reflects: the lentil log level is borderline stationary on ADF/KPSS (p = 0.049 and 0.07), and notebook 05 says so and still differences it; ETS beat SARIMA for the staple index; division relative-price eta squared is 0.30 to 0.68 (was 0.14 to 0.72), with 36 Tukey pairs (was 34).

Reproducibility: statsmodels ignores `random_state` when ETS simulation resamples residuals, so the staple index interval moved between runs (lower 95% bound 132.7, then 132.2). Notebook 05 now draws the resampled errors itself from a seeded generator, which gives an interval of 132.8 to 199.6. Two reruns of notebook 05 wrote byte-identical forecast tables.
