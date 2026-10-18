/* Experiment 42: sample inspection, path-distance replay, and pointer capture. */
const $ = (id) => document.getElementById(id);
const state = {index: {summary: {}, samples: []}, results: {}, filtered: [], limit: 60,
  selected: null, sample: null, token: 0, playing: false, fraction: 1, lastFrame: 0,
  strokes: [], strokeDevices: [], activePointer: null, saving: false};
const names = {image: 'Rendered image', reference: 'Reference trace', recovered: 'Recovered path'};
const pct = (x) => Number.isFinite(x) ? `${(x * 100).toFixed(1)}%` : '-';
const icons = () => window.lucide?.createIcons();
const text = (id, value) => { $(id).textContent = value ?? ''; };

async function api(path, options) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}

function toast(message) {
  text('toast', message); $('toast').hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => { $('toast').hidden = true; }, 3500);
}

function view(name) {
  for (const node of document.querySelectorAll('[data-view]')) node.classList.toggle('active', node.dataset.view === name);
  for (const name2 of ['samples', 'capture', 'results']) $(`${name2}-view`).hidden = name2 !== name;
  if (name === 'capture') requestAnimationFrame(paintPad);
  if (name === 'results') loadResults();
}

function filterSamples() {
  const query = $('search').value.toLocaleLowerCase().trim(), split = $('split').value;
  state.filtered = state.index.samples.filter(s => (split === 'all' || s.split === split)
    && (!query || s.text.toLocaleLowerCase().includes(query) || s.id.includes(query)));
  const order = $('sort').value;
  state.filtered.sort((a, b) => order === 'coverage' ? a.ink_coverage - b.ink_coverage :
    order === 'length' ? b.text.length - a.text.length : a.id.localeCompare(b.id));
  state.limit = 60;
  renderList();
  if (!state.filtered.some(s => s.id === state.selected)) {
    if (state.filtered.length) selectSample(state.filtered[0].id);
    else emptySample();
  }
}

function renderList() {
  const fragment = document.createDocumentFragment();
  for (const s of state.filtered.slice(0, state.limit)) {
    const button = document.createElement('button');
    button.className = 'sample-item' + (s.id === state.selected ? ' selected' : '');
    button.setAttribute('role', 'option'); button.setAttribute('aria-selected', String(s.id === state.selected));
    const label = document.createElement('span'); label.className = 'arabic'; label.lang = 'ar'; label.textContent = s.text || 'Untitled recording';
    const meta = document.createElement('span'); meta.className = 'item-meta';
    const id = document.createElement('span'); id.textContent = s.id.slice(0, 8);
    const cover = document.createElement('span'); cover.textContent = pct(s.ink_coverage) + ' ink';
    meta.append(id, cover); button.append(label, meta); button.onclick = () => selectSample(s.id); fragment.append(button);
  }
  if (!state.filtered.length) {
    const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = 'No matching observations.'; fragment.append(empty);
  }
  $('sample-list').replaceChildren(fragment);
  text('sample-count', state.filtered.length.toLocaleString());
  text('list-range', `${Math.min(state.limit, state.filtered.length)} of ${state.filtered.length}`);
  $('more').hidden = state.filtered.length <= state.limit;
  updateNavigation();
}

function updateNavigation() {
  const i = state.filtered.findIndex(s => s.id === state.selected);
  $('previous').disabled = i <= 0; $('next').disabled = i < 0 || i >= state.filtered.length - 1;
  $('download').disabled = !state.sample;
}

function emptySample() {
  state.token++; state.selected = null; state.sample = null; state.playing = false;
  text('sample-id', 'No sample selected'); text('transcription', ''); text('provenance', 'No observations');
  text('segmentation', ''); $('raster').removeAttribute('src');
  for (const id of ['image-reading', 'reference-reading', 'recovered-reading', 'source-dataset', 'source-parent',
    'source-motion', 'source-transcription', 'data-note', 'reference-count', 'recovered-count', 'reference-time', 'image-size']) text(id, '');
  for (const id of ['coverage', 'iou', 'components', 'failures']) text(id, '-');
  paint(); updateNavigation();
}

