"""
HTML report generator.

Produces a fully self-contained interactive dashboard from the SQLite data.
No external runtime dependencies — everything is embedded or loaded from CDN.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from src import database as db
from src.config import REPORT_PATH


# ── HTML template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>European Fintech Investment Tracker</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {{ --accent: #6366f1; }}
    body {{ font-family: 'Inter', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:9999px; font-size:11px; font-weight:600; }}
    .stage-seed     {{ background:#7c3aed22; color:#a78bfa; border:1px solid #7c3aed44; }}
    .stage-a        {{ background:#2563eb22; color:#93c5fd; border:1px solid #2563eb44; }}
    .stage-b        {{ background:#059669'22; color:#6ee7b7; border:1px solid #05966944; }}
    .stage-c        {{ background:#d9770622; color:#fcd34d; border:1px solid #d9770644; }}
    .stage-growth   {{ background:#dc262622; color:#fca5a5; border:1px solid #dc262644; }}
    .stage-pe       {{ background:#71717a22; color:#d4d4d8; border:1px solid #71717a44; }}
    .stage-other    {{ background:#0f172a;   color:#94a3b8; border:1px solid #334155;  }}
    .detail-panel   {{ display:none; }}
    .detail-panel.open {{ display:block; }}
    input, select   {{ background:#0f172a; border:1px solid #334155; color:#e2e8f0; border-radius:6px; padding:6px 10px; }}
    input:focus, select:focus {{ outline: 2px solid #6366f1; border-color:transparent; }}
    th {{ cursor:pointer; user-select:none; }}
    th:hover {{ color:#a5b4fc; }}
    tr.inv-row:hover {{ background:#1e3a5f33; cursor:pointer; }}
    .chip {{ background:#1e293b; border:1px solid #334155; border-radius:6px; padding:2px 7px; font-size:11px; color:#94a3b8; display:inline-block; margin:2px; }}
    .metric-badge {{ background:#1e3a5f; border:1px solid #2563eb44; border-radius:6px; padding:3px 8px; font-size:11px; color:#93c5fd; display:inline-block; margin:2px; }}
    .stat-card {{ text-align:center; padding:20px; }}
    .stat-num  {{ font-size:2.2rem; font-weight:700; color:#a5b4fc; }}
    .stat-lbl  {{ font-size:0.8rem; color:#64748b; margin-top:4px; letter-spacing:.05em; text-transform:uppercase; }}
    #search-box {{ width:220px; }}
    .sort-asc::after  {{ content:' ↑'; color:#6366f1; }}
    .sort-desc::after {{ content:' ↓'; color:#6366f1; }}
  </style>
</head>
<body class="p-4 md:p-8">

<!-- Header -->
<div class="mb-8">
  <h1 class="text-3xl font-bold text-white mb-1">
    🇪🇺 European Fintech Investment Tracker
  </h1>
  <p class="text-slate-400 text-sm">
    Powered by Claude Opus 4.6 · Last updated: <span id="last-updated">{last_updated}</span>
  </p>
</div>

<!-- Summary Stats -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
  <div class="card stat-card">
    <div class="stat-num" id="s-total">{total_investments}</div>
    <div class="stat-lbl">Investment Rounds</div>
  </div>
  <div class="card stat-card">
    <div class="stat-num" id="s-capital">{total_eur_billions}</div>
    <div class="stat-lbl">Total Capital (EUR)</div>
  </div>
  <div class="card stat-card">
    <div class="stat-num" id="s-countries">{total_countries}</div>
    <div class="stat-lbl">Countries</div>
  </div>
  <div class="card stat-card">
    <div class="stat-num" id="s-visible">–</div>
    <div class="stat-lbl">Matching Filters</div>
  </div>
</div>

<!-- Charts Row -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
  <div class="card p-4">
    <h3 class="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wide">By Stage</h3>
    <canvas id="chart-stage" height="220"></canvas>
  </div>
  <div class="card p-4">
    <h3 class="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wide">By Country</h3>
    <canvas id="chart-country" height="220"></canvas>
  </div>
  <div class="card p-4">
    <h3 class="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wide">By Tech Focus</h3>
    <canvas id="chart-tech" height="220"></canvas>
  </div>
</div>

<!-- Filters -->
<div class="card p-4 mb-4 flex flex-wrap gap-3 items-end">
  <div>
    <label class="block text-xs text-slate-400 mb-1">Search</label>
    <input id="search-box" type="text" placeholder="Company, investor…" oninput="applyFilters()" />
  </div>
  <div>
    <label class="block text-xs text-slate-400 mb-1">Stage</label>
    <select id="f-stage" onchange="applyFilters()"><option value="">All</option></select>
  </div>
  <div>
    <label class="block text-xs text-slate-400 mb-1">Round Type</label>
    <select id="f-type" onchange="applyFilters()"><option value="">All</option></select>
  </div>
  <div>
    <label class="block text-xs text-slate-400 mb-1">Country</label>
    <select id="f-country" onchange="applyFilters()"><option value="">All</option></select>
  </div>
  <div>
    <label class="block text-xs text-slate-400 mb-1">Tech Focus</label>
    <select id="f-tech" onchange="applyFilters()"><option value="">All</option></select>
  </div>
  <button onclick="clearFilters()"
    class="px-3 py-1.5 text-sm rounded bg-slate-700 hover:bg-slate-600 text-slate-300 transition">
    Clear
  </button>
</div>

<!-- Table -->
<div class="card overflow-hidden mb-8">
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-slate-700 text-slate-400 text-xs uppercase tracking-wide">
          <th class="text-left px-4 py-3" onclick="sortTable('company_name')">Company</th>
          <th class="text-left px-4 py-3" onclick="sortTable('country')">Country</th>
          <th class="text-left px-4 py-3" onclick="sortTable('stage')">Stage</th>
          <th class="text-left px-4 py-3" onclick="sortTable('round_type')">Type</th>
          <th class="text-right px-4 py-3" onclick="sortTable('amount_raised_eur_millions')">Raised (EUR)</th>
          <th class="text-right px-4 py-3" onclick="sortTable('post_money_valuation_eur_m')">Valuation</th>
          <th class="text-left px-4 py-3" onclick="sortTable('deal_date')">Date</th>
          <th class="text-left px-4 py-3">Lead Investor(s)</th>
          <th class="text-left px-4 py-3">Focus</th>
        </tr>
      </thead>
      <tbody id="inv-body"></tbody>
    </table>
  </div>
  <div id="no-results" class="hidden text-center py-12 text-slate-500">
    No investments match the current filters.
  </div>
</div>

<!-- Detail Modal -->
<div id="modal-overlay"
     class="fixed inset-0 bg-black/60 flex items-start justify-center pt-10 z-50 hidden"
     onclick="closeModal(event)">
  <div class="card w-full max-w-3xl mx-4 mb-10 overflow-y-auto max-h-[85vh]" onclick="event.stopPropagation()">
    <div class="flex justify-between items-start p-5 border-b border-slate-700">
      <div>
        <h2 id="modal-company" class="text-xl font-bold text-white"></h2>
        <p id="modal-meta" class="text-sm text-slate-400 mt-0.5"></p>
      </div>
      <button onclick="closeModal()" class="text-slate-400 hover:text-white text-xl leading-none">✕</button>
    </div>
    <div class="p-5 space-y-5">
      <div>
        <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Company Summary</h3>
        <p id="modal-summary" class="text-slate-300 leading-relaxed"></p>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div>
          <div class="text-xs text-slate-500 mb-1">Amount Raised</div>
          <div id="modal-amount" class="text-white font-semibold text-lg"></div>
          <div id="modal-amount-orig" class="text-slate-400 text-xs"></div>
        </div>
        <div>
          <div class="text-xs text-slate-500 mb-1">Valuation</div>
          <div id="modal-valuation" class="text-white font-semibold"></div>
        </div>
        <div>
          <div class="text-xs text-slate-500 mb-1">Stage / Type</div>
          <div id="modal-stage" class="text-white font-semibold"></div>
        </div>
        <div>
          <div class="text-xs text-slate-500 mb-1">Location</div>
          <div id="modal-location" class="text-white"></div>
        </div>
        <div>
          <div class="text-xs text-slate-500 mb-1">Customer Segment</div>
          <div id="modal-segment" class="text-white"></div>
        </div>
        <div>
          <div class="text-xs text-slate-500 mb-1">Founded</div>
          <div id="modal-founded" class="text-white"></div>
        </div>
      </div>
      <div>
        <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Investors</h3>
        <div class="space-y-1">
          <div id="modal-lead-inv" class="text-sm text-slate-300"></div>
          <div id="modal-new-inv" class="text-sm text-slate-300"></div>
          <div id="modal-exist-inv" class="text-sm text-slate-300"></div>
        </div>
      </div>
      <div id="modal-metrics-section">
        <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Key Metrics</h3>
        <div id="modal-metrics" class="flex flex-wrap gap-1"></div>
      </div>
      <div id="modal-focus-section">
        <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Technology Focus</h3>
        <div id="modal-focus" class="flex flex-wrap gap-1"></div>
      </div>
      <div id="modal-funds-section">
        <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Use of Funds</h3>
        <p id="modal-funds" class="text-slate-300 text-sm"></p>
      </div>
      <div id="modal-notable-section">
        <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Notable Details</h3>
        <p id="modal-notable" class="text-slate-300 text-sm"></p>
      </div>
      <div class="border-t border-slate-700 pt-4">
        <a id="modal-source" href="#" target="_blank" rel="noopener"
           class="text-indigo-400 hover:text-indigo-300 text-sm underline">
          Read Original Article ↗
        </a>
      </div>
    </div>
  </div>
</div>

<script>
// ── Data ─────────────────────────────────────────────────────────────────────
const ALL_DATA = {investments_json};

// ── State ────────────────────────────────────────────────────────────────────
let sortKey = 'deal_date';
let sortAsc = false;
let visibleData = [...ALL_DATA];

// ── Utilities ────────────────────────────────────────────────────────────────
const fmt = (v, unit='') => v != null ? v.toLocaleString() + unit : '–';
const fmtM = v => v != null ? (v >= 1000 ? `€${{(v/1000).toFixed(1)}}B` : `€${{v.toFixed(0)}}M`) : '–';

function stageClass(stage) {{
  const s = (stage||'').toLowerCase();
  if (s.includes('seed')) return 'stage-seed';
  if (s.includes('series a')) return 'stage-a';
  if (s.includes('series b')) return 'stage-b';
  if (s.includes('series c') || s.includes('series d') || s.includes('series e')) return 'stage-c';
  if (s.includes('growth')) return 'stage-growth';
  if (s.includes('private equity') || s.includes('pe')) return 'stage-pe';
  return 'stage-other';
}}

function invText(label, arr) {{
  if (!arr || !arr.length) return '';
  return `<span class="text-slate-500">${{label}}:</span> ${{arr.join(', ')}}`;
}}

// ── Populate filter dropdowns ────────────────────────────────────────────────
function populateFilters() {{
  const stages   = [...new Set(ALL_DATA.map(d => d.stage).filter(Boolean))].sort();
  const types    = [...new Set(ALL_DATA.map(d => d.round_type).filter(Boolean))].sort();
  const countries= [...new Set(ALL_DATA.map(d => d.country).filter(Boolean))].sort();
  const techs    = [...new Set(ALL_DATA.flatMap(d => d.technology_focus || []))].sort();

  const fill = (id, opts) => {{
    const el = document.getElementById(id);
    opts.forEach(o => {{ const opt = document.createElement('option'); opt.value = opt.textContent = o; el.appendChild(opt); }});
  }};
  fill('f-stage', stages);
  fill('f-type', types);
  fill('f-country', countries);
  fill('f-tech', techs);
}}

// ── Filtering ────────────────────────────────────────────────────────────────
function applyFilters() {{
  const q       = document.getElementById('search-box').value.toLowerCase();
  const stage   = document.getElementById('f-stage').value;
  const type    = document.getElementById('f-type').value;
  const country = document.getElementById('f-country').value;
  const tech    = document.getElementById('f-tech').value;

  visibleData = ALL_DATA.filter(d => {{
    if (stage   && d.stage       !== stage)   return false;
    if (type    && d.round_type  !== type)    return false;
    if (country && d.country     !== country) return false;
    if (tech    && !(d.technology_focus||[]).includes(tech)) return false;
    if (q) {{
      const blob = [
        d.company_name, d.country, d.city, d.company_summary,
        ...(d.lead_investors||[]), ...(d.new_investors||[]),
        ...(d.existing_investors||[]), ...(d.technology_focus||[]),
      ].join(' ').toLowerCase();
      if (!blob.includes(q)) return false;
    }}
    return true;
  }});

  renderTable();
  document.getElementById('s-visible').textContent = visibleData.length;
}}

function clearFilters() {{
  ['search-box','f-stage','f-type','f-country','f-tech'].forEach(id => {{
    const el = document.getElementById(id);
    el.tagName === 'SELECT' ? el.selectedIndex = 0 : (el.value = '');
  }});
  applyFilters();
}}

// ── Sorting ──────────────────────────────────────────────────────────────────
function sortTable(key) {{
  if (sortKey === key) sortAsc = !sortAsc;
  else {{ sortKey = key; sortAsc = true; }}

  // Update header indicators
  document.querySelectorAll('th').forEach(th => th.classList.remove('sort-asc','sort-desc'));
  const headers = ['company_name','country','stage','round_type','amount_raised_eur_millions','post_money_valuation_eur_m','deal_date','x','x2'];
  const idx = headers.indexOf(key);
  const ths = document.querySelectorAll('th');
  if (idx >= 0) ths[idx].classList.add(sortAsc ? 'sort-asc' : 'sort-desc');

  visibleData.sort((a,b) => {{
    const av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
    return sortAsc ? cmp : -cmp;
  }});
  renderTable();
}}

// ── Table render ─────────────────────────────────────────────────────────────
function renderTable() {{
  const tbody = document.getElementById('inv-body');
  tbody.innerHTML = '';

  if (visibleData.length === 0) {{
    document.getElementById('no-results').classList.remove('hidden');
    return;
  }}
  document.getElementById('no-results').classList.add('hidden');

  visibleData.forEach((d, idx) => {{
    const leads = (d.lead_investors||[]).join(', ') || (d.new_investors||[])[0] || '–';
    const focusTags = (d.technology_focus||[]).slice(0,2).map(f =>
      `<span class="chip">${{f}}</span>`).join('');

    const tr = document.createElement('tr');
    tr.className = 'inv-row border-b border-slate-800 transition-colors';
    tr.onclick = () => openModal(d);
    tr.innerHTML = `
      <td class="px-4 py-3">
        <div class="font-semibold text-white">${{d.company_name||'–'}}</div>
        <div class="text-xs text-slate-500">${{d.city||''}}</div>
      </td>
      <td class="px-4 py-3 text-slate-300">${{d.country||'–'}}</td>
      <td class="px-4 py-3">
        <span class="badge ${{stageClass(d.stage)}}">${{d.stage||'–'}}</span>
      </td>
      <td class="px-4 py-3 text-slate-400 text-xs">${{d.round_type||'–'}}</td>
      <td class="px-4 py-3 text-right font-mono font-semibold text-green-400">${{fmtM(d.amount_raised_eur_millions)}}</td>
      <td class="px-4 py-3 text-right font-mono text-slate-400">${{fmtM(d.post_money_valuation_eur_m)}}</td>
      <td class="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">${{d.deal_date||'–'}}</td>
      <td class="px-4 py-3 text-slate-300 text-xs max-w-[180px] truncate" title="${{leads}}">${{leads}}</td>
      <td class="px-4 py-3">${{focusTags}}</td>
    `;
    tbody.appendChild(tr);
  }});
}}

// ── Modal ────────────────────────────────────────────────────────────────────
function openModal(d) {{
  const $ = id => document.getElementById(id);
  $('modal-company').textContent = d.company_name || '–';
  $('modal-meta').textContent = [d.city, d.country, d.deal_date].filter(Boolean).join(' · ');
  $('modal-summary').textContent = d.company_summary || 'No summary available.';
  $('modal-amount').textContent = fmtM(d.amount_raised_eur_millions);
  $('modal-amount-orig').textContent = d.amount_raised_original || '';
  $('modal-valuation').textContent = d.valuation_stated || fmtM(d.post_money_valuation_eur_m) || '–';
  $('modal-stage').textContent = [d.stage, d.round_type].filter(Boolean).join(' · ') || '–';
  $('modal-location').textContent = [d.city, d.country].filter(Boolean).join(', ') || '–';
  $('modal-segment').textContent = d.customer_segment || '–';
  $('modal-founded').textContent = d.founding_year || '–';

  $('modal-lead-inv').innerHTML  = invText('Lead', d.lead_investors);
  $('modal-new-inv').innerHTML   = invText('New', d.new_investors);
  $('modal-exist-inv').innerHTML = invText('Existing', d.existing_investors);

  const metrics = d.key_metrics || {{}};
  const mEl = $('modal-metrics');
  mEl.innerHTML = '';
  if (Object.keys(metrics).length) {{
    Object.entries(metrics).forEach(([k,v]) => {{
      mEl.innerHTML += `<span class="metric-badge"><b>${{k}}</b>: ${{v}}</span>`;
    }});
    $('modal-metrics-section').style.display = '';
  }} else {{ $('modal-metrics-section').style.display = 'none'; }}

  const fEl = $('modal-focus');
  fEl.innerHTML = (d.technology_focus||[]).map(f => `<span class="chip">${{f}}</span>`).join('');
  $('modal-focus-section').style.display = (d.technology_focus||[]).length ? '' : 'none';

  $('modal-funds').textContent = d.use_of_funds || '';
  $('modal-funds-section').style.display = d.use_of_funds ? '' : 'none';

  $('modal-notable').textContent = d.notable_details || '';
  $('modal-notable-section').style.display = d.notable_details ? '' : 'none';

  $('modal-source').href = d.source_url || d.article_url || '#';
  $('modal-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}}

function closeModal(e) {{
  if (!e || e.target === document.getElementById('modal-overlay')) {{
    document.getElementById('modal-overlay').classList.add('hidden');
    document.body.style.overflow = '';
  }}
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

// ── Charts ───────────────────────────────────────────────────────────────────
const CHART_COLORS = [
  '#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444',
  '#ec4899','#14b8a6','#f97316','#84cc16','#a855f7','#0ea5e9',
];

function countBy(data, keyFn) {{
  const counts = {{}};
  data.forEach(d => {{
    const key = keyFn(d);
    if (key) counts[key] = (counts[key]||0) + 1;
  }});
  return Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, 10);
}}

function makeChart(canvasId, entries, label) {{
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'doughnut',
    data: {{
      labels: entries.map(e => e[0]),
      datasets: [{{ data: entries.map(e => e[1]), backgroundColor: CHART_COLORS, borderWidth: 0 }}],
    }},
    options: {{
      plugins: {{
        legend: {{ position:'bottom', labels: {{ color:'#94a3b8', font:{{ size:11 }}, boxWidth:12 }} }},
        tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{ctx.raw}}` }} }},
      }},
      cutout: '60%',
    }},
  }});
}}

function buildCharts() {{
  makeChart('chart-stage',   countBy(ALL_DATA, d => d.stage),   'Stage');
  makeChart('chart-country', countBy(ALL_DATA, d => d.country), 'Country');
  makeChart('chart-tech',    countBy(ALL_DATA, d => (d.technology_focus||[])[0]), 'Tech Focus');
}}

// ── Init ─────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {{
  populateFilters();
  applyFilters();
  buildCharts();
  // Default sort by date descending
  sortTable('deal_date');
  sortTable('deal_date');  // toggle back to desc
  document.getElementById('s-visible').textContent = ALL_DATA.length;
}});
</script>
</body>
</html>
"""


# ── Report generator ───────────────────────────────────────────────────────────

def generate_report(output_path: str = REPORT_PATH) -> str:
    """Build and write the HTML report. Returns the output path."""
    investments = db.get_all_investments()
    stats = db.investment_count()

    total_eur = stats.get("total_eur_millions") or 0.0
    if total_eur >= 1000:
        eur_display = f"€{total_eur/1000:.1f}B"
    else:
        eur_display = f"€{total_eur:.0f}M"

    last_updated = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    html = HTML_TEMPLATE.format(
        investments_json=json.dumps(investments, default=str, ensure_ascii=False),
        last_updated=last_updated,
        total_investments=len(investments),
        total_eur_billions=eur_display,
        total_countries=stats.get("countries") or 0,
    )

    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    return str(path.resolve())
