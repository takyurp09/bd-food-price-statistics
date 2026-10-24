# Raw data sources

All files were downloaded by `src/download.py` on 24 October 2026. Downloads are treated as untrusted data: they stay in this folder and are read with `python -I`.

| File | Source | URL | Licence | Coverage |
|---|---|---|---|---|
| `wfp_food_prices_bgd.csv`, `wfp_markets_bgd.csv` | World Food Programme, "Bangladesh - Food Prices", Humanitarian Data Exchange | https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh (resource URLs found through the CKAN API `package_show?id=wfp-food-prices-for-bangladesh`) | CC BY-IGO | Jul 1998 to Aug 2026; 34,467 rows; 73 commodities; 110 markets; retail (33,600) and wholesale (867); BDT. Row 2 of the CSV is an HXL tag row and is skipped. |
| `faostat_cpi_bgd.csv` | FAOSTAT, Consumer Price Indices (domain CP), Bangladesh rows of the bulk file. FAO republishes the BBS national CPI. | https://bulks-faostat.fao.org/production/ConsumerPriceIndices_E_All_Data_(Normalized).zip | CC BY 4.0 | Monthly, Jan 2000 to Jun 2026: food CPI (2015 = 100), general CPI (2015 = 100), food price inflation (%, flag E = estimated by FAO). |
| `imf_er_bgd.xml`, `imf_bdt_usd_monthly.csv` | IMF, Exchange Rates dataset (IMF.STA ER, formerly in IFS), BDT per USD, period average | https://api.imf.org/external/sdmx/2.1/data/IMF.STA,ER/BGD.XDC_USD.PA_RT.M | IMF Copyright and Usage terms, https://www.imf.org/en/About/copyright-and-terms | May 1970 to Aug 2026. |
| `nasa_power_<division>.json`, `nasa_power_rain_monthly.csv` | NASA POWER, monthly point data, PRECTOTCORR (bias-corrected precipitation, mm/day), at the eight division headquarters | https://power.larc.nasa.gov/api/temporal/monthly/point (parameters in `src/download.py`) | NASA open data, no restrictions | Jan 2000 to Dec 2025. Converted to mm per month. |
| `CMO-Historical-Data-Monthly.xlsx`, `world_prices_monthly.csv` | World Bank Commodity Price Data (Pink Sheet), monthly | https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx | CC BY 4.0 | Jan 1960 to Dec 2025: rice Thai 5%, wheat US HRW, palm oil, soybean oil, sugar (world), crude oil average (USD), and the World Bank food price index (2010 = 100). |
| `ramadan_dates.csv` | Computed with the `hijridate` package (Umm al-Qura calendar), Ramadan 1420 to 1448 AH | https://pypi.org/project/hijridate/ | MIT (package) | Dec 1999 to Feb 2027. Bangladesh follows local moon sighting, so its start date can be one day later than Umm al-Qura. That error is at most one day in a month and does not matter for monthly data. |

## Index weights (BBS HIES)

The base quantities in `src/indices.py` come from Bangladesh Bureau of Statistics, *Household Income and Expenditure Survey (HIES) 2022: Final Report* (Dec 2023), Table 5.2, "Average Per Capita Daily Food Intake (Grams) by Food Items and Locality", national columns. The table gives both 2022 and 2016. PDF: https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs/2024/12/22b6e770f6a84cd9a48ff636ae506818.pdf (read on 24 October 2026, not kept in this folder).

| Item in index | HIES row | 2016 g/day | 2022 g/day |
|---|---|---|---|
| rice_coarse | Rice | 367.2 | 328.92 |
| atta | Wheat | 19.8 | 22.92 |
| lentil_masur | Pulses: Masoor | 9.8 | 11.88 |
| palm_oil, soybean_oil | Edible oils (total) | 26.8 | 30.85 |
| sugar | Sugar (gur excluded) | 6.4 | 15.12 |
| egg | Eggs | 13.6 | 12.73 |
| chicken_broiler | Chicken/Duck | 17.1 | 26.17 |
| onion | Onion | 31.1 | 30.16 |
| potato | Potato | 64.8 | 69.70 |
| chili_green | Chillies | 12.9 | 3.57 |

The long basket (base 2016) uses the 2016 column and the short basket (base 2025) uses 2022. Conversions: kg per month = g per day x 30.4 / 1000. Oil is priced per litre, so kg are divided by 0.92 kg/L, a typical density of vegetable oil. Eggs are priced per piece, so grams are divided by 50 g per egg (assumed edible weight). HIES does not separate palm from soybean oil (its "Soyabean" row, 27.85 g, likely includes loose palm oil sold under that name), so the short basket splits total edible oil 50/50 between the two; in the long basket palm oil stands in for all edible oil. All wheat is treated as atta, all chicken/duck as broiler, and the chillies row (green and dry together) as green chili.

## Flood months

