'use strict';

(() => {
  const get = id => document.getElementById(id);
  const make = (tag, text, className) => {
    const value = document.createElement(tag);
    if (text !== undefined) value.textContent = String(text);
    if (className) value.className = className;
    return value;
  };
  let listing = null;
  let page = 1;
  let queryRevision = 0;
  let searchTimer;
  let writing = false;
  let formState = null;
  let lastDay = '';

  async function api(url, method = 'GET', body) {
    const response = await fetch(url, method === 'GET' ? {} : {
      method, headers: { 'Content-Type': 'application/json', 'X-Dashboard-Request': '1' },
      body: JSON.stringify(body || {}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Could not load intern information.');
    }
    return data;
  }

  function errorAt(id, error) {
    get(id).textContent = error.message;
    get(id).hidden = false;
  }

  function query() {
    return new URLSearchParams({ search: get('intern-search').value, status: get('intern-status').value,
      sort: get('intern-sort').value, direction: get('intern-direction').value, page, pageSize: 25 });
  }

  async function loadList() {
    const revision = ++queryRevision;
    get('management-error').hidden = true;
    get('intern-table').setAttribute('aria-busy', 'true');
    try {
      const result = await api('/api/interns?' + query());
      if (revision !== queryRevision) return;
      listing = result;
      if (listing.connected && page > 1 && !listing.rows.length) { page = 1; return loadList(); }
      lastDay = listing.asOf || '';
      renderList();
    } catch (error) {
      if (revision === queryRevision) errorAt('management-error', error);
    } finally {
      if (revision === queryRevision) get('intern-table').setAttribute('aria-busy', 'false');
    }
  }

  function renderList() {
    const holder = get('intern-table');
    holder.replaceChildren();
    const schemaReady = Boolean(listing.schema?.ready);
    get('add-intern').disabled = !schemaReady || writing;
    get('prepare-workbook').hidden = schemaReady || !listing.connected;
    get('management-notice').hidden = !listing.connected || schemaReady;
    get('management-notice-text').textContent = 'Prepare the missing workbook fields to enable registration and editing.';
    get('intern-count').textContent = listing.connected ? `${listing.total} matching interns · ${listing.counts.Active || 0} active · ${listing.counts.Completed || 0} completed · ${listing.counts.Inactive || 0} inactive` : 'Connect to Excel to load the directory.';
    get('duration-date').textContent = listing.asOf ? `Durations as of ${listing.asOf} · updated automatically` : '';
    const pages = Math.max(1, Math.ceil((listing.total || 0) / 25));
    get('intern-page').textContent = `Page ${page} of ${pages}`;
    get('intern-previous').disabled = page <= 1 || writing;
    get('intern-next').disabled = page >= pages || writing;
    if (!listing.rows.length) {
      holder.append(make('p', listing.connected ? 'No interns match this view. Try another status or search.' : 'Open your source workbook in Excel and select Connect to Excel.', 'directory-empty'));
      return;
    }
    const table = make('table'); table.setAttribute('aria-label', 'Intern management');
    const columns = [['name', 'Full name'], ['status', 'Status'], ['duration', 'Months as Intern'],
      ['start_date', 'Start date'], ['end_date', 'End date'], ['department', 'Department / team'],
      ['role', 'Role'], ['supervisor', 'Supervisor'], ['university', 'University'], ['career', 'Degree / program'], ['semester', 'Semester']];
    const head = make('thead'), header = make('tr');
    for (const [, label] of columns) { const th = make('th', label); th.scope = 'col'; header.append(th); }
    const actionHeader = make('th', 'Actions'); actionHeader.scope = 'col'; header.append(actionHeader); head.append(header);
    const body = make('tbody');
    for (const record of listing.rows) {
      const row = make('tr');
      for (const [key] of columns) {
        const cell = make('td');
        if (key === 'duration') {
          cell.append(make('strong', record.duration.months === null ? '—' : record.duration.months), make('small', record.duration.text, 'duration-detail'));
        } else if (key === 'status') {
          cell.append(make('span', record.status, `status-pill status-${record.status.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`));
        } else cell.textContent = record[key] || '—';
        row.append(cell);
      }
      const actions = make('td', undefined, 'row-actions');
      const view = make('button', 'View details', 'text-button');
      view.addEventListener('click', () => showIntern(record.id, false)); actions.append(view);
      if (schemaReady) {
        const edit = make('button', 'Edit', 'text-button');
        edit.addEventListener('click', () => showIntern(record.id, true)); actions.append(edit);
        const remove = make('button', 'Delete', 'text-button danger-button');
        remove.addEventListener('click', () => deleteIntern(record)); actions.append(remove);
      }
      row.append(actions); body.append(row);
    }
    table.append(head, body); holder.append(table);
  }

  function addField(sections, groupName, descriptor, value, editable, extra = false, isNew = false) {
    let section = sections.get(groupName);
    if (!section) {
      section = make('fieldset'); section.append(make('legend', groupName));
      const grid = make('div', undefined, 'form-grid'); section.append(grid); sections.set(groupName, section); get('intern-fields').append(section);
    }
    const area = make('label', undefined, 'form-label');
    area.append(make('span', descriptor.label + (editable && isNew && descriptor.required ? ' *' : '')));
    if (!editable) {
      area.append(make('span', value || 'Not specified', 'detail-value'));
    } else {
      let input;
      if (descriptor.type === 'status') {
        input = make('select');
        const statuses = ['Candidate', 'In process', 'Intern', 'Hired', 'Graduate', 'Offboarded', 'Active', 'Completed', 'Inactive'];
        for (const status of statuses) input.add(new Option(status, status));
        if (value && !statuses.includes(value)) input.add(new Option(value, value));
      } else if (descriptor.key === 'recruitment_source') {
        input = make('select');
        const sources = ['', 'LinkedIn', 'University job board', 'Job fair', 'Employee referral', 'Social media', 'Company website', 'Recruitment event', 'Direct contact', 'Other'];
        for (const source of sources) input.add(new Option(source || 'Select a source', source));
      } else {
        input = make('input');
        input.type = descriptor.type === 'date' && value && !/^\d{4}-\d{2}-\d{2}$/.test(value) ? 'text' : descriptor.type || 'text';
        input.maxLength = 2000;
        if (descriptor.type === 'date' && input.type === 'text') input.placeholder = 'Use YYYY-MM-DD to correct this legacy date';
      }
      input.value = value || '';
      input.setAttribute('aria-label', descriptor.label);
      input.required = isNew && descriptor.required;
      input.dataset.field = descriptor.key;
      input.dataset.extra = extra ? '1' : '0';
      input.dataset.original = value || '';
      if (extra && /^months$/i.test(descriptor.key.trim())) {
        input.disabled = true; area.append(make('small', 'Legacy value retained. Duration is calculated automatically.'));
      }
      area.append(input);
    }
    section.querySelector('.form-grid').append(area);
  }

  async function showIntern(id, editable) {
    if (writing) return;
    get('intern-form-error').hidden = true;
    try {
      let data;
      if (!id) {
        if (!listing?.schema?.ready) throw new Error('Connect to Excel and prepare workbook fields first.');
        data = { schema: listing.schema, values: { status: 'Active' },
          extra: Object.fromEntries((listing.schema.extraColumns || []).map(column => [column, ''])) };
      } else data = await api('/api/interns/' + encodeURIComponent(id));
      formState = { id, revision: data.schema.revision, editable };
      get('intern-fields').replaceChildren();
      const sections = new Map();
      for (const descriptor of data.schema.fields) addField(sections, descriptor.group, descriptor, data.values[descriptor.key], editable, false, !id);
      for (const [column, value] of Object.entries(data.extra)) {
        const descriptor = (data.schema.extraFields || []).find(field => field.key === column) || { key: column, label: column, type: 'text' };
        addField(sections, 'Other existing information', descriptor, value, editable, true, !id);
      }
      if (data.record) {
        const section = make('p', `Months as Intern: ${data.record.duration.months ?? '—'} · ${data.record.duration.text}`, 'duration-summary');
        get('intern-fields').prepend(section);
      }
      get('intern-dialog-title').textContent = !id ? 'Add intern' : editable ? 'Edit intern' : 'Intern details';
      get('intern-form-intro').textContent = editable ? 'Changes are saved to the connected Excel workbook. Completed and Inactive interns remain available in history; an end date is required.' : 'All existing personal, emergency, insurance, and administrative information is retained.';
      get('intern-save').hidden = !editable;
      get('intern-save').disabled = false;
      get('intern-dialog').showModal();
    } catch (error) { errorAt('management-error', error); }
  }

  async function afterSave() {
    page = 1;
    await loadList();
    window.dispatchEvent(new Event('interns-updated'));
  }

  async function deleteIntern(record) {
    if (writing) return;
    const name = record.name || 'this intern';
    if (!window.confirm(`Delete ${name}? This removes the record from the connected Excel workbook. A recovery backup will be created first.`)) return;
    writing = true;
    get('management-error').hidden = true;
    try {
      await api('/api/interns/' + encodeURIComponent(record.id), 'DELETE', { revision: listing.schema.revision });
      await afterSave();
    } catch (error) { errorAt('management-error', error); }
    finally { writing = false; if (listing) renderList(); }
  }

  get('intern-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (writing || !formState?.editable) return;
    writing = true; get('intern-save').disabled = true; get('intern-form-error').hidden = true;
    const editingId = formState.id;
    try {
      const fields = {}, extra = {};
      get('intern-fields').querySelectorAll('[data-field]').forEach(input => {
        if (input.disabled) return;
        if (formState.id && input.value === input.dataset.original) return;
        if (!formState.id && !input.value && input.dataset.extra === '1') return;
        (input.dataset.extra === '1' ? extra : fields)[input.dataset.field] = input.value;
      });
      await api(formState.id ? '/api/interns/' + encodeURIComponent(formState.id) : '/api/interns', formState.id ? 'PATCH' : 'POST', { fields, extra, revision: formState.revision });
      get('intern-dialog').close();
      if (!editingId) { get('intern-status').value = 'All'; get('intern-search').value = fields.name; get('intern-sort').value = 'start_date'; get('intern-direction').value = 'desc'; }
      await afterSave();
    } catch (error) { errorAt('intern-form-error', error); }
    finally { writing = false; get('intern-save').disabled = false; if (listing) renderList(); }
  });

  get('add-intern').addEventListener('click', () => showIntern(null, true));
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => { if (!writing) get(button.dataset.close).close(); }));
  get('intern-dialog').addEventListener('cancel', event => { if (writing) event.preventDefault(); });
  get('intern-dialog').addEventListener('close', () => { get('intern-fields').replaceChildren(); formState = null; });

  get('prepare-workbook').addEventListener('click', () => {
    get('migration-error').hidden = true;
    get('migration-columns').replaceChildren(...listing.schema.missingColumns.map(column => make('li', column)));
    if (!listing.schema.missingColumns.length) get('migration-columns').append(make('li', 'Fill missing record keys only.'));
    get('migration-dialog').showModal();
  });
  get('migration-save').addEventListener('click', async () => {
    if (writing) return;
    writing = true; get('migration-save').disabled = true;
    try {
      await api('/api/management/migrate', 'POST', { revision: listing.schema.revision });
      get('migration-dialog').close(); await afterSave();
    } catch (error) { errorAt('migration-error', error); }
    finally { writing = false; get('migration-save').disabled = false; if (listing) renderList(); }
  });
  get('migration-dialog').addEventListener('cancel', event => { if (writing) event.preventDefault(); });
  get('intern-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { page = 1; loadList(); }, 250); });
  for (const id of ['intern-status', 'intern-sort', 'intern-direction']) get(id).addEventListener('change', () => { page = 1; loadList(); });
  get('intern-reload').addEventListener('click', () => loadList());
  get('intern-previous').addEventListener('click', () => { if (page > 1) { page--; loadList(); } });
  get('intern-next').addEventListener('click', () => { page++; loadList(); });
  window.addEventListener('dashboard-loaded', () => loadList());
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !writing && !get('intern-dialog').open) loadList();
  });
  setInterval(() => {
    const mexicoDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Mexico_City' }).format(new Date());
    if (lastDay && mexicoDay !== lastDay && !writing && !document.hidden) loadList();
  }, 60000);
  loadList();
})();
