/* Read-only selectors for committed research exports. No inference, auth or storage access. */
const status = document.querySelector('#research-controls-status')
const controls = [...document.querySelectorAll('.research-controls select')]
controls.forEach(control => { control.disabled = true })
const number = value => Number.isFinite(value) ? value.toFixed(6) : 'Unavailable'
const label = method => method === 'kaplan_meier' ? 'Kaplan–Meier' : 'Logistic comparison'

async function load(path) {
  const response = await fetch(path, { credentials: 'omit', cache: 'no-cache' })
  if (!response.ok) throw new Error('Research export unavailable')
  return response.json()
}

try {
  const [data, ledger] = await Promise.all([load('/research/dashboard.json'), load('/research/dashboard-figures.json')])
  if (data.schema_version !== 'research-dashboard-1' || ledger.schema_version !== 'dashboard-figures-1') throw new Error('Unsupported export')
  const files = new Map(ledger.figures.map(figure => [figure.file, figure.sha256]))
  const get = id => document.getElementById(id)
  const swap = (name, variant) => {
    const figure = document.querySelector(`#figure-${name}`)
    const url = suffix => {
      const file = `${variant}${suffix}.svg`
      const digest = files.get(file)
      if (!/^[a-f0-9]{64}$/.test(digest ?? '')) throw new Error('Unavailable figure')
      return `/research/${file}?v=${digest.slice(0, 10)}`
    }
    figure.querySelector('source').srcset = url('-mobile')
    figure.querySelector('img').src = url('')
  }
  const updateCalibration = () => {
    const method = get('calibration-model').value, horizon = get('calibration-horizon').value
    if (!['kaplan_meier', 'logistic'].includes(method) || !['6', '12', '24'].includes(horizon)) throw new Error('Unsupported calibration')
    swap('calibration', `calibration-${method}-${horizon}`)
    const rows = []
    for (const [period, title] of [['validation', '2024 validation'], ['test', '2025 inspected test']]) {
      const result = data.categories.Flood[period][method][`${horizon}h`]
      for (const bin of result.reliability) rows.push([title, bin.count, number(bin.mean_predicted), number(bin.observed_frequency)])
    }
    const tbody = document.querySelector('#figure-calibration tbody')
    tbody.replaceChildren(...rows.map(row => {
      const tr = document.createElement('tr')
      row.forEach(value => { const td = document.createElement('td'); td.textContent = value; tr.append(td) })
      return tr
    }))
    get('calibration-context').textContent = `${label(method)} · ${horizon}h · separate 2024 validation and previously inspected 2025 test · bin values below match this selection.`
  }
  const updateDuration = () => {
    const method = get('duration-model').value, scale = get('duration-scale').value
    if (!['kaplan_meier', 'logistic'].includes(method) || !['log', 'linear'].includes(scale)) throw new Error('Unsupported duration')
    swap('duration-errors', `duration-errors-${method}-${scale}`)
    const result = data.flood_holdout_summary.verified_metrics[method]
    get('duration-context').textContent = `${label(method)} · 3,539 snapshots / 567 reporting episodes · MAE ${result.mean_absolute_error_hours.toFixed(3)}h · ${result.unidentified_intervals.toLocaleString('en-US')} unidentified interval bounds remain null · ${scale} scatter axes.`
  }
  const updateTarget = (reset = false) => {
    const category = data.categories[get('research-event').value]
    if (!category) throw new Error('Unsupported target')
    const horizonSelect = get('research-horizon')
    const oldHorizon = Number(horizonSelect.value)
    if (reset) {
      horizonSelect.replaceChildren(...category.horizons.map(h => new Option(`${h} hours`, String(h))))
      horizonSelect.value = String(category.horizons.includes(oldHorizon) ? oldHorizon : category.horizons[0])
    }
    const horizon = Number(horizonSelect.value), period = get('research-period').value
    if (!category.horizons.includes(horizon) || !['validation', 'test'].includes(period)) throw new Error('Unsupported horizon or period')
    const method = category.selected_estimator, result = category[period][method][`${horizon}h`]
    get('research-readout').textContent = `${category.name} · ${period === 'test' ? '2025 retrospective' : '2024 validation'} · ${horizon}h · ${label(method)} · ${result.snapshot_count.toLocaleString('en-US')} snapshots / ${result.episode_count.toLocaleString('en-US')} groups. Brier ${number(result.brier_score)}; group-bootstrap 95% interval ${number(result.episode_bootstrap_brier_95.lower_95)}–${number(result.episode_bootstrap_brier_95.upper_95)}; calibration error ${number(result.expected_calibration_error)}. Artifact: ${category.model_version}.`
    get('research-target-limits').replaceChildren(...category.limits.map(limit => {
      const li = document.createElement('li'); li.textContent = limit; return li
    }))
  }
  const guarded = action => () => {
    try { action() } catch { status.textContent = 'This saved selection is unavailable. Default figures, downloads and source tables remain available.' }
  }
  for (const id of ['calibration-model', 'calibration-horizon']) get(id).addEventListener('change', guarded(updateCalibration))
  for (const id of ['duration-model', 'duration-scale']) get(id).addEventListener('change', guarded(updateDuration))
  get('research-event').addEventListener('change', guarded(() => updateTarget(true)))
  for (const id of ['research-horizon', 'research-period']) get(id).addEventListener('change', guarded(() => updateTarget()))
  updateCalibration(); updateDuration(); updateTarget(true)
  controls.forEach(control => { control.disabled = false })
  status.textContent = 'Interactive controls select precomputed research results only. No simulation or model inference runs in your browser.'
} catch {
  status.textContent = 'Interactive research data is unavailable. Static charts, numerical tables and source downloads remain accessible.'
}