async function selectSample(id) {
  const token = ++state.token; state.selected = id; state.playing = false;
  $('sample-error').hidden = true; renderList();
  try {
    const sample = await api(`/api/sample/${id}`);
    if (token !== state.token) return;
    state.sample = sample; state.fraction = 1;
    text('sample-id', `${sample.dataset} / ${sample.id} / ${sample.split}`);
    text('transcription', sample.text || 'Untitled recording');
    const captured = sample.provenance === 'captured_input';
    text('provenance', captured ? `Recorded ${sample.device} input` : 'Human retracing');
    text('segmentation', captured ? sample.style : 'Oracle word boundary · style unlabelled');
    $('raster').src = `/assets/${id}.png`;
    text('image-size', `${sample.width} × ${sample.height}`);
    text('reference-count', `${sample.reference.length} strokes`);
    text('reference-time', captured ? 'Event times retained' : 'Timing unavailable');
    text('recovered-count', `${sample.recovered.strokes.length} walks`);
    text('coverage', pct(sample.recovered.ink_coverage)); text('iou', pct(sample.recovered.ink_iou));
    text('components', sample.recovered.components); text('failures', sample.recovered.failures.length);
    text('source-dataset', sample.dataset); text('source-parent', sample.parent);
    text('source-motion', captured ? `${sample.device}; x/y, event time, pressure, tilt retained` : 'Annotator sequence; original writer motion unavailable');
    text('source-transcription', captured ? sample.transcription_status : 'Upstream annotation; primitive sequence validated');
    text('data-note', captured ? 'Freely recorded input. No character boundaries supplied. Retrieval and sequence models, when available, were fitted to Calliar retracings.' :
      'Calliar annotators traced existing images in prescribed character order. Vowel marks and decoration are generally omitted upstream. Ink coverage does not measure correct text or historical stroke order.');
    updateReadings(); updateNavigation(); paint();
  } catch (error) {
    if (token !== state.token) return;
    text('sample-error', error.message); $('sample-error').hidden = false;
  }
}

function updateReadings() {
  const mode = $('reader-mode').value;
  for (const arm of ['image', 'reference', 'recovered']) {
    const output = mode === 'sequence' ? state.results : state.results.retrieval;
    const stored = output?.arms?.[arm]?.predictions?.find(p => p.id === state.selected);
    const captured = mode === 'sequence' ? state.sample?.predictions?.[arm] : state.sample?.retrieval_predictions?.[arm]?.predicted;
    const prediction = captured ?? stored?.predicted;
    text(`${arm}-reading`, prediction === undefined ? 'Not evaluated' : prediction || 'No characters');
    $(`${arm}-reading`).classList.toggle('unmeasured', !prediction);
    $(`${arm}-reading`).previousElementSibling.textContent = mode === 'sequence' ? 'CTC reading' : 'Retrieval match';
  }
}

