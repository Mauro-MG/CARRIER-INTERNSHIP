'use strict';

const charts = new Map();
const filterSelects = new Map();
let busy = false;
let currentView = null;
const $ = id => document.getElementById(id);
const palette = ['#0a84e8', '#8dc4f2', '#315f93', '#b8ddf8', '#6a9fd1'];

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function selectedFilters() {
  return Object.fromEntries([...filterSelects].map(([key, select]) => [key, select.value]));
}

function setBusy(value) {
  busy = value;
  document.body.classList.toggle('loading', value);
  document.querySelector('main').setAttribute('aria-busy', String(value));
  document.querySelectorAll('.header-actions button, #clear, #filters select').forEach(control => { control.disabled = value; });
}

async function load(action, filters = selectedFilters()) {
  if (busy) return;
  setBusy(true);
  $('error').hidden = true;
  $('status').textContent = action === 'render' ? 'Updating dashboard…' : action === 'state' ? 'Starting the dashboard…' : 'Loading data from Excel…';
  $('connection-badge').textContent = action === 'render' ? 'Updating…' : 'Loading…';
  try {
    const response = await fetch(`/api/${action}`, action === 'state' ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Dashboard-Request': '1' },
      body: JSON.stringify({ filters }),
    });
    const view = await response.json();
    if (!response.ok) throw new Error(view.error || 'Could not load the dashboard.');
    render(view);
    currentView = view;
    window.dispatchEvent(new CustomEvent('dashboard-loaded', { detail: view.connected }));
  } catch (error) {
    $('error').textContent = error.message;
    $('error').hidden = false;
    $('status').textContent = 'Could not load the dashboard. ' + (currentView?.connected ? 'The last loaded data is still displayed.' : 'Check Excel and try again.');
    // Restore selections to the data still displayed after a failed filter request.
    currentView?.filters.forEach(filter => { filterSelects.get(filter.key).value = filter.selected; });
  } finally {
    $('connection-badge').textContent = currentView?.connected ? 'Connected to Excel' : 'Not connected';
    $('connection-badge').classList.toggle('connected', Boolean(currentView?.connected));
    setBusy(false);
  }
}

function renderFilters(filters) {
  const holder = $('filters');
  holder.replaceChildren();
  filterSelects.clear();
  for (const filter of filters) {
    const area = element('div');
    const label = element('label', filter.label, 'filter-label');
    const select = element('select');
    select.id = `filter-${filter.key}`;
    label.htmlFor = select.id;
    for (const choice of filter.choices) select.add(new Option(choice, choice));
    select.value = filter.selected;
    select.addEventListener('change', () => load('render'));
    filterSelects.set(filter.key, select);
    area.append(label, select); holder.append(area);
  }
}

function chartOptions(key, data, connected) {
  const donut = key === 'gender';
  return {
    chart: { type: donut ? 'pie' : 'bar', backgroundColor: 'transparent',
      style: { fontFamily: 'Segoe UI, Arial, sans-serif' }, animation: false,
      spacing: [12, 8, 10, 0] },
    title: { text: null },
    credits: { enabled: true },
    colors: palette,
    accessibility: { description: `Interns by ${key}. Counts reflect the current filters.` },
    lang: { noData: connected ? 'No data available' : 'Connect to Excel to view data' },
    noData: { style: { color: '#64748b', fontSize: '11px', fontWeight: 'normal' } },
    xAxis: { categories: data.map(([label]) => label), lineWidth: 0, tickWidth: 0,
      labels: { style: { color: '#64748b', fontSize: '10px' } } },
    yAxis: { title: { text: null }, min: 0, allowDecimals: false, gridLineColor: '#f0f3f7',
      labels: { style: { color: '#94a3b8', fontSize: '9px' } } },
    legend: { enabled: donut, align: 'center', verticalAlign: 'bottom',
      labelFormat: '{name} · {y}',
      itemStyle: { color: '#64748b', fontSize: '10px', fontWeight: 'normal' },
      symbolRadius: 5, symbolHeight: 8, symbolWidth: 8 },
    tooltip: { headerFormat: '', pointFormat: '<b>{point.name}</b>: {point.y} interns', useHTML: false },
    plotOptions: {
      series: { animation: false, borderWidth: 0, dataLabels: { enabled: !donut,
        style: { color: '#112e51', fontSize: '10px', textOutline: 'none' } } },
      bar: { borderRadius: 3, maxPointWidth: 12, color: palette[0] },
      pie: { innerSize: '68%', size: '90%', borderWidth: 2, borderColor: '#fff',
        showInLegend: true, dataLabels: { enabled: false } },
    },
    series: [{ name: 'Interns', data: data.map(([name, y]) => ({ name, y })) }],
  };
}

