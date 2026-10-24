/* Bangladesh food price statistics dashboard. Data baked by scripts/build_site_data.py. */
(function () {
  'use strict';
  var C = { blue: '#0072B2', orange: '#E69F00', off: '#D55E00', green: '#009E73', sky: '#56B4E9', pink: '#CC79A7', yellow: '#F0E442', muted: '#64748b', grid: '#e2e8f0', text: '#0f172a' };
  var PAL = [C.blue, C.orange, C.green, C.off, C.pink, C.sky, '#8c6d31'];
  var D = {}, charts = {}, rendered = {};
  var mobile = function () { return window.innerWidth < 600; };

  // ---------- formatting ----------
  function f(v, d) { return v == null ? '–' : (+v).toFixed(d == null ? 1 : d).replace('-', '−'); }
  function pct(v, d) { return v == null ? '–' : f(v * 100, d) + '%'; }
  function sgn(v, d) { return v == null ? '–' : (v > 0 ? '+' : '') + f(v, d); }
  function int(v) { return Math.round(v).toLocaleString('en-US').replace('-', '−'); }
  function bdt(v) { return (v < 0 ? '−' : '') + 'Tk ' + Math.round(Math.abs(v)).toLocaleString('en-US'); }
  function pv(p) { if (p == null) return '–'; if (p < 0.001) return '<0.001'; return p.toFixed(3); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function monthName(ym) { return MON[+ym.slice(5, 7) - 1] + ' ' + ym.slice(0, 4); }

  function chart(id) {
    if (!charts[id]) charts[id] = echarts.init(document.getElementById(id), null, { renderer: 'canvas' });
    return charts[id];
  }
  var base = function () {
    return {
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: C.text },
      grid: { left: 8, right: 16, top: 36, bottom: 30, containLabel: true },
      tooltip: { trigger: 'axis', confine: true },
      legend: { type: 'scroll', top: 0, left: 0, right: 0, textStyle: { color: C.muted, fontSize: 11 } }
    };
  };
  var yVal = function (fmt, name) { return { type: 'value', scale: true, name: name, nameTextStyle: { color: C.muted }, axisLabel: { color: C.muted, formatter: fmt }, splitLine: { lineStyle: { color: C.grid } } }; };
  // category date axis: label January only, every `step` years (wider on phones)
  function dateAxis(months, step) {
    var s = step || (months.length > 150 ? (mobile() ? 6 : 3) : months.length > 60 ? (mobile() ? 2 : 1) : 1);
    return { type: 'category', data: months, boundaryGap: false,
      axisTick: { show: false },
      axisLabel: { color: C.muted, hideOverlap: true, interval: function (i, v) { return v.slice(5, 7) === '01' && (+v.slice(0, 4)) % s === 0; },
        formatter: function (v) { return v.slice(0, 4); } } };
  }
  function axisTip(fmt) {
    return { trigger: 'axis', confine: true, formatter: function (ps) {
      var out = monthName(ps[0].axisValue);
      ps.forEach(function (p) { var v = Array.isArray(p.value) ? p.value[1] : p.value; if (v != null && p.seriesName.indexOf('_') !== 0) out += '<br>' + p.marker + esc(p.seriesName) + ': <b>' + fmt(v) + '</b>'; });
      return out;
    } };
  }
  function kpiCard(label, value, sub, color) {
    return '<div class="kpi" style="--kc:' + color + '"><div class="kpi-l">' + label + '</div><div class="kpi-v">' + value + '</div><div class="kpi-s">' + sub + '</div></div>';
  }

  // ---------- tabs ----------
  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  function show(tab) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    });
    var key = tab.id.replace('tab-', '');
    if (!rendered[key]) { RENDER[key](); rendered[key] = true; }
    Object.keys(charts).forEach(function (k) { charts[k].resize(); });
    try { history.replaceState(null, '', '#' + key); } catch (e) {}
  }
  tabs.forEach(function (t, i) {
    t.addEventListener('click', function () { show(t); });
    t.addEventListener('keydown', function (e) {
      var j = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null;
      if (j == null) return;
      var n = tabs[(j + tabs.length) % tabs.length]; n.focus(); show(n);
    });
  });
  window.addEventListener('hashchange', function () { var t = tabFor(location.hash.slice(1)); if (t && t.getAttribute('aria-selected') !== 'true') show(t); });
  var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { Object.keys(charts).forEach(function (k) { charts[k].resize(); }); }, 120); });

  // ---------- Overview ----------
  function renderOverview() {
    var o = D.overview, k = o.kpi;
    document.getElementById('ov-question').innerHTML = 'Rice, wheat flour (atta), red lentils and palm oil are the four staples with the longest WFP price record in Bangladesh (the full file has ' + int(k.wfp_rows) + ' price records from ' + k.wfp_markets + ' markets). ' +
      '<strong>How fast have staple prices risen, does the official food CPI capture it, and what can a buyer do about price spikes?</strong> Each tab answers one part with one topic from BUS173.';
    document.getElementById('kpis').innerHTML = [
      kpiCard('Staple prices since 2016', '+' + f(k.fisher_last - 100, 1) + '%', 'Fisher index ' + f(k.fisher_last, 1) + ' in ' + monthName(k.last_month) + ' (2016 = 100), HIES-weighted', C.blue),
      kpiCard('Rice share of the rise', pct(k.rice_share, 0), 'Rice adds ' + f(k.contrib.rice_coarse, 1) + ' of the Laspeyres points, palm oil ' + f(k.contrib.palm_oil, 1), C.orange),
      kpiCard('Volatility vs food CPI', f(k.sd_ratio, 1) + '× <span class="pair">CI ' + f(k.sd_ratio_ci[0], 1) + '–' + f(k.sd_ratio_ci[1], 1) + '</span>', 'SD of y/y inflation: staples ' + f(k.sd_yoy_fisher, 1) + ' pp, food CPI ' + f(k.sd_yoy_cpi, 1) + ' pp', C.off),
      kpiCard('Palm oil pass-through', f(k.palm_pt, 2) + ' <span class="pair">CI ' + f(k.palm_pt_ci[0], 2) + '–' + f(k.palm_pt_ci[1], 2) + '</span>', 'A 10% rise in the world price in taka adds about ' + f(k.palm_10, 1) + '% within 3 months', C.green),
      kpiCard('Ramadan price rise', 'None found', 'No staple rises more in Ramadan (lowest p = ' + pv(k.ram_min_p) + '). Spikes are rarer then: odds ratio ' + f(k.ram_or, 2), C.sky),
      kpiCard('Bayes rule, palm oil buying', f(-k.bayes_pct, 2) + '% <span class="pair">cheaper</span>', 'than buying monthly, 2020-2025 back-test (Tk ' + f(k.bayes_bdt_l, 2) + ' per litre); perfect foresight: ' + f(-k.oracle_pct, 2) + '%', C.pink)
    ].join('');
    document.getElementById('ov-note').innerHTML = 'Both lines trend up, so their levels correlate at r = ' + f(k.corr_levels, 2) + '. Year-on-year changes correlate at only r = ' + f(k.corr_yoy, 2) +
      ', and staple prices lead the CPI by about ' + k.lead + (k.lead === 1 ? ' month' : ' months') + ' (r = ' + f(k.lead_corr, 2) + '). In ' + monthName(k.cmp_last) + ' the staple index sat ' + f(Math.abs(k.gap_last), 1) +
      '% below the food CPI, so since 2016 the official food basket has risen faster than these four staples.';
    var opt = base();
    opt.tooltip = axisTip(function (v) { return f(v, 1); });
    opt.xAxis = dateAxis(o.months);
    opt.yAxis = yVal(null);
    opt.series = [
      { name: 'Staple Fisher index (4 items)', type: 'line', data: o.fisher, symbol: 'none', lineStyle: { width: 2.2, color: C.blue }, itemStyle: { color: C.blue },
        markLine: { symbol: 'none', silent: true, lineStyle: { color: C.muted, type: 'dashed', width: 1 }, label: { formatter: '2016 = 100', color: C.muted, fontSize: 11, position: 'insideStartTop' }, data: [{ yAxis: 100 }] } },
      { name: 'Official food CPI', type: 'line', data: o.cpi_food, symbol: 'none', lineStyle: { width: 2.2, color: C.orange }, itemStyle: { color: C.orange } }
    ];
    chart('c-ov').setOption(opt);
  }

  // ---------- Prices ----------
  function renderExplorer() {
    var P = D.prices, it = document.getElementById('sel-item').value, e = P.explorer[it];
    var first = e.national.findIndex(function (v) { return v != null; });
    var months = e.months.slice(first);
    var nd = Object.keys(e.divisions).filter(function (d) { return e.divisions[d].some(function (v) { return v != null; }); });
    document.getElementById('ex-hint').textContent = e.unit + ' · ' + nd.length + ' divisions · ' + monthName(months[0]) + ' to ' + monthName(months[months.length - 1]);
    var opt = base();
    opt.tooltip = axisTip(function (v) { return f(v, 1); });
    opt.xAxis = dateAxis(months);
    opt.yAxis = yVal(null);
    opt.series = nd.map(function (d, i) {
      return { name: d, type: 'line', data: e.divisions[d].slice(first), symbol: 'none', connectNulls: false, lineStyle: { width: 1.1, color: PAL[(i + 1) % PAL.length], opacity: 0.8 }, itemStyle: { color: PAL[(i + 1) % PAL.length] } };
    });
    opt.series.unshift({ name: 'National', type: 'line', data: e.national.slice(first), symbol: 'none', lineStyle: { width: 3, color: C.text }, itemStyle: { color: C.text }, z: 5 });
    chart('c-explorer').setOption(opt, true);
  }
  function renderPrices() {
    var P = D.prices, sel = document.getElementById('sel-item');
    sel.innerHTML = Object.keys(P.explorer).map(function (k) { return '<option value="' + k + '">' + esc(P.explorer[k].label) + '</option>'; }).join('');
    sel.addEventListener('change', renderExplorer);
    renderExplorer();

    var X = P.index, F = P.index_facts, o = base();
    o.tooltip = axisTip(function (v) { return f(v, 1); });
    o.xAxis = dateAxis(X.months);
    o.yAxis = yVal(null);
    o.series = [['Laspeyres', X.laspeyres, C.blue], ['Paasche', X.paasche, C.orange], ['Fisher', X.fisher, C.text], ['Chain Laspeyres', X.chain, C.green]].map(function (s, i) {
      return { name: s[0], type: 'line', data: s[1], symbol: 'none', lineStyle: { width: i === 2 ? 2.4 : 1.5, color: s[2], type: i === 3 ? 'dashed' : 'solid' }, itemStyle: { color: s[2] } };
    });
    chart('c-index').setOption(o);
    document.getElementById('ix-note').innerHTML = '<strong>How to read this:</strong> in ' + monthName(F.last) + ' Laspeyres (2016 quantities) reads ' + f(F.las, 1) + ', Paasche (current quantities) ' + f(F.paa, 1) +
      ', and Fisher, their geometric mean, ' + f(F.fis, 1) + '. Laspeyres runs above Paasche because households shift toward items that got relatively cheaper; the gap peaked at ' + f(F.gap_max, 1) + '% in ' + monthName(F.gap_max_month) +
      '. Redrawing the weights 500 times at random keeps the latest Laspeyres between ' + f(F.sens_lo, 1) + ' and ' + f(F.sens_hi, 1) + ' (5th to 95th percentile).';

    document.querySelector('#t-weights tbody').innerHTML = P.weights.map(function (r) {
      return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[2]) + '</td><td class="num">' + f(r[3], 2) + '</td><td class="num">' + f(r[4], 1) + '</td><td class="num">' + pct(r[5], 1) + '</td><td class="wrap-cell">' + esc(r[6]) + '</td></tr>';
    }).join('');

    var Y = P.yoy, o2 = base();
    o2.tooltip = axisTip(function (v) { return f(v, 1) + '%'; });
    o2.xAxis = dateAxis(Y.months);
    o2.yAxis = yVal(function (v) { return v + '%'; });
    o2.series = [
      { name: 'Staple Fisher index', type: 'line', data: Y.fisher, symbol: 'none', lineStyle: { width: 1.8, color: C.blue }, itemStyle: { color: C.blue } },
      { name: 'Food CPI', type: 'line', data: Y.cpi, symbol: 'none', lineStyle: { width: 2, color: C.orange }, itemStyle: { color: C.orange } }
    ];
    chart('c-yoy').setOption(o2);
    var yf = P.yoy_facts;
    document.getElementById('yoy-note').innerHTML = '<strong>How to read this:</strong> the SD of staple y/y inflation is ' + f(yf.sd_f, 1) + ' points against ' + f(yf.sd_c, 1) + ' for the food CPI. Monthly y/y rates correlate at r = ' +
      f(yf.corr, 2) + '; annual averages at r = ' + f(yf.corr_annual, 2) + '.';

    var A = P.annual, o3 = base();
    o3.tooltip = { trigger: 'axis', confine: true, valueFormatter: function (v) { return f(v, 1) + '%'; } };
    o3.xAxis = { type: 'category', data: A.years, axisLabel: { color: C.muted, interval: mobile() ? 3 : 1 } };
    o3.yAxis = yVal(function (v) { return v + '%'; });
    o3.series = [
      { name: 'Staple Fisher index', type: 'bar', data: A.staple, itemStyle: { color: C.blue } },
      { name: 'Food CPI', type: 'bar', data: A.cpi, itemStyle: { color: C.orange } }
    ];
    chart('c-annual').setOption(o3);
  }

  // ---------- Tests ----------
  function renderTestTable() {
    var T = D.tests, s = document.getElementById('sel-section').value;
    var rows = T.rows.filter(function (r) { return s === 'all' || (r[0] + '|' + r[1]) === s; });
    document.querySelector('#t-tests tbody').innerHTML = rows.map(function (r) {
      var sig = r[7] != null && r[7] < 0.05;
      return '<tr' + (sig ? ' class="sig"' : '') + '><td>' + esc(r[2]) + '</td><td>' + esc(r[3]) + '</td><td class="num">' + (r[4] == null ? '–' : int(r[4])) + '</td><td class="num">' + f(r[5], 2) +
        '</td><td class="num">' + pv(r[6]) + '</td><td class="num">' + pv(r[7]) + '</td><td>' + (r[8] ? esc(r[8]) + ' ' + f(r[9], 2) : '–') + '</td><td class="wrap-cell">' + (r[10] ? esc(r[10]) : '') + '</td></tr>';
    }).join('');
  }
  function renderTests() {
    var T = D.tests, sel = document.getElementById('sel-section'), seen = {};
    var opts = ['<option value="all">All sections (' + T.rows.length + ' tests)</option>'];
    T.rows.forEach(function (r) { var k = r[0] + '|' + r[1]; if (!seen[k]) { seen[k] = 0; } seen[k]++; });
    Object.keys(seen).forEach(function (k) { var p = k.split('|'); opts.push('<option value="' + esc(k) + '">Notebook ' + p[0] + ' · ' + esc(p[1].replace(/^\d+[ab]? /, '')) + ' (' + seen[k] + ')</option>'); });
    sel.innerHTML = opts.join('');
    sel.value = '02|3 Ramadan';
    if (!sel.value) sel.value = 'all';
    sel.addEventListener('change', renderTestTable);
    renderTestTable();
    var c = T.counts;
    document.getElementById('ht-hint').textContent = 'Notebook 02: ' + c.t02_holm + ' of ' + c.t02 + ' significant after Holm · notebook 03: ' + c.t03_holm + ' of ' + c.t03;

    var R = T.ramadan, o = base();
    o.legend = { show: false }; o.grid.top = 16; o.grid.right = 24;
    o.tooltip = { trigger: 'axis', confine: true, formatter: function (ps) { var r = R[ps[0].dataIndex]; return esc(r[1]) + '<br>Excess change <b>' + sgn(r[2], 2) + '%</b><br>One-sided p = ' + pv(r[3]); } };
    o.xAxis = { type: 'category', data: R.map(function (r) { return r[1]; }), axisLabel: { color: C.muted, interval: 0, fontSize: mobile() ? 10 : 12, formatter: function (v) { return v.replace(' (', '\n('); } } };
    o.yAxis = yVal(function (v) { return v + '%'; }); o.yAxis.scale = false;
    o.series = [{ type: 'bar', name: 'Excess change', data: R.map(function (r) { return { value: r[2], itemStyle: { color: r[2] > 0 ? C.off : C.blue } }; }), barMaxWidth: 60,
      label: { show: true, position: 'top', color: C.muted, fontSize: 11, formatter: function (p) { return 'p = ' + pv(R[p.dataIndex][3]); } } }];
    chart('c-ramadan').setOption(o);
    var mk = T.ramadan_market.filter(function (r) { return r[2] > 0; });
    document.getElementById('ram-note').innerHTML = '<strong>How to read this:</strong> a bar above zero would mean prices rise more in Ramadan than in the two months before, after removing the normal monthly drift. Three of four staples go the other way and none is significant. In the 2025-2026 market data, ' +
      (mk.length ? mk.map(function (r) { return esc(r[1].toLowerCase()) + ' (' + sgn(r[2], 2) + '%)'; }).join(', ') + ' is the only item that rose; ' : '') + 'onion fell ' + f(-T.ramadan_market.filter(function (r) { return r[0] === 'onion'; })[0][2], 1) + '% and eggs ' + f(-T.ramadan_market.filter(function (r) { return r[0] === 'egg'; })[0][2], 1) + '%.';

    var L = T.levels, data = [];
    L.values.forEach(function (row, i) { row.forEach(function (v, j) { data.push([j, i, v]); }); });
    var h = {
      textStyle: base().textStyle,
      tooltip: { confine: true, formatter: function (p) { return esc(L.divisions[p.value[1]]) + ', ' + esc(L.items[p.value[0]]) + '<br><b>' + sgn(p.value[2], 1) + '%</b> vs national'; } },
      grid: { left: 8, right: 8, top: 8, bottom: 52, containLabel: true },
      xAxis: { type: 'category', data: L.items, axisLabel: { color: C.muted, interval: 0, fontSize: 11, formatter: function (v) { return v.replace(' (', '\n('); } } },
      yAxis: { type: 'category', data: L.divisions, inverse: true, axisLabel: { color: C.muted } },
      visualMap: { min: -6, max: 6, calculable: false, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 140, itemWidth: 10, text: ['+6%', '−6%'], textStyle: { color: C.muted, fontSize: 11 },
        inRange: { color: ['#0072B2', '#f8fafc', '#D55E00'] } },
      series: [{ type: 'heatmap', data: data, label: { show: true, fontSize: 11, color: C.text, formatter: function (p) { return sgn(p.value[2], 1); } } }]
    };
    chart('c-levels').setOption(h);
    document.getElementById('lv-note').innerHTML = '<strong>How to read this:</strong> one-way ANOVA on yearly relative prices finds real division differences in levels (η² = ' + f(T.eta.rice_coarse, 2) + ' rice, ' + f(T.eta.atta, 2) + ' atta, ' +
      f(T.eta.lentil_masur, 2) + ' lentils, ' + f(T.eta.palm_oil, 2) + ' palm oil; ' + T.tukey_sig + ' Tukey pairs differ). But ' + T.infl_any_sig + ' of 4 items show a division difference in annual inflation: some divisions are dearer, none gets dearer faster. On the division Laspeyres index, where rice carries most of the weight, ' +
      esc(T.dearest) + ' was dearest in 2025 and ' + esc(T.cheapest) + ' cheapest. Item by item the dearest division differs: ' +
      L.items.map(function (it, j) { var b = 0; L.values.forEach(function (v, i) { if (v[j] > L.values[b][j]) b = i; }); return esc(it.replace(/ \(.*\)/, '').toLowerCase()) + ' ' + esc(L.divisions[b]) + ' (' + sgn(L.values[b][j], 1) + '%)'; }).join(', ') + '.';

    document.querySelector('#t-cross tbody').innerHTML = T.cross.map(function (r) {
      var re = r.ev_spike / (r.ev_spike + r.ev_none), ro = r.oth_spike / (r.oth_spike + r.oth_none), sig = r.p_fisher != null && r.p_fisher < 0.05;
      return '<tr' + (sig ? ' class="chosen"' : '') + '><td>' + esc(r.event) + '</td><td class="num">' + int(r.ev_spike) + ' / ' + int(r.ev_none) + '</td><td class="num">' + int(r.oth_spike) + ' / ' + int(r.oth_none) +
        '</td><td class="num">' + pct(re, 1) + ' vs ' + pct(ro, 1) + '</td><td class="num">' + f(r.odds, 2) + (r.ci ? ' (' + f(r.ci[0], 2) + '–' + f(r.ci[1], 2) + ')' : '') + '</td><td class="num">' + pv(r.p_fisher) + '</td><td class="num">' + pv(r.p_perm) + '</td></tr>';
    }).join('');
    var fl = T.cross.filter(function (r) { return r.event.indexOf('one month later') > 0 && r.event.indexOf('Flood') === 0; })[0];
    document.getElementById('cross-note').innerHTML = '<strong>How to read this:</strong> counts are item-months for the four staples (national) or division-item-months (rain). Only a flood followed by prices one month later stands out (odds ratio ' + f(fl.odds, 2) +
      ', Fisher p = ' + pv(fl.p_fisher) + '), and the circular-shift permutation test, which keeps the time pattern of floods, puts p at ' + pv(fl.p_perm) + '. Ramadan months show fewer spikes, not more. Direction of change by season: χ² = ' + f(T.dir_season.chi2, 1) +
      ', permutation p = ' + pv(T.dir_season.p) + ', Cramér\'s V = ' + f(T.dir_season.v, 3) + '. Spikes by calendar month: χ² = ' + f(T.gof.chi2, 1) + ', p = ' + pv(T.gof.p) + '.';

    document.querySelector('#t-dist tbody').innerHTML = T.dist.map(function (r) {
      return '<tr><td>' + esc(r[1]) + '</td><td class="num">' + r[2] + '</td><td class="num">' + f(r[3], 2) + '</td><td class="num">' + f(r[4], 2) + '</td><td class="num">' + f(r[5], 2) + '</td><td class="num">' + pv(r[6]) +
        '</td><td class="num">' + pv(r[7]) + '</td><td class="num">' + f(r[8], 1) + '</td><td class="num">' + f(r[9], 1) + '</td><td class="num">' + pct(r[10], 1) + '</td></tr>';
    }).join('');
  }

  // ---------- Regression ----------
  function renderRegression() {
    var G = D.regression, n = G.vars.length;
    var short = function (v) { return v.replace('World ', 'W. ').replace(' (coarse)', '').replace('Wheat flour (atta)', 'Atta').replace('Lentils (masur)', 'Lentils').replace(' (L)', '').replace(' (Thai 5%)', ' rice').replace(' (US HRW)', ' wheat').replace('W. rice rice', 'W. rice').replace('W. wheat wheat', 'W. wheat'); };
    var h = {
      textStyle: base().textStyle,
      tooltip: { confine: true, formatter: function (p) { var d = p.data; return esc(G.vars[d[0]]) + ' × ' + esc(G.vars[d[1]]) + '<br>r = <b>' + f(d[2], 2) + '</b>' + (d[4] ? '<br>n = ' + d[4] + ', p = ' + pv(d[3]) : ''); } },
      grid: { left: 8, right: 8, top: 8, bottom: 52, containLabel: true },
      xAxis: { type: 'category', data: G.vars.map(short), axisLabel: { color: C.muted, interval: 0, rotate: 45, fontSize: 10 } },
      yAxis: { type: 'category', data: G.vars.map(short), inverse: true, axisLabel: { color: C.muted, fontSize: 10 } },
      visualMap: { dimension: 2, min: -1, max: 1, calculable: false, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 140, itemWidth: 10, text: ['+1', '−1'], textStyle: { color: C.muted, fontSize: 11 },
        inRange: { color: ['#0072B2', '#f8fafc', '#D55E00'] } },
      series: [{ type: 'heatmap', data: G.heat, label: { show: !mobile(), fontSize: 9, color: C.text, formatter: function (p) { return p.data[0] === p.data[1] ? '' : f(p.data[2], 2); } } }]
    };
    chart('c-heat').setOption(h);

    var S = G.spurious, o = base();
    o.grid.top = 40;
    o.tooltip.valueFormatter = function (v) { return f(v, 2); };
    o.yAxis = { type: 'category', data: S.map(function (r) { return r[0] + ' vs\n' + r[1]; }), inverse: true, axisLabel: { color: C.muted, fontSize: 11 } };
    o.xAxis = yVal(function (v) { return v.toFixed(1); }); o.xAxis.scale = false; o.xAxis.min = -0.2; o.xAxis.max = 1;
    o.series = [
      { name: 'Correlation of levels', type: 'bar', data: S.map(function (r) { return r[2]; }), itemStyle: { color: C.off } },
      { name: 'Correlation of monthly changes', type: 'bar', data: S.map(function (r) { return r[3]; }), itemStyle: { color: C.blue } }
    ];
    chart('c-spur').setOption(o);
    var sl = G.simple.filter(function (r) { return r[0] === 'rice_coarse'; });
    document.getElementById('spur-note').innerHTML = '<strong>How to read this:</strong> two series that both trend up look related in levels even when they are not. Of 2,000 pairs of independent random walks, ' + pct(G.rw.levels, 0) + ' show a "significant" level correlation; in changes it is ' +
      pct(G.rw.diff, 1) + ', close to the 5% you would expect. Regressing rice on the Thai price in levels gives slope ' + f(sl[0][3], 2) + ' with R² = ' + f(sl[0][6], 2) + ' and Durbin-Watson ' + f(sl[0][7], 2) + '; in changes the slope is ' + f(sl[1][3], 3) + ' (CI ' + f(sl[1][4], 2) + ' to ' + f(sl[1][5], 2) + ').';

    var T = G.passthrough, o2 = base();
    o2.legend = { show: false }; o2.grid.top = 16; o2.grid.right = 24;
    o2.tooltip = { trigger: 'axis', confine: true, formatter: function (ps) { var r = T[ps[0].dataIndex]; return esc(r[1]) + ' (' + (r[2] === 'fx' ? 'exchange rate' : 'world price in taka') + ')<br>Pass-through <b>' + f(r[3], 2) + '</b><br>95% CI ' + f(r[4], 2) + ' to ' + f(r[5], 2) + '<br>p (H0: 0) = ' + pv(r[6]) + '<br>Adj. R² = ' + f(r[9], 2); } };
    o2.xAxis = { type: 'category', data: T.map(function (r) { return r[1] + (r[2] === 'fx' ? '*' : ''); }), axisLabel: { color: C.muted, interval: 0, fontSize: mobile() ? 10 : 12, formatter: function (v) { return v.replace(' (', '\n('); } } };
    o2.yAxis = yVal(function (v) { return v.toFixed(1); }); o2.yAxis.scale = false; o2.yAxis.min = -1; o2.yAxis.max = 1;
    o2.series = [
      { name: 'Pass-through', type: 'bar', barMaxWidth: 56, data: T.map(function (r) { return { value: r[3], itemStyle: { color: r[2] === 'fx' ? C.muted : r[6] < 0.05 ? C.green : C.sky } }; }),
        markLine: { symbol: 'none', silent: true, lineStyle: { color: C.text, type: 'dashed', width: 1 }, label: { formatter: 'full pass-through', color: C.muted, fontSize: 11, position: 'insideEndTop' }, data: [{ yAxis: 1 }] } },
      { name: '_ci', type: 'custom', renderItem: function (params, api) {
        var x = api.coord([api.value(0), api.value(1)]), y2 = api.coord([api.value(0), api.value(2)]), w = 8;
        var st = { stroke: C.text, lineWidth: 1.5 };
        return { type: 'group', children: [
          { type: 'line', shape: { x1: x[0], y1: x[1], x2: y2[0], y2: y2[1] }, style: st },
          { type: 'line', shape: { x1: x[0] - w, y1: x[1], x2: x[0] + w, y2: x[1] }, style: st },
          { type: 'line', shape: { x1: y2[0] - w, y1: y2[1], x2: y2[0] + w, y2: y2[1] }, style: st }] };
      }, data: T.map(function (r, i) { return [i, r[4], r[5]]; }), z: 10, tooltip: { show: false } }
    ];
    chart('c-pt').setOption(o2);
    document.getElementById('pt-note').innerHTML = '<strong>How to read this:</strong> 0.66 means a 10% rise in the world palm oil price, in taka, raises the Bangladeshi price by about 6.6% within three months. Every interval sits below 1, so no staple passes on world prices in full. Rice (' +
      f(T[0][3], 2) + ') is mostly insulated. *Lentils have no world price series, so their bar is the exchange-rate effect and is not significant. A division panel gives the same palm oil answer (' + f(G.panel.lr, 2) + ', CI ' + f(G.panel.ci[0], 2) + '–' + f(G.panel.ci[1], 2) + ', ' + int(G.panel.n) + ' division-months).';

    document.querySelector('#t-oos tbody').innerHTML = G.oos.map(function (r) {
      var good = r[6] < 1;
      return '<tr' + (r[0] === 'palm_oil' ? ' class="chosen"' : '') + '><td>' + esc(r[1]) + '</td><td class="num">' + r[3] + '</td><td class="num">' + f(r[4], 2) + '</td><td class="num">' + f(r[5], 2) + '</td><td class="num ' + (good ? 'pos' : 'neg') + '">' + f(r[6], 2) + '</td><td class="num">' + f(r[7], 2) + '</td></tr>';
    }).join('');
    var dg = G.diag;
    document.getElementById('oos-note').innerHTML = '<strong>How to read this:</strong> the ratio divides the model\'s RMSE on 2020-2025 monthly % changes by that of the training-sample mean. Below 1 means the model helps. Only palm oil clearly does (ratio ' + f(G.oos[3][6], 2) + ', out-of-sample R² ' + f(G.oos[3][7], 2) +
      '). Residual checks: Breusch-Godfrey rejects in ' + dg.bg + ' of 4 models and Jarque-Bera in ' + dg.jb + ' of 4, so all standard errors are Newey-West; the largest VIF is ' + f(dg.vif, 2) + '.';
  }

  // ---------- Time series ----------
  function renderTrend() {
    var S = D.timeseries, k = document.getElementById('sel-trend').value, h = S.hist[k], tr = S.trend[k], st = S.strength[k];
    document.getElementById('trend-hint').textContent = 'Log-linear growth ' + f(tr[0], 2) + '% a year (CI ' + f(tr[1], 2) + ' to ' + f(tr[2], 2) + ')';
    var o = base();
    o.tooltip = axisTip(function (v) { return f(v, 1); });
    o.xAxis = dateAxis(h.months);
    o.yAxis = yVal(null);
    o.series = [
      { name: k === 'rice_coarse' ? 'Coarse rice' : 'Staple index', type: 'line', data: h.values, symbol: 'none', lineStyle: { width: 1.2, color: C.sky }, itemStyle: { color: C.sky } },
      { name: 'Trend (centred 12-month MA)', type: 'line', data: h.trend, symbol: 'none', lineStyle: { width: 2.4, color: C.blue }, itemStyle: { color: C.blue } }
    ];
    chart('c-trend').setOption(o, true);
    document.getElementById('trend-note').innerHTML = '<strong>How to read this:</strong> on log prices, STL gives a trend strength of ' + f(st[1], 2) + ' and a seasonal strength of ' + f(st[0], 2) + ' (0 = none, 1 = all). These prices are mostly trend plus shocks.';
  }
  function renderForecast() {
    var S = D.timeseries, k = document.getElementById('sel-fc').value, h = S.hist[k], F = S.forecast[k];
    var start = Math.max(0, h.months.length - 48), hm = h.months.slice(start), months = hm.concat(F.months);
    var pad = function (arr, before) { var a = []; for (var i = 0; i < before; i++) a.push(null); return a.concat(arr); };
    var nH = hm.length, last = h.values[h.values.length - 1];
    var lo95 = pad([last].concat(F.lo95), nH - 1), hi95 = pad([last].concat(F.hi95), nH - 1), lo80 = pad([last].concat(F.lo80), nH - 1), hi80 = pad([last].concat(F.hi80), nH - 1);
    var band = function (lo, hi) { return hi.map(function (v, i) { return v == null ? null : v - lo[i]; }); };
    document.getElementById('fc-hint').textContent = F.method.toUpperCase() + ', from ' + monthName(F.last_month);
    var o = base();
    o.tooltip = axisTip(function (v) { return f(v, 1); });
    o.xAxis = dateAxis(months, 1);
    o.xAxis.axisLabel.interval = function (i, v) { return v.slice(5, 7) === '01'; };
    o.yAxis = yVal(null);
    o.series = [
      { name: '_lo95', type: 'line', data: lo95, stack: 'b95', symbol: 'none', lineStyle: { opacity: 0 }, tooltip: { show: false } },
      { name: '95% interval', type: 'line', data: band(lo95, hi95), stack: 'b95', symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: C.blue, opacity: 0.12 }, itemStyle: { color: '#c6dcec' } },
      { name: '_lo80', type: 'line', data: lo80, stack: 'b80', symbol: 'none', lineStyle: { opacity: 0 }, tooltip: { show: false } },
      { name: '80% interval', type: 'line', data: band(lo80, hi80), stack: 'b80', symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: C.blue, opacity: 0.22 }, itemStyle: { color: '#99c2dd' } },
      { name: 'Actual', type: 'line', data: h.values.slice(start), symbol: 'none', lineStyle: { width: 2, color: C.text }, itemStyle: { color: C.text } },
      { name: 'Forecast', type: 'line', data: pad([last].concat(F.f), nH - 1), symbol: 'none', lineStyle: { width: 2, color: C.blue, type: 'dashed' }, itemStyle: { color: C.blue } }
    ];
    o.legend.data = ['Actual', 'Forecast', '80% interval', '95% interval'];
    o.tooltip = { trigger: 'axis', confine: true, formatter: function (ps) {
      var i = ps[0].dataIndex, out = monthName(months[i]);
      if (i < nH) return out + '<br>Actual: <b>' + f(h.values[start + i], 1) + '</b>';
      var j = i - nH;
      return out + '<br>Forecast: <b>' + f(F.f[j], 1) + '</b><br>80%: ' + f(F.lo80[j], 1) + ' to ' + f(F.hi80[j], 1) + '<br>95%: ' + f(F.lo95[j], 1) + ' to ' + f(F.hi95[j], 1);
    } };
    chart('c-fc').setOption(o, true);
    var n = F.f.length - 1;
    document.getElementById('fc-note').innerHTML = '<strong>How to read this:</strong> the forecast for ' + monthName(F.months[n]) + ' is ' + f(F.f[n], 1) + ' (last actual ' + f(F.last, 1) + '), with a 95% interval of ' + f(F.lo95[n], 1) + ' to ' + f(F.hi95[n], 1) +
      '. The forecast barely moves; the width of the band is the real message. Six months out, a price anywhere in that range would be normal.';
  }
  function renderTimeseries() {
    var S = D.timeseries, o = base();
    o.tooltip = { trigger: 'axis', confine: true, valueFormatter: function (v) { return f(v, 1); } };
    o.xAxis = { type: 'category', data: S.seasonal.month.map(function (m) { return MON[m - 1]; }), axisLabel: { color: C.muted } };
    o.yAxis = yVal(function (v) { return v.toFixed(1); });
    o.series = [['Coarse rice', S.seasonal.rice, C.blue], ['Lentils', S.seasonal.lentil, C.orange], ['Staple index', S.seasonal.index, C.text]].map(function (s) {
      return { name: s[0], type: 'line', data: s[1], symbol: 'circle', symbolSize: 5, lineStyle: { width: 2, color: s[2] }, itemStyle: { color: s[2] } };
    });
    o.series[0].markLine = { symbol: 'none', silent: true, lineStyle: { color: C.muted, type: 'dashed', width: 1 }, label: { show: false }, data: [{ yAxis: 100 }] };
    chart('c-seas').setOption(o);
    var r = S.seasonal.rice, mx = r.indexOf(Math.max.apply(null, r)), mn = r.indexOf(Math.min.apply(null, r));
    document.getElementById('seas-note').innerHTML = '<strong>How to read this:</strong> rice is ' + f(r[mx] - 100, 1) + '% above its trend in ' + MON[mx] + ' and ' + f(100 - r[mn], 1) + '% below in ' + MON[mn] +
      '. The pattern is small: STL puts rice\'s seasonal strength at ' + f(S.strength.rice_coarse[0], 2) + ' on a 0 to 1 scale.';
    document.getElementById('sel-trend').addEventListener('change', renderTrend); renderTrend();
    document.getElementById('sel-fc').addEventListener('change', renderForecast); renderForecast();

    var nm = { rice_coarse: 'Coarse rice', staple_index: 'Staple index' }, mm = { ets: 'ETS', sarima: 'SARIMA', seasonal_naive: 'Seasonal naive' };
    document.querySelector('#t-bt tbody').innerHTML = S.backtest.map(function (b) {
      var best = S.backtest.filter(function (x) { return x[0] === b[0]; }).reduce(function (a, x) { return x[4] < a[4] ? x : a; });
      return '<tr' + (best === b ? ' class="chosen"' : '') + '><td>' + nm[b[0]] + '</td><td>' + mm[b[1]] + (best === b ? '<span class="badge">best</span>' : '') + '</td><td class="num">' + f(b[2], 2) + '%</td><td class="num">' + f(b[3], 2) + '%</td><td class="num">' + f(b[4], 3) + '</td><td class="num">' + f(b[5], 3) + '</td></tr>';
    }).join('');

    var V = S.volatility.slice().reverse(), o2 = base();
    o2.legend = { show: false }; o2.grid.top = 8; o2.grid.right = 44;
    o2.tooltip = { trigger: 'axis', confine: true, formatter: function (ps) { var v = V[ps[0].dataIndex]; return esc(v[1]) + '<br>SD of monthly change <b>' + f(v[2], 1) + '%</b><br>Largest rise ' + f(v[4], 1) + '%, largest fall ' + f(v[5], 1) + '%<br>' + v[3] + ' monthly changes' + (v[6] != null ? '<br>2007-2026 SD: ' + f(v[6], 1) + '%' : ''); } };
    o2.yAxis = { type: 'category', data: V.map(function (v) { return v[1]; }), axisLabel: { color: C.muted, fontSize: 11 } };
    o2.xAxis = yVal(function (v) { return v + '%'; }); o2.xAxis.scale = false;
    o2.series = [{ type: 'bar', name: 'SD', data: V.map(function (v) { return { value: v[2], itemStyle: { color: v[6] != null ? C.blue : C.orange } }; }),
      label: { show: true, position: 'right', color: C.muted, fontSize: 11, formatter: function (p) { return f(p.value, 1) + '%'; } } }];
    chart('c-vol').setOption(o2);

    var RV = S.rolling, o3 = base(), nmap = { rice_coarse: ['Coarse rice', C.blue], atta: ['Atta', C.orange], lentil_masur: ['Lentils', C.green], palm_oil: ['Palm oil', C.off] };
    o3.tooltip = axisTip(function (v) { return f(v, 1) + '%'; });
    o3.xAxis = dateAxis(RV.months);
    o3.yAxis = yVal(function (v) { return v + '%'; }); o3.yAxis.scale = false;
    o3.series = Object.keys(RV.series).map(function (k) { return { name: nmap[k][0], type: 'line', data: RV.series[k], symbol: 'none', lineStyle: { width: 1.6, color: nmap[k][1] }, itemStyle: { color: nmap[k][1] } }; });
    chart('c-roll').setOption(o3);
    var pk = S.peak_rolling.split(' ');
    document.getElementById('roll-note').innerHTML = '<strong>How to read this:</strong> each point is the SD of the previous 12 monthly changes. The peak was palm oil in ' + monthName(pk[1]) + ' (' + pk[2] + '%). Blue bars on the left chart are the long-basket staples; orange bars are items tracked only since 2024, where vegetables swing far more than grains.';
  }

  // ---------- Bayesian decision (same formulas as src/bayes_decision.py) ----------
  var B = null, ST = {};
  function payoff(P0, gS, gN, r, s, m, Q, H) {
    var c = r / 12 + s, fwd = 0, ms = 0, mn = 0;
    for (var k = 1; k <= H; k++) { fwd += Q * P0 * (1 + k * c); ms += Q * P0 * (1 + m * (gS[k - 1] - 1)); mn += Q * P0 * gN[k - 1]; }
    return { fwd: fwd, ms: ms, mn: mn, savS: ms - fwd, savN: mn - fwd, carry: c };
  }
  function emv(pay, p) { return { fwd: pay.fwd, mon: p * pay.ms + (1 - p) * pay.mn }; }
  function minE(e) { return Math.min(e.fwd, e.mon); }
  function solve(inp) {
    var X = D.bayes, sg = X.signals.filter(function (s) { return s.x === inp.x; })[0];
    var pay = payoff(X.P0, X.growth_spike, X.growth_none, inp.r, inp.s, inp.m, X.qty, X.H);
    var prior = X.n_spike / X.n_train, l1 = sg.l1, l0 = sg.l0;
    var pSig = prior * l1 + (1 - prior) * l0;
    var postOn = prior * l1 / pSig, postOff = prior * (1 - l1) / (1 - pSig);
    var be = pay.savS === pay.savN ? NaN : -pay.savN / (pay.savS - pay.savN);
    var evpi = minE(emv(pay, prior)) - (prior * Math.min(pay.fwd, pay.ms) + (1 - prior) * Math.min(pay.fwd, pay.mn));
    var evsi = minE(emv(pay, prior)) - (pSig * minE(emv(pay, postOn)) + (1 - pSig) * minE(emv(pay, postOff)));
    return { pay: pay, prior: prior, l1: l1, l0: l0, pSig: pSig, postOn: postOn, postOff: postOff, be: be, evpi: evpi, evsi: evsi, sig: sg };
  }
  window.__bayes = function (inp) { var X = D.bayes.base; return solve(inp || { r: X.r, s: X.s, m: X.m, x: X.x }); };

  function readInputs() {
    return { r: +document.getElementById('s-rate').value / 100, s: +document.getElementById('s-store').value / 100, m: +document.getElementById('s-mult').value, x: ST.x, obs: ST.obs };
  }
  function setSeg(id, v) { document.querySelectorAll('#' + id + ' button').forEach(function (b) { b.setAttribute('aria-checked', b.getAttribute('data-v') === String(v)); }); }

  function recompute() {
    var inp = readInputs(), R = solve(inp), X = D.bayes, pay = R.pay;
    document.getElementById('o-rate').textContent = f(inp.r * 100, 2) + '%';
    document.getElementById('o-store').textContent = f(inp.s * 100, 2) + '%';
    document.getElementById('o-mult').textContent = f(inp.m, 2) + '×';
    var post = inp.obs === 'on' ? R.postOn : R.postOff, e = emv(pay, post), fwd = e.fwd < e.mon;
    document.getElementById('kpis-b').innerHTML = [
      kpiCard('Prior P(spike)', f(R.prior, 3), X.n_spike + ' of ' + X.n_train + ' months, 2007-2019', C.muted),
      kpiCard('Posterior, signal ' + inp.obs, f(post, 3), 'after the world-price signal', inp.obs === 'on' ? C.off : C.blue),
      kpiCard('Breakeven P(spike)', f(R.be, 3), 'forward pays above this', C.text),
      kpiCard('EVPI', bdt(R.evpi), 'per 3,000 L decision', C.green),
      kpiCard('EVSI of the signal', bdt(R.evsi), pct(R.evpi > 0 ? R.evsi / R.evpi : 0, 1) + ' of EVPI', C.sky)
    ].join('');
    var box = document.getElementById('dec-box');
    box.className = 'decision-box ' + (fwd ? 'fwd' : 'mon');
    box.innerHTML = '<span>Decision with the signal ' + inp.obs + ':</span> <strong>' + (fwd ? 'buy forward' : 'buy monthly') + '</strong><br><small>Expected cost: forward ' + bdt(e.fwd) + ', monthly ' + bdt(e.mon) + ' for 3,000 L. ' +
      (fwd ? 'Forward' : 'Monthly') + ' saves ' + bdt(Math.abs(e.fwd - e.mon)) + ' in expectation. P(spike) = ' + f(post, 3) + (post > R.be ? ' is above' : ' is below') + ' the breakeven ' + f(R.be, 3) + '.</small>';

    // EMV lines
    var ps = [], cf = [], cm = [];
    for (var i = 0; i <= 120; i++) { var p = i / 200; ps.push(p); var ee = emv(pay, p); cf.push([p, ee.fwd / 3000]); cm.push([p, ee.mon / 3000]); }
    var o = base();
    o.grid.top = 40;
    o.tooltip = { trigger: 'axis', confine: true, formatter: function (a) { var out = 'P(spike) = ' + f(a[0].value[0], 3); a.forEach(function (q) { if (q.seriesName.indexOf('_') !== 0) out += '<br>' + q.marker + esc(q.seriesName) + ': <b>Tk ' + f(q.value[1], 2) + '</b>/L'; }); return out; } };
    o.xAxis = { type: 'value', min: 0, max: 0.6, name: 'P(spike next month)', nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: C.muted }, axisLabel: { color: C.muted, formatter: function (v) { return v.toFixed(1); } }, splitLine: { lineStyle: { color: C.grid } } };
    o.yAxis = yVal(function (v) { return v.toFixed(0); });
    var vl = function (x, lab, col, pos) { return { xAxis: x, lineStyle: { color: col, type: 'dotted', width: 1.4 }, label: { formatter: lab, color: col, fontSize: 10, position: pos || 'insideEndTop' } }; };
    o.series = [
      { name: 'Forward buy (A1)', type: 'line', data: cf, symbol: 'none', lineStyle: { width: 2.4, color: C.off }, itemStyle: { color: C.off },
        markLine: { symbol: 'none', silent: true, data: [
          { xAxis: R.be, lineStyle: { color: C.text, type: 'dashed', width: 1.2 }, label: { formatter: 'breakeven ' + f(R.be, 3), color: C.text, fontSize: 11, position: 'insideEndTop' } },
          vl(R.prior, 'prior', C.muted, 'insideStartTop'), vl(R.postOn, 'signal on', C.off, 'insideStartTop'), vl(R.postOff, 'off', C.blue, 'insideStartBottom')] } },
      { name: 'Buy monthly (A2)', type: 'line', data: cm, symbol: 'none', lineStyle: { width: 2.4, color: C.blue }, itemStyle: { color: C.blue } }
    ];
    if (!(R.be >= 0 && R.be <= 0.6)) o.series[0].markLine.data.shift();
    chart('c-emv').setOption(o, true);

    var tb = function (on) {
      var l1 = on ? R.l1 : 1 - R.l1, l0 = on ? R.l0 : 1 - R.l0, j1 = R.prior * l1, j0 = (1 - R.prior) * l0, t = j1 + j0;
      return [['Spike next month', R.prior, l1, j1, j1 / t], ['No spike', 1 - R.prior, l0, j0, j0 / t], ['Total = P(signal ' + (on ? 'on' : 'off') + ')', 1, null, t, 1]];
    };
    var rows = tb(inp.obs === 'on');
    document.querySelector('#t-bayes tbody').innerHTML = rows.map(function (r, i) {
      return '<tr' + (i === 0 ? ' class="chosen"' : '') + '><td>' + r[0] + '</td><td class="num">' + f(r[1], 3) + '</td><td class="num">' + (r[2] == null ? '' : f(r[2], 3)) + '</td><td class="num">' + f(r[3], 4) + '</td><td class="num">' + f(r[4], 3) + '</td></tr>';
    }).join('');
    document.getElementById('bt-hint').textContent = 'Signal ' + inp.obs + ', threshold ' + f(inp.x, 0) + '%';
    document.getElementById('bayes-note').innerHTML = '<strong>How to read this:</strong> likelihood is P(signal ' + inp.obs + ' | state) from 2007-2019. With a ' + f(inp.x, 0) + '% threshold the signal fired in ' + pct(R.l1, 1) + ' of pre-spike months and ' + pct(R.l0, 1) +
      ' of other months. Joint = prior × likelihood; posterior = joint ÷ total. On the 2020-2025 test this threshold fired ' + R.sig.test_months + ' times and the rule cost ' + sgn(R.sig.test_pct, 2) + '% vs buying monthly (base-case costs).';

    document.querySelector('#t-pay tbody').innerHTML = [['Spike next month', pay.fwd, pay.ms, pay.savS], ['No spike', pay.fwd, pay.mn, pay.savN]].map(function (r) {
      return '<tr><td>' + r[0] + '</td><td class="num">' + bdt(r[1]) + '</td><td class="num">' + bdt(r[2]) + '</td><td class="num ' + (r[3] < 0 ? 'neg' : 'pos') + '">' + bdt(r[3]) + '</td></tr>';
    }).join('');
    document.getElementById('pay-note').innerHTML = '<strong>How to read this:</strong> forward buying costs the price now (Tk ' + f(X.P0, 2) + '/L) plus ' + f(pay.carry * 100, 2) + '% a month in financing and storage for each month a litre is held. Monthly buying pays the average 2007-2019 price path after a spike (+' +
      f((1 + inp.m * (X.growth_spike[2] - 1) - 1) * 100, 1) + '% by month 3) or after no spike (' + f((X.growth_none[2] - 1) * 100, 1) + '%).';
    var P = X.published, base0 = solve({ r: X.base.r, s: X.base.s, m: X.base.m, x: X.base.x });
    var ok = function (a, b, tol) { return Math.abs(a - b) <= tol ? '<b class="ok">✓</b>' : '<b class="neg">✗</b>'; };
    document.getElementById('checks').innerHTML = 'Base case recomputed in your browser vs notebook 06: prior ' + f(base0.prior, 3) + ' ' + ok(base0.prior, P.prior, 5e-4) + ', posterior ' + f(base0.postOn, 3) + ' ' + ok(base0.postOn, P.post_on, 5e-4) +
      ', breakeven ' + f(base0.be, 3) + ' ' + ok(base0.be, P.breakeven, 5e-4) + ', EVPI ' + bdt(base0.evpi) + ' ' + ok(base0.evpi, P.evpi, 1) + ', EVSI ' + bdt(base0.evsi) + ' ' + ok(base0.evsi, P.evsi, 1) + '.';
  }

  function renderBayes() {
    var X = D.bayes, b = X.base;
    document.getElementById('p0').textContent = 'Tk ' + f(X.P0, 2) + ' per litre';
    document.getElementById('seg-x').innerHTML = X.signals.map(function (s) { return '<button type="button" role="radio" data-v="' + s.x + '">' + f(s.x, 0) + '%</button>'; }).join('');
    document.querySelectorAll('#seg-x button').forEach(function (bt) { bt.addEventListener('click', function () { ST.x = +bt.getAttribute('data-v'); setSeg('seg-x', ST.x); recompute(); }); });
    document.querySelectorAll('#seg-obs button').forEach(function (bt) { bt.addEventListener('click', function () { ST.obs = bt.getAttribute('data-v'); setSeg('seg-obs', ST.obs); recompute(); }); });
    ['s-rate', 's-store', 's-mult'].forEach(function (id) { document.getElementById(id).addEventListener('input', recompute); });
    function reset() {
      document.getElementById('s-rate').value = b.r * 100; document.getElementById('s-store').value = b.s * 100; document.getElementById('s-mult').value = b.m;
      ST.x = b.x; ST.obs = 'on'; setSeg('seg-x', ST.x); setSeg('seg-obs', ST.obs); recompute();
    }
    document.getElementById('b-reset').addEventListener('click', reset);
    reset();

    var Cu = X.cum, o = base();
    o.tooltip = axisTip(function (v) { return 'Tk ' + f(v, 2) + 'm'; });
    o.xAxis = dateAxis(Cu.months, 1);
    o.yAxis = yVal(function (v) { return v.toFixed(1) + 'm'; }); o.yAxis.scale = false;
    o.series = [['Bayes rule', Cu.bayes, C.green, 2.4], ['Always forward', Cu.forward, C.off, 1.4], ['Perfect foresight', Cu.oracle, C.muted, 1.2]].map(function (s) {
      return { name: s[0], type: 'line', data: s[1], symbol: 'none', lineStyle: { width: s[3], color: s[2], type: s[0] === 'Perfect foresight' ? 'dashed' : 'solid' }, itemStyle: { color: s[2] } };
    });
    o.series[0].markLine = { symbol: 'none', silent: true, lineStyle: { color: C.text, width: 1 }, label: { show: false }, data: [{ yAxis: 0 }] };
    chart('c-cum').setOption(o);
    document.querySelector('#t-btb tbody').innerHTML = X.backtest.map(function (r) {
      return '<tr' + (r[0] === 'Bayes rule' ? ' class="chosen"' : '') + '><td>' + esc(r[0]) + '</td><td class="num">' + f(r[1] / 1e6, 2) + '</td><td class="num ' + (r[3] < 0 ? 'pos' : r[3] > 0 ? 'neg' : '') + '">' + sgn(r[3], 2) + '%</td><td class="num">' + sgn(r[4], 2) + '</td></tr>';
    }).join('');
    var bf = X.bt_facts;
    document.getElementById('btb-note').innerHTML = '<strong>How to read this:</strong> cumulative saving over always buying monthly, Tk million, ' + bf.n + ' decision months. The signal fired ' + bf.signal_months + ' times and the rule bought forward each time; ' +
      esc(bf.fwd_note.replace(/^Months the rule said forward buy; /, '')) + '. Spikes came more often than in training (' + pct(bf.spike_rate, 1) + ' of months vs ' + pct(X.n_spike / X.n_train, 1) + ').';

    var Bt = X.beta, o2 = base();
    o2.tooltip = { trigger: 'axis', confine: true, formatter: function (a) { var out = 'θ = ' + f(a[0].value[0], 3); a.forEach(function (q) { out += '<br>' + q.marker + esc(q.seriesName) + ': ' + f(q.value[1], 2); }); return out; } };
    o2.xAxis = { type: 'value', min: 0, max: 0.4, name: 'Monthly spike rate θ', nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: C.muted }, axisLabel: { color: C.muted, formatter: function (v) { return v.toFixed(1); } }, splitLine: { lineStyle: { color: C.grid } } };
    o2.yAxis = yVal(function (v) { return v.toFixed(0); }); o2.yAxis.scale = false;
    o2.series = Bt.dens.map(function (d, j) {
      var st = Bt.stages[j + 1], col = j === 0 ? C.blue : C.off;
      return { name: st[0], type: 'line', data: d.map(function (v, i) { return [Bt.theta[i], v]; }), symbol: 'none', lineStyle: { width: 2, color: col }, itemStyle: { color: col },
        areaStyle: { color: col, opacity: 0.08 },
        markArea: { silent: true, itemStyle: { color: col, opacity: 0.08 }, data: [[{ xAxis: st[4] }, { xAxis: st[5] }]] } };
    });
    o2.series[0].markLine = { symbol: 'none', silent: true, lineStyle: { color: C.text, type: 'dashed', width: 1 }, label: { formatter: 'breakeven', color: C.text, fontSize: 11 }, data: [{ xAxis: X.published.breakeven }] };
    chart('c-beta').setOption(o2);
    document.querySelector('#t-beta tbody').innerHTML = Bt.stages.map(function (s) {
      return '<tr><td>' + esc(s[0]) + '</td><td class="num">Beta(' + s[1] + ', ' + s[2] + ')</td><td class="num">' + f(s[3], 3) + '</td><td class="num">' + f(s[4], 3) + ' to ' + f(s[5], 3) + '</td></tr>';
    }).join('');
    var s2 = Bt.stages[2];
    document.getElementById('beta-note').innerHTML = '<strong>How to read this:</strong> starting from a flat prior, the 2007-2019 record gives a mean spike rate of ' + f(Bt.stages[1][3], 3) + '. Adding 2020-2025 moves it to ' + f(s2[3], 3) + ' (95% credible interval ' + f(s2[4], 3) + ' to ' + f(s2[5], 3) +
      '). The whole interval sits well below the breakeven, so without a signal, buying monthly stays the better choice.';
  }

  var RENDER = { overview: renderOverview, prices: renderPrices, tests: renderTests, regression: renderRegression, timeseries: renderTimeseries, bayes: renderBayes };
  var ALIAS = { indices: 'prices', index: 'prices', hypothesis: 'tests', contingency: 'tests', ts: 'timeseries', forecast: 'timeseries', decision: 'bayes', calculator: 'bayes' };
  function tabFor(h) { return document.getElementById('tab-' + (ALIAS[h] || h)); }

  // ---------- load ----------
  Promise.all(['overview', 'prices', 'tests', 'regression', 'timeseries', 'bayes'].map(function (n) {
    return fetch('data/' + n + '.json').then(function (r) { if (!r.ok) throw new Error(n + ': ' + r.status); return r.json(); }).then(function (j) { D[n] = j; });
  })).then(function () {
    document.getElementById('loading').remove();
    document.getElementById('gen').textContent = 'Data built ' + D.overview.generated;
    var h = location.hash.slice(1), t = tabFor(h);
    show(t || tabs[0]);
  }).catch(function (err) {
    document.getElementById('loading').textContent = 'Could not load data (' + err.message + ').';
  });
})();