function drawPath(canvas, strokes, fraction, colour) {
  const ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save(); ctx.scale(canvas.width / 384, canvas.height / 128);
  if ($('ghost').checked && $('raster').complete && $('raster').naturalWidth) {
    ctx.globalAlpha = .12; ctx.drawImage($('raster'), 0, 0, 384, 128); ctx.globalAlpha = 1;
  }
  const segments = []; let total = 0;
  for (const stroke of strokes) {
    if (stroke.length === 1) { segments.push({a: stroke[0], b: stroke[0], start: total, length: 1}); total++; }
    for (let i = 1; i < stroke.length; i++) {
      const a = stroke[i - 1], b = stroke[i], length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      segments.push({a, b, start: total, length}); total += length;
    }
  }
  const wanted = total * fraction; let cursor = null;
  ctx.lineWidth = 2.3; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = colour; ctx.fillStyle = colour;
  if (fraction > 0) for (const segment of segments) {
    if (segment.start >= wanted) break;
    const f = segment.length ? Math.min(1, (wanted - segment.start) / segment.length) : 1;
    const end = [segment.a[0] + (segment.b[0] - segment.a[0]) * f, segment.a[1] + (segment.b[1] - segment.a[1]) * f];
    ctx.beginPath(); ctx.moveTo(...segment.a); ctx.lineTo(...end); ctx.stroke();
    if (segment.a === segment.b) { ctx.beginPath(); ctx.arc(...end, 1.3, 0, Math.PI * 2); ctx.fill(); }
    cursor = end;
  }
  if (cursor && fraction < 1) { ctx.fillStyle = '#263b35'; ctx.beginPath(); ctx.arc(...cursor, 3, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
}

function paint() {
  drawPath($('reference-canvas'), state.sample?.reference || [], state.fraction, '#147c80');
  drawPath($('recovered-canvas'), state.sample?.recovered.strokes || [], state.fraction, '#b24f40');
  $('progress').value = Math.round(state.fraction * 1000); text('progress-value', pct(state.fraction).replace('.0', ''));
  $('play').setAttribute('aria-label', state.playing ? 'Pause traces' : 'Play traces');
  $('play').title = state.playing ? 'Pause traces' : 'Play traces';
  if ($('play').dataset.playing !== String(state.playing)) {
    $('play').dataset.playing = String(state.playing);
    $('play').innerHTML = `<i data-lucide="${state.playing ? 'pause' : 'play'}"></i>`; icons();
  }
}

function animate(now) {
  if (state.playing && state.sample) {
    state.fraction = Math.min(1, state.fraction + Math.min(100, now - state.lastFrame) / 6000 * Number($('speed').value));
    if (state.fraction >= 1) state.playing = false;
    paint();
  }
  state.lastFrame = now; requestAnimationFrame(animate);
}

function paintPad() {
  const canvas = $('capture-canvas'), bounds = canvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(bounds.width * ratio); canvas.height = Math.round(bounds.height * ratio);
  const ctx = canvas.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, bounds.width, bounds.height);
  ctx.lineWidth = 2.5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#202426'; ctx.fillStyle = '#202426';
  for (const stroke of state.strokes) {
    if (stroke.length === 1) { ctx.beginPath(); ctx.arc(stroke[0][0], stroke[0][1], 1.25, 0, Math.PI * 2); ctx.fill(); }
    else { ctx.beginPath(); ctx.moveTo(stroke[0][0], stroke[0][1]); for (const p of stroke.slice(1)) ctx.lineTo(p[0], p[1]); ctx.stroke(); }
  }
  text('capture-count', `${state.strokes.length} ${state.strokes.length === 1 ? 'stroke' : 'strokes'} · ${state.strokes.reduce((n, s) => n + s.length, 0)} points`);
  const types = [...new Set(state.strokeDevices)]; text('device', types.length > 1 ? 'Mixed input' : types[0] ? `${types[0]} input` : 'No input yet');
  $('undo').disabled = !state.strokes.length || state.saving || state.activePointer !== null;
  $('clear').disabled = !state.strokes.length || state.saving || state.activePointer !== null;
  $('save').disabled = state.saving || state.activePointer !== null;
}

function recordPoint(event) {
  const bounds = $('capture-canvas').getBoundingClientRect();
  const stroke = state.strokes.at(-1);
  for (const e of (event.getCoalescedEvents?.().length ? event.getCoalescedEvents() : [event])) {
    const point = [e.clientX - bounds.left, e.clientY - bounds.top, e.timeStamp, Math.max(0, Math.min(1, e.pressure || 0)), e.tiltX || 0, e.tiltY || 0];
    if (!stroke.length || point[2] >= stroke.at(-1)[2]) stroke.push(point);
  }
  paintPad();
}

async function saveCapture(event) {
  event.preventDefault();
  if (state.saving || state.activePointer !== null) return;
  if (!state.strokes.length) { text('capture-status', 'No writing recorded.'); return; }
  if ($('checked').checked && !$('capture-text').value.trim()) { text('capture-status', 'A checked transcription cannot be empty.'); return; }
  state.saving = true; paintPad(); text('capture-status', 'Saving observation…');
  const types = [...new Set(state.strokeDevices)];
  try {
    const record = await api('/api/captures', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      strokes: state.strokes, text: $('capture-text').value, writer: $('writer').value, style: $('style').value,
      checked: $('checked').checked, device: types.length > 1 ? 'mixed' : types[0] || 'unknown'})});
    state.strokes = []; state.strokeDevices = []; $('capture-text').value = ''; $('checked').checked = false; paintPad();
    state.index = await api('/api/index'); $('split').value = 'unassigned'; $('search').value = ''; filterSamples();
    await selectSample(record.id); view('samples'); toast('Observation saved locally'); text('capture-status', '');
  } catch (error) { text('capture-status', error.message); }
  finally { state.saving = false; paintPad(); }
}

function fillTable(id, rows) {
  const body = $(id).querySelector('tbody'); body.replaceChildren();
  for (const values of rows) { const tr = document.createElement('tr'); for (const value of values) { const td = document.createElement('td'); td.textContent = value; tr.append(td); } body.append(tr); }
  if (!rows.length) { const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 6; td.textContent = 'No completed measurements yet.'; tr.append(td); body.append(tr); }
}