function renderCharts(view) {
  for (const [key, data] of Object.entries(view.charts)) {
    charts.get(key)?.destroy();
    charts.set(key, Highcharts.chart(`chart-${key}`, chartOptions(key, data, view.connected)));
  }
}

function renderRecent(recent, connected) {
  const holder = $('recent');
  holder.replaceChildren();
  if (!recent.rows.length || !recent.columns.length) {
    const empty = element('div', undefined, 'empty-table');
    empty.append(element('p', connected ? 'No data available' : 'Your newest talent, at a glance.'),
      element('small', connected ? 'Try clearing the filters.' : 'Connect to Excel to view recent interns.'));
    holder.append(empty); return;
  }
  const table = element('table');
  table.setAttribute('aria-label', 'Recent interns');
  const head = element('thead');
  const header = element('tr');
  for (const column of recent.columns) {
    const cell = element('th', column); cell.scope = 'col'; header.append(cell);
  }
  head.append(header);
  const body = element('tbody');
  for (const row of recent.rows) {
    const tr = element('tr');
    for (const value of row) tr.append(element('td', value));
    body.append(tr);
  }
  table.append(head, body); holder.append(table);
}

function render(view) {
  renderFilters(view.filters);
  $('metrics').replaceChildren(...view.metrics.map(([label, value]) => {
    const card = element('article', undefined, 'metric');
    card.append(element('p', label, 'metric-label'), element('p', value, 'metric-value'), element('span', undefined, 'metric-accent'));
    return card;
  }));
  renderCharts(view);
  renderRecent(view.recent, view.connected);
  $('status').textContent = view.connected ? 'Connected to desktop Excel. Dashboard updates are local until Excel completes its SharePoint sync.' : 'Open the source workbook in Excel, then select Connect to Excel.';
  $('loaded').textContent = view.source ? `${view.source.records.toLocaleString()} records • ${view.source.sheet} • refreshed ${view.source.refreshedAt}` : 'Data not connected';
  $('source').hidden = !view.source;
  $('source').textContent = view.source ? `Source: ${view.source.path} • ${view.source.sheet}` : '';
}

$('connect').addEventListener('click', () => load('connect'));
$('refresh').addEventListener('click', () => load('refresh'));
$('clear').addEventListener('click', () => load('render', {}));
document.querySelectorAll('.nav-tab').forEach(tab => tab.addEventListener('click', () => {
  const view = tab.dataset.view;
  document.querySelectorAll('.app-view').forEach(section => { section.hidden = section.id !== view; });
  document.querySelectorAll('.nav-tab').forEach(button => {
    const selected = button === tab;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-selected', String(selected));
  });
  window.dispatchEvent(new CustomEvent('view-changed', { detail: view }));
}));
window.addEventListener('interns-updated', () => load('render'));
window.addEventListener('view-changed', event => {
  if (event.detail === 'dashboard-view') requestAnimationFrame(() => charts.forEach(chart => chart.reflow()));
});
if (typeof Highcharts === 'undefined') {
  $('error').textContent = 'Highcharts could not load. Run npm install in the app folder and restart.';
  $('error').hidden = false;
  $('status').textContent = 'Chart library unavailable.';
} else {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) Highcharts.setOptions({ plotOptions: { series: { animation: false } } });
  load('state');
}
