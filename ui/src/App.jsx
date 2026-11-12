import { useEffect, useRef, useState } from 'react'

const AGENT_COLORS = {
  coordinator: '#8b9bb4',
  scout: '#4ade80',
  scribe: '#c084fc',
}

function describeEvent(evt) {
  const d = evt.detail || {}
  switch (evt.event) {
    case 'run_started':
      return `${d.role} jobs in ${d.location}`
    case 'discovering':
      return `fetching Agent Card from ${d.url}`
    case 'discovered':
      return `${d.name} v${d.version} — skills: ${(d.skills || []).join(', ')}`
    case 'task_sent':
      return d.title
        ? `tailor an application for "${d.title}"${d.company ? ` @ ${d.company}` : ''}`
        : `find ${d.role} jobs in ${d.location}`
    case 'completed':
      if (d.jobs !== undefined)
        return `found ${d.jobs} jobs — top: "${d.top_job?.title}" @ ${d.top_job?.company}`
      return `wrote ${d.bullets} bullets (${d.model})`
    case 'failed':
      return d.error || 'failed'
    default:
      return JSON.stringify(d)
  }
}

export default function App() {
  const [role, setRole] = useState('web developer')
  const [location, setLocation] = useState('Patna')
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [elapsed, setElapsed] = useState(null)
  const [copied, setCopied] = useState(false)
  const feedRef = useRef(null)
  const sourceRef = useRef(null)
  const startRef = useRef(null)

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight })
  }, [events])

  useEffect(() => () => sourceRef.current?.close(), [])

  function run() {
    if (running) return
    sourceRef.current?.close()
    setEvents([])
    setResult(null)
    setError(null)
    setElapsed(null)
    setCopied(false)
    setRunning(true)
    startRef.current = Date.now()

    const url =
      `/api/stream?role=${encodeURIComponent(role)}` +
      `&location=${encodeURIComponent(location)}`
    const source = new EventSource(url)
    sourceRef.current = source

    source.onmessage = (msg) => {
      if (msg.data === '[DONE]') {
        source.close()
        setRunning(false)
        return
      }
      let evt
      try {
        evt = JSON.parse(msg.data)
      } catch {
        return
      }
      if (evt.event === 'result') {
        setResult(evt.detail)
        if (evt.detail.error) setError(evt.detail.error)
        setElapsed(((Date.now() - startRef.current) / 1000).toFixed(1))
        setRunning(false)
        source.close()
      } else {
        setEvents((prev) => [...prev, evt])
      }
    }
    source.onerror = () => {
      source.close()
      setRunning(false)
      setError((prev) => prev || 'Lost connection to the Coordinator. Is it running on :8000?')
    }
  }

  function copyApplication() {
    const app = result?.application
    if (!app) return
    const text =
      `Tailored for: ${result.top_job?.title} @ ${result.top_job?.company}\n\n` +
      app.bullets.map((b) => `• ${b}`).join('\n') +
      `\n\n${app.cover_note}`
    const done = () => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done))
    } else {
      fallbackCopy(text, done)
    }
  }

  function fallbackCopy(text, done) {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    done()
  }

  const jobs = result?.jobs || []
  const app = result?.application

  return (
    <div className="page">
      <header>
        <h1>A2A Job Team</h1>
        <p className="subtitle">
          Two agents, two frameworks, one protocol — Scout (LangGraph) finds the
          jobs, Scribe (plain Python + Gemini) writes the application.
        </p>
      </header>

      <form
        className="run-form"
        onSubmit={(e) => {
          e.preventDefault()
          run()
        }}
      >
        <label>
          Role
          <input value={role} onChange={(e) => setRole(e.target.value)} disabled={running} />
        </label>
        <label>
          Location
          <input value={location} onChange={(e) => setLocation(e.target.value)} disabled={running} />
        </label>
        <button type="submit" disabled={running}>
          {running ? 'Running…' : 'Run the team'}
        </button>
      </form>

      {(running || elapsed) && (
        <p className="status">
          {running ? 'Agents are working — watch the trace below.' : `Done in ${elapsed}s.`}
        </p>
      )}

      {error && <div className="error">{error}</div>}

      <div className="columns">
        <section className="feed-panel">
          <h2>Live trace</h2>
          <div className="feed" ref={feedRef}>
            {events.length === 0 && (
              <p className="feed-empty">
                {running ? 'Connecting…' : 'Run the team to see every handoff here, live.'}
              </p>
            )}
            {events.map((evt) => (
              <div key={evt.seq} className="feed-event">
                <span
                  className="agent-dot"
                  style={{ background: AGENT_COLORS[evt.agent] || '#fff' }}
                />
                <span className="agent-name">{evt.agent}</span>
                <span className="event-name">{evt.event.replaceAll('_', ' ')}</span>
                <span className="event-detail">{describeEvent(evt)}</span>
                <span className="event-time">
                  {new Date(evt.time).toLocaleTimeString('en-IN', { hour12: false })}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="results-panel">
          <h2>Jobs found {jobs.length > 0 && `(${jobs.length})`}</h2>
          {jobs.length === 0 && (
            <p className="muted">No jobs yet — they appear here once Scout finishes.</p>
          )}
          <div className="job-list">
            {jobs.map((job, i) => (
              <article key={job.link || job.title} className={i === 0 ? 'job-card top' : 'job-card'}>
                <div className="job-head">
                  <h3>{job.title}</h3>
                  <span className="score">score {job.score}</span>
                </div>
                <p className="job-meta">
                  {job.company} · {job.location}
                  {i === 0 && <span className="top-badge">top pick — sent to Scribe</span>}
                </p>
                {job.snippet && <p className="job-snippet">{job.snippet}</p>}
                {job.why_it_fits && <p className="job-why">Why it fits: {job.why_it_fits}</p>}
                {job.link && (
                  <a href={job.link} target="_blank" rel="noreferrer">
                    Open listing ↗
                  </a>
                )}
              </article>
            ))}
          </div>

          {app && (
            <div className="application">
              <div className="app-head">
                <h2>Tailored application {app.model && <span className="model">({app.model})</span>}</h2>
                <button type="button" onClick={copyApplication}>
                  {copied ? 'Copied ✓' : 'Copy all'}
                </button>
              </div>
              <ul className="bullets">
                {app.bullets.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
              <p className="cover-note">{app.cover_note}</p>
            </div>
          )}
        </section>
      </div>

      <footer>
        Local demo — nothing is applied for. Scout searches, Scribe drafts, you decide.
      </footer>
    </div>
  )
}
