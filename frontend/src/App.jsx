import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getConfig, getDay, getHourlyProfile, getSummary } from './api'
import './App.css'

const fmt = (n) => (n == null ? '-' : Math.round(n).toLocaleString('en-GB'))
const mw = (v) => `${fmt(v)} MW`
const hourLabel = (iso) => iso.slice(11, 16)
const longTime = (iso) => `${iso.slice(8, 10)} Jan, ${iso.slice(11, 16)} UTC`

function shiftDay(dateStr, delta) {
  const dt = new Date(`${dateStr}T00:00:00Z`)
  dt.setUTCDate(dt.getUTCDate() + delta)
  return dt.toISOString().slice(0, 10)
}

function useFetch(loader, deps) {
  const [state, setState] = useState({ data: null, error: null })

  useEffect(() => {
    let live = true
    loader()
      .then((data) => live && setState({ data, error: null }))
      .catch((err) => live && setState({ data: null, error: err.message }))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}

function Status({ state, children }) {
  if (state.error) {
    return (
      <div className="notice error">
        Could not load data ({state.error}). Check that the backend is running on port 8000.
      </div>
    )
  }
  if (!state.data) {
    return <div className="notice">Loading...</div>
  }
  return children(state.data)
}

function Stat({ label, value, unit, hint }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit"> {unit}</span>}
      </div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

function DaySection({ day, cutoff }) {
  const state = useFetch(() => getDay(day, cutoff), [day, cutoff])

  return (
    <section className="section" id="day-section">
      <h2>Delivery day: {day}</h2>
      <p className="lead">
        The forecast a buyer actually had when the day-ahead decision had to be made, against what the
        wind farms delivered.
      </p>
      <Status state={state}>
        {(d) => {
          const m = d.metrics
          const chartData = d.hours.map((h) => ({
            hour: hourLabel(h.target),
            Forecast: h.forecast,
            Actual: h.actual,
          }))
          const diff = d.total_forecast_mwh - d.total_actual_mwh
          const diffPct = (100 * diff) / d.total_actual_mwh

          return (
            <>
              <div className="stats">
                <Stat
                  label="Forecast used"
                  value={longTime(d.forecast_publish_times[0])}
                  hint={`latest published before the ${longTime(d.decision_cutoff)} cutoff`}
                />
                <Stat
                  label="Energy gap for the day"
                  value={`${diff >= 0 ? '+' : '-'}${fmt(Math.abs(diff))}`}
                  unit="MWh"
                  hint={`forecast ${fmt(d.total_forecast_mwh)} vs actual ${fmt(d.total_actual_mwh)} MWh (${diffPct >= 0 ? '+' : '-'}${Math.abs(diffPct).toFixed(1)}%)`}
                />
                <Stat label="Average error (MAE)" value={fmt(m.mae_mw)} unit="MW" hint={`${m.mae_pct_of_mean_actual}% of average wind`} />
                <Stat label="Bias" value={fmt(m.bias_mw)} unit="MW" hint="forecast minus actual, averaged" />
                <Stat label="Worst-case shortfall (P90)" value={fmt(m.p90_shortfall_mw)} unit="MW" hint="forecast too high by this much or less in 9 of 10 hours" />
              </div>

              <div className="chart-card">
                <h3>Forecast vs actual wind generation, by hour</h3>
                <p className="sub">Hours are UTC, which equals London time in January.</p>
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ee" />
                    <XAxis dataKey="hour" interval={2} />
                    <YAxis domain={[0, 'auto']} tickFormatter={(v) => `${v / 1000} GW`} />
                    <Tooltip formatter={(v) => mw(v)} />
                    <Legend />
                    <Line type="monotone" dataKey="Forecast" stroke="#c2410c" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="Actual" stroke="#0f766e" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )
        }}
      </Status>
    </section>
  )
}

function SummarySection({ cutoff, selectedDay, onPickDay }) {
  const summary = useFetch(() => getSummary(cutoff), [cutoff])
  const profile = useFetch(() => getHourlyProfile(cutoff), [cutoff])

  return (
    <section className="section">
      <h2>How accurate was the forecast across January?</h2>
      <p className="lead">
        Every delivery hour in January 2026, using the forecast available at the cutoff on the
        previous day.
      </p>

      <Status state={summary}>
        {(s) => {
          const m = s.metrics
          const biasPct = (100 * m.bias_mw) / m.mean_actual_mw
          const dailyData = s.daily.map((d) => ({ ...d, day: d.date.slice(8) }))

          // The click lives on the whole chart. Recharts reports which bar the
          // mouse is over, but the field name differs between versions, so we
          // try the index first and fall back to the x-axis label ("28").
          const handleBarClick = (chartState) => {
            if (!chartState) return
            const rawIndex = chartState.activeTooltipIndex ?? chartState.activeIndex
            const index = Number(rawIndex)
            let item = Number.isInteger(index) ? dailyData[index] : undefined
            if (!item && chartState.activeLabel != null) {
              item = dailyData.find((d) => d.day === String(chartState.activeLabel))
            }
            if (item) onPickDay(item.date)
          }

          return (
            <>
              <div className="callout">
                On average the forecast was <strong>{fmt(m.bias_mw)} MW</strong> ({biasPct.toFixed(1)}%)
                {m.bias_mw >= 0 ? ' above' : ' below'} what wind actually delivered, and it was too high
                in <strong>{s.share_hours_over_forecast_pct}%</strong> of hours. In 9 out of 10 hours the
                forecast overshoot was no more than <strong>{fmt(m.p90_shortfall_mw)} MW</strong>.
              </div>

              <div className="stats">
                <Stat label="Average error (MAE)" value={fmt(m.mae_mw)} unit="MW" hint={`${m.mae_pct_of_mean_actual}% of average wind`} />
                <Stat label="Typical large error (RMSE)" value={fmt(m.rmse_mw)} unit="MW" hint="punishes big misses more" />
                <Stat label="Bias" value={fmt(m.bias_mw)} unit="MW" hint="positive = forecast too high" />
                <Stat label="Worst-case shortfall (P90)" value={fmt(m.p90_shortfall_mw)} unit="MW" hint="plan a buffer of about this much" />
                <Stat label="Hours over-forecast" value={`${s.share_hours_over_forecast_pct}%`} hint={`of ${m.n_hours} delivery hours`} />
              </div>

              <div className="chart-card">
                <h3>Average forecast error per delivery day</h3>
                <p className="sub">Orange bars: forecast was too high. Green bars: too low. Click a bar to jump to that day (darker bar = selected day).</p>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={dailyData}
                    margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
                    onClick={handleBarClick}
                    style={{ cursor: 'pointer' }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ee" />
                    <XAxis dataKey="day" />
                    <YAxis tickFormatter={(v) => `${v / 1000} GW`} />
                    <Tooltip
                      formatter={(v) => mw(v)}
                      labelFormatter={(label) => `${label} Jan`}
                    />
                    <ReferenceLine y={0} stroke="#647282" />
                    <Bar dataKey="bias_mw" name="Average error">
                      {dailyData.map((d) => (
                        <Cell
                          key={d.date}
                          fill={d.bias_mw >= 0 ? '#c2410c' : '#0f766e'}
                          fillOpacity={d.date === selectedDay ? 1 : 0.55}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )
        }}
      </Status>

      <Status state={profile}>
        {(rows) => (
          <div className="chart-card">
            <h3>Average forecast error by hour of the day</h3>
            <p className="sub">Shows whether the forecast is worse at particular times of day (UTC).</p>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={rows} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ee" />
                <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, '0')}:00`} interval={1} />
                <YAxis
                  domain={[0, (max) => Math.ceil(max / 1000) * 1000]}
                  tickCount={4}
                  tickFormatter={(v) => `${v / 1000} GW`}
                />
                <Tooltip
                  formatter={(v) => mw(v)}
                  labelFormatter={(h) => `${String(h).padStart(2, '0')}:00 UTC`}
                />
                <ReferenceLine y={0} stroke="#647282" />
                <Bar dataKey="bias_mw" name="Average error" fill="#c2410c" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Status>
    </section>
  )
}

export default function App() {
  const config = useFetch(getConfig, [])
  const [day, setDay] = useState('2026-01-15')
  const [cutoff, setCutoff] = useState('09:00')

  const minDay = config.data?.first_day ?? '2026-01-01'
  const maxDay = config.data?.last_day ?? '2026-01-31'

  const pickDay = (value) => {
    if (value && value >= minDay && value <= maxDay) setDay(value)
  }
  const move = (delta) => pickDay(shiftDay(day, delta))
  const pickCutoff = (value) => {
    if (/^\d{2}:\d{2}$/.test(value)) setCutoff(value)
  }

  // Clicking a bar far down the page changes the section at the top, so scroll
  // that section into view to show the person what changed.
  const pickDayFromChart = (value) => {
    pickDay(value)
    document.getElementById('day-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="page">
      <header className="header">
        <h1>UK day-ahead wind forecast check</h1>
        <p>National wind generation, Elexon data, delivery days in January 2026.</p>
      </header>

      <div className="controls">
        <div className="control">
          <label htmlFor="day">Delivery day</label>
          <div className="control-row">
            <button onClick={() => move(-1)} aria-label="Previous day">&larr;</button>
            <input id="day" type="date" min={minDay} max={maxDay} value={day} onChange={(e) => pickDay(e.target.value)} />
            <button onClick={() => move(1)} aria-label="Next day">&rarr;</button>
          </div>
        </div>
        <div className="control">
          <label htmlFor="cutoff">Decision cutoff (UTC, day before)</label>
          <input id="cutoff" type="time" value={cutoff} onChange={(e) => pickCutoff(e.target.value)} />
        </div>
        <p className="note">
          The buyer uses the newest forecast published at or before this time on the day before delivery.
        </p>
      </div>

      <DaySection day={day} cutoff={cutoff} />
      <SummarySection cutoff={cutoff} selectedDay={day} onPickDay={pickDayFromChart} />

      <div className="footnotes">
        How the numbers are built:
        <ul>
          <li>Error = forecast minus actual. Positive means wind came in below the forecast.</li>
          <li>Forecasts are hourly and actuals are half-hourly, so each actual hour is the average of its two half-hours.</li>
          <li>All times are UTC. January in the UK is GMT, so this is also London time.</li>
          <li>Data: Elexon BMRS, WINDFOR (forecasts) and FUELHH (actual wind generation).</li>
        </ul>
      </div>
    </div>
  )
}