async function loadResults() {
  try {
    state.results = await api('/api/results'); $('results-error').hidden = true;
    const retrieval = state.results.retrieval;
    text('retrieval-note', retrieval?.interpretation || 'The nearest-example control has not been run.');
    fillTable('retrieval-table', Object.entries(retrieval?.arms || {}).map(([arm, r]) => [names[arm], r.test.samples,
      pct(r.test.accuracy), pct(r.test.cer), `${pct(r.seen_text.accuracy)} (${r.seen_text.samples})`, `${pct(r.unseen_text.accuracy)} (${r.unseen_text.samples})`]));
    text('neural-note', state.results.interpretation || 'The sequence-reader pilot has not completed.');
    fillTable('neural-table', Object.entries(state.results.arms || {}).map(([arm, r]) => [names[arm], r.parameters.toLocaleString(),
      r.test.samples, pct(r.test.accuracy), pct(r.test.cer), pct(Math.min(...r.history.map(x => x.validation.cer)))]));
    const audit = state.index.summary;
    $('audit').replaceChildren();
    for (const [name, value] of [['Source drawings', audit.source_drawings], ['Validated words', audit.words],
      ['Rejected drawings', audit.rejected_drawings], ['Duplicate word rasters', audit.duplicate_word_rasters],
      ['Mean ink coverage', pct(audit.mean_ink_coverage)], ['Words with unresolved paths', audit.words_with_recovery_failures]]) {
      const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = name; dd.textContent = value ?? '-'; $('audit').append(dt, dd);
    }
    $('limits').replaceChildren();
    for (const note of audit.notes || []) { const li = document.createElement('li'); li.textContent = note; $('limits').append(li); }
    updateReadings();
  } catch (error) { text('results-error', error.message); $('results-error').hidden = false; }
}

function bind() {
  for (const button of document.querySelectorAll('[data-view]')) button.onclick = () => view(button.dataset.view);
  $('search').oninput = filterSamples; $('split').onchange = filterSamples; $('sort').onchange = filterSamples;
  $('more').onclick = () => { state.limit += 60; renderList(); };
  for (const [id, delta] of [['previous', -1], ['next', 1]]) $(id).onclick = () => {
    const i = state.filtered.findIndex(s => s.id === state.selected); if (state.filtered[i + delta]) selectSample(state.filtered[i + delta].id);
  };
  $('download').onclick = () => {
    if (!state.sample) return; const blob = new Blob([JSON.stringify(state.sample, null, 2)], {type: 'application/json'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${state.sample.id}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  $('play').onclick = () => { if (!state.sample) return; if (state.fraction >= 1) state.fraction = 0; state.playing = !state.playing; paint(); };
  $('restart').onclick = () => { state.fraction = 0; state.playing = false; paint(); };
  $('progress').oninput = () => { state.fraction = Number($('progress').value) / 1000; state.playing = false; paint(); };
  $('ghost').onchange = paint; $('raster').onload = paint;
  $('refresh').onclick = loadResults;
  $('reader-mode').onchange = updateReadings;
  const pad = $('capture-canvas');
  pad.onpointerdown = (e) => { if (state.saving || state.activePointer !== null || e.button !== 0) return; e.preventDefault(); state.activePointer = e.pointerId;
    state.strokes.push([]); state.strokeDevices.push(e.pointerType || 'unknown'); pad.setPointerCapture(e.pointerId); recordPoint(e); };
  pad.onpointermove = (e) => { if (e.pointerId === state.activePointer) { e.preventDefault(); recordPoint(e); } };
  pad.onpointerup = (e) => { if (e.pointerId === state.activePointer) { recordPoint(e); state.activePointer = null; if (pad.hasPointerCapture(e.pointerId)) pad.releasePointerCapture(e.pointerId); paintPad(); } };
  pad.onpointercancel = (e) => { if (e.pointerId === state.activePointer) { state.strokes.pop(); state.strokeDevices.pop(); state.activePointer = null; paintPad(); } };
  $('undo').onclick = () => { state.strokes.pop(); state.strokeDevices.pop(); paintPad(); };
  $('clear').onclick = () => { state.strokes = []; state.strokeDevices = []; state.activePointer = null; paintPad(); };
  $('capture-form').onsubmit = saveCapture; window.addEventListener('resize', paintPad);
}

async function init() {
  bind(); icons(); requestAnimationFrame(animate);
  try { state.index = await api('/api/index'); filterSamples(); await loadResults(); }
  catch (error) { text('sample-error', error.message); $('sample-error').hidden = false; }
}
init();
