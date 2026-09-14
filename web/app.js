const state = {
  mode: 'gcode',
  configSubMode: 'values',
  files: { gcodes: null, config: null },
};

const qs = (sel, root = document) => root.querySelector(sel);

const escapeHtml = (str) => String(str).replace(/[&<>"']/g, (ch) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[ch]));

const formatBytes = (n) => {
  if (n == null) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDate = (unixSeconds) => {
  if (!unixSeconds) return '';
  const d = new Date(unixSeconds * 1000);
  return d.toLocaleString(undefined, {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
};

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const message = body?.error?.message || res.statusText || 'Request failed';
    const status = body?.error?.code || res.status;
    const err = new Error(message);
    err.status = status;
    throw err;
  }
  return body?.result !== undefined ? body.result : body;
}

// --- File lists -------------------------------------------------------

async function loadFileList(root) {
  if (state.files[root]) return state.files[root];
  const list = await fetchJSON(`/server/files/list?root=${encodeURIComponent(root)}`);
  state.files[root] = list || [];
  return state.files[root];
}

function populateSelect(selectEl, files, filterText) {
  const needle = (filterText || '').toLowerCase();
  const filtered = files
    .filter((f) => !needle || f.path.toLowerCase().includes(needle))
    .sort((a, b) => (b.modified || 0) - (a.modified || 0));

  const previouslySelected = selectEl.value;
  selectEl.innerHTML = '';
  for (const f of filtered) {
    const opt = document.createElement('option');
    opt.value = f.path;
    opt.textContent = `${f.path}  —  ${formatBytes(f.size)}  —  ${formatDate(f.modified)}`;
    selectEl.appendChild(opt);
  }
  if (filtered.some((f) => f.path === previouslySelected)) {
    selectEl.value = previouslySelected;
  }
}

function wireFilePicker(root, filterId, selectId, onChange) {
  const filterEl = qs(`#${filterId}`);
  const selectEl = qs(`#${selectId}`);
  filterEl.addEventListener('input', () => {
    populateSelect(selectEl, state.files[root] || [], filterEl.value);
    onChange();
  });
  selectEl.addEventListener('change', onChange);
  return { filterEl, selectEl };
}

async function refreshRoot(root, pickers) {
  const files = await loadFileList(root);
  for (const p of pickers) populateSelect(p.selectEl, files, p.filterEl.value);
}

// --- Tabs ---------------------------------------------------------------

const gcodePickers = [
  wireFilePicker('gcodes', 'filter-gcode-1', 'select-gcode-1', updateGcodeButton),
  wireFilePicker('gcodes', 'filter-gcode-2', 'select-gcode-2', updateGcodeButton),
];
const configPickers = [
  wireFilePicker('config', 'filter-config-1', 'select-config-1', updateConfigButton),
  wireFilePicker('config', 'filter-config-2', 'select-config-2', updateConfigButton),
];

async function switchMode(mode) {
  state.mode = mode;
  qs('#tab-gcode').setAttribute('aria-selected', String(mode === 'gcode'));
  qs('#tab-config').setAttribute('aria-selected', String(mode === 'config'));
  qs('#panel-gcode').hidden = mode !== 'gcode';
  qs('#panel-config').hidden = mode !== 'config';
  clearResults();
  try {
    if (mode === 'gcode') {
      await refreshRoot('gcodes', gcodePickers);
    } else {
      await refreshRoot('config', configPickers);
    }
  } catch (err) {
    renderError(err);
    qs('#results').hidden = false;
  }
}

qs('#tab-gcode').addEventListener('click', () => switchMode('gcode'));
qs('#tab-config').addEventListener('click', () => switchMode('config'));

for (const radio of document.querySelectorAll('input[name="config-sub-mode"]')) {
  radio.addEventListener('change', () => {
    if (radio.checked) state.configSubMode = radio.value;
  });
}

// --- Compare actions ------------------------------------------------------

function updateGcodeButton() {
  const f1 = qs('#select-gcode-1').value;
  const f2 = qs('#select-gcode-2').value;
  qs('#compare-gcode-btn').disabled = !f1 || !f2;
}

function updateConfigButton() {
  const f1 = qs('#select-config-1').value;
  const f2 = qs('#select-config-2').value;
  qs('#compare-config-btn').disabled = !f1 || !f2;
}

function clearResults() {
  qs('#results').hidden = true;
  qs('#results-body').innerHTML = '';
  qs('#error-banner').hidden = true;
  qs('#error-banner').innerHTML = '';
}

function setBusy(spinnerId, busy) {
  qs(`#${spinnerId}`).style.display = busy ? 'inline' : 'none';
}

function renderError(err) {
  const hints = {
    404: 'Check that the file still exists in that root.',
    400: 'This gcode file has no recognized slicer settings block (e.g. Cura), or a request parameter was invalid.',
    422: 'This config file could not be parsed as INI.',
  };
  const hint = hints[err.status] || '';
  const banner = qs('#error-banner');
  banner.hidden = false;
  banner.innerHTML = `${escapeHtml(err.message)}${hint ? `<span class="hint">${escapeHtml(hint)}</span>` : ''}`;
  qs('#results').hidden = false;
}

qs('#compare-gcode-btn').addEventListener('click', async () => {
  clearResults();
  const file1 = qs('#select-gcode-1').value;
  const file2 = qs('#select-gcode-2').value;
  const includeSame = qs('#include-same').checked;
  setBusy('spinner-gcode', true);
  try {
    const result = await fetchJSON('/server/slicer/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file1, file2, include_same: includeSame }),
    });
    qs('#results').hidden = false;
    qs('#results-body').innerHTML = renderGcodeDiff(result);
  } catch (err) {
    renderError(err);
  } finally {
    setBusy('spinner-gcode', false);
  }
});

qs('#compare-config-btn').addEventListener('click', async () => {
  clearResults();
  const file1 = qs('#select-config-1').value;
  const file2 = qs('#select-config-2').value;
  const mode = state.configSubMode;
  setBusy('spinner-config', true);
  try {
    const result = await fetchJSON('/server/config/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file1, file2, mode }),
    });
    qs('#results').hidden = false;
    qs('#results-body').innerHTML = mode === 'text' ? renderConfigTextDiff(result) : renderConfigValuesDiff(result);
  } catch (err) {
    renderError(err);
  } finally {
    setBusy('spinner-config', false);
  }
});

// --- Renderers --------------------------------------------------------

const renderBadges = (summary) => `
  <div class="badges">
    <span class="badge"><strong>${summary.same}</strong>same</span>
    <span class="badge"><strong>${summary.changed}</strong>changed</span>
    <span class="badge"><strong>${summary.only_left}</strong>only in file 1</span>
    <span class="badge"><strong>${summary.only_right}</strong>only in file 2</span>
  </div>`;

function renderGcodeDiff(result) {
  let html = renderBadges(result.summary);

  const changedRows = Object.keys(result.changed).sort().map((key) => {
    const entry = result.changed[key];
    const rawBadge = entry.canonical ? '' : ' <span style="color:var(--muted)">(raw)</span>';
    return `
      <tr>
        <td><code>${escapeHtml(key)}</code>${rawBadge}</td>
        <td>${escapeHtml(entry.left.value)}<br><code>${escapeHtml(entry.left.raw_key)}</code></td>
        <td>${escapeHtml(entry.right.value)}<br><code>${escapeHtml(entry.right.raw_key)}</code></td>
      </tr>`;
  }).join('');
  html += `
    <details open>
      <summary>Changed (${Object.keys(result.changed).length})</summary>
      ${changedRows ? `<table><tr><th>Key</th><th>File 1</th><th>File 2</th></tr>${changedRows}</table>` : '<p>None</p>'}
    </details>`;

  [['only_left', 'Only in file 1'], ['only_right', 'Only in file 2']].forEach(([bucket, label]) => {
    const rows = Object.keys(result[bucket]).sort().map((key) => {
      const entry = result[bucket][key];
      return `<tr><td><code>${escapeHtml(key)}</code></td><td>${escapeHtml(entry.value)}</td><td><code>${escapeHtml(entry.raw_key)}</code></td></tr>`;
    }).join('');
    html += `
      <details open>
        <summary>${label} (${Object.keys(result[bucket]).length})</summary>
        ${rows ? `<table><tr><th>Key</th><th>Value</th><th>Raw key</th></tr>${rows}</table>` : '<p>None</p>'}
      </details>`;
  });

  html += `
    <details>
      <summary>Unchanged (${result.same_keys.length})</summary>
      ${result.same_keys.length
        ? `<ul class="plain-list">${result.same_keys.map((k) => `<li><code>${escapeHtml(k)}</code></li>`).join('')}</ul>`
        : '<p>None</p>'}
    </details>`;

  if (result.warnings?.length) {
    html += `
      <details open>
        <summary>Warnings</summary>
        <ul class="plain-list">${result.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
      </details>`;
  }
  return html;
}

function renderConfigValuesDiff(result) {
  let html = renderBadges(result.summary);

  const changedRows = Object.keys(result.changed).sort().map((key) => {
    const entry = result.changed[key];
    return `<tr><td><code>${escapeHtml(key)}</code></td><td>${escapeHtml(entry.left)}</td><td>${escapeHtml(entry.right)}</td></tr>`;
  }).join('');
  html += `
    <details open>
      <summary>Changed (${Object.keys(result.changed).length})</summary>
      ${changedRows ? `<table><tr><th>Key</th><th>File 1</th><th>File 2</th></tr>${changedRows}</table>` : '<p>None</p>'}
    </details>`;

  [['only_left', 'Only in file 1'], ['only_right', 'Only in file 2']].forEach(([bucket, label]) => {
    const rows = Object.keys(result[bucket]).sort()
      .map((key) => `<tr><td><code>${escapeHtml(key)}</code></td><td>${escapeHtml(result[bucket][key])}</td></tr>`)
      .join('');
    html += `
      <details open>
        <summary>${label} (${Object.keys(result[bucket]).length})</summary>
        ${rows ? `<table><tr><th>Key</th><th>Value</th></tr>${rows}</table>` : '<p>None</p>'}
      </details>`;
  });

  html += `
    <details>
      <summary>Unchanged (${result.same_keys.length})</summary>
      ${result.same_keys.length
        ? `<ul class="plain-list">${result.same_keys.map((k) => `<li><code>${escapeHtml(k)}</code></li>`).join('')}</ul>`
        : '<p>None</p>'}
    </details>`;
  return html;
}

function renderConfigTextDiff(result) {
  const { text } = result;
  let html = `
    <div class="badges">
      <span class="badge">${text.identical ? 'Identical' : 'Different'}</span>
      <span class="badge" style="color:var(--add-fg)">+${text.lines_added}</span>
      <span class="badge" style="color:var(--remove-fg)">-${text.lines_removed}</span>
    </div>`;

  if (text.identical) {
    return `${html}<p>No textual differences.</p>`;
  }

  for (const hunk of text.hunks) {
    html += `<div class="hunk-header">@@ -${hunk.left_start},${hunk.left_lines} +${hunk.right_start},${hunk.right_lines} @@</div>`;
    html += '<table class="diff-table">';
    for (const line of hunk.lines) {
      const cls = line.type === 'add' ? 'diff-add' : line.type === 'remove' ? 'diff-remove' : 'diff-context';
      const marker = line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ';
      html += `
        <tr class="${cls}">
          <td class="lineno">${line.left_line || ''}</td>
          <td class="lineno">${line.right_line || ''}</td>
          <td class="diff-text">${escapeHtml(`${marker} ${line.text}`)}</td>
        </tr>`;
    }
    html += '</table>';
  }
  return html;
}

// --- Init -----------------------------------------------------------------

try {
  await refreshRoot('gcodes', gcodePickers);
} catch (err) {
  renderError(err);
  qs('#results').hidden = false;
}