`src/clean.py` builds two flood measures:

1. `heavy_rain`: a division-month whose rainfall is above the 90th percentile of the same calendar month for that division over 2000 to 2025 (NASA POWER). This is the objective measure and does not depend on the event list.
2. `flood_known`: months of major flood events listed in `flood_events.csv`, one row per event with start and end month, divisions affected ("national" means all divisions are flagged) and a source URL. Each event was checked against a humanitarian situation report or a damage assessment:

| Event | Months | Divisions | Source |
|---|---|---|---|
| 2004 monsoon floods | Jul to Sep 2004 | national | World Bank/ADB damage and needs assessment, https://www.preventionweb.net/quick/67985 |
| 2007 monsoon floods | Jul to Sep 2007 | national | Disaster Management Information Centre sitrep, Aug 2007, https://reliefweb.int/report/bangladesh/bangladesh-disaster-management-information-centre-situation-report-02-aug-2007 |
| 2017 northern floods | Aug 2017 | national | ACT Alliance alert, https://actalliance.org/?p=6387 |
| 2019 monsoon floods | Jul 2019 | national | IFRC MDRBD022 operation update, https://reliefweb.int/report/bangladesh/bangladesh-monsoon-floods-emergency-plan-action-operation-update-n-1-appeal-n |
| 2020 monsoon floods | Jul to Aug 2020 | national | ReliefWeb FL-2020-000161-BGD, https://reliefweb.int/disaster/FL-2020-000161-BGD |
| 2022 north-east flash floods | Jun 2022 | Sylhet, Mymensingh, Rangpur | UN RC situation update 1, 19 Jun 2022, https://m.reliefweb.int/report/3858093/bangladesh/bangladesh-2022-severe-flash-flood-office-un-resident-coordinator-situation-update-1-19-june-2022 |
| 2024 eastern flash floods | Aug 2024 | Chattogram, Sylhet | OCHA situation report 1, 25 Aug 2024, https://reliefweb.int/report/bangladesh/bangladesh-eastern-flash-flood-situation-report-no-01-25-august-2024 |

All seven events in the earlier hand-entered list were confirmed, so none was dropped. One change: the 2024 event now also flags Sylhet division, because Moulvibazar and Habiganj were among the worst-hit districts. The 2004 September month rests on the second wave that flooded Dhaka; the 2007 September month on the mid-September second wave reported by UNICEF and IRIN. The 2017 source is an NGO alert, not a UN or government report. FFWC annual flood reports were not reachable online and were not used.

## Sources that failed or were not used

- **FAO Food Price Index (monthly CSV):** the old download path on fao.org returned 404 and the page did not expose a machine-readable link. The World Bank food price index from the Pink Sheet is used in its place.
- **FRED:** `DEXBDUS` and `CCUSMA02BDM618N` returned 404. FRED has no BDT series that we could use. The IMF API worked, and the rate implied by WFP's `price / usdprice` is kept as a second series (`bdt_per_usd_wfp`).
- **BBS and Bangladesh Bank (Monthly Economic Trends):** both publish CPI as PDF tables. They were not scraped because FAOSTAT carries the same BBS index in machine-readable form.
- **Pink Sheet edition:** the file at the URL above ends in Dec 2025. A later edition may have a new URL.

## Licences

- Code, notebooks and text in this repo: MIT licence, Muhammad Taky Tahmid (see `LICENSE`).
- WFP food prices on HDX: CC BY-IGO. Credit "World Food Programme (WFP), via HDX".
- FAOSTAT consumer price indices: CC BY 4.0, under FAO's statistical database terms of use.
- World Bank Pink Sheet: CC BY 4.0.
- IMF exchange rates: IMF "Copyright and Usage" terms, https://www.imf.org/en/About/copyright-and-terms. Check that page before redistributing the series; this repo only uses the data with attribution.
- NASA POWER rainfall: NASA open data, no restrictions; NASA asks users to cite the POWER project.
- Flood event list (`flood_events.csv`): built here from the cited reports. Each row links to its source, and the reports themselves stay under their publishers' terms.
- The lending rate in notebook 06 is a single figure quoted from a news report (The Financial Express, citing Bangladesh Bank) and is not redistributed as data.
- The 9% lending-rate cap used in the notebook 06 variant comes from Bangladesh Bank BRPD Circular No. 03 of 24 February 2020 (cap in force from 1 April 2020; https://www.bb.org.bd/en/index.php/mediaroom/circular, reported at https://www.tbsnews.net/node/297970). The cap ended on 1 July 2023, when the monetary policy for July-December 2023, announced on 18 June 2023, brought in the SMART reference rate (https://www.bb.org.bd/en/index.php/monetaryactivity/mps, reported at https://en.prothomalo.com/business/local/mlhvuwarpr). Both dates were checked against these reports on 24 October 2026; the Bangladesh Bank PDF itself returned HTTP 403 to our fetch.
