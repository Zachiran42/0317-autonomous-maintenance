import { useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Database, Play, RotateCcw, Server, ShieldAlert, Zap } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || ''

type Service = { id: string; name: string; health: string; cpu_percent: number; error_rate: number; latency_ms: number; restart_count: number }
type Incident = { id: string; service_id: string; scenario: string; trigger: string; status: string; probable_cause?: string; evidence: string[]; tools_used: string[]; actions: string[]; verification?: string; escalation?: Record<string, unknown>; created_at: string }
type Event = { id: string; timestamp: string; event_type: string; summary: string; status: string; tool?: string }
type Config = { agent_runtime: string; persistence_backend: string; event_backend: string; model: string }

const fetchJson = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${API}${path}`, init)
  if (!response.ok) throw new Error(await response.text())
  return response.status === 204 ? (undefined as T) : response.json()
}

const statusLabel: Record<string, string> = {
  queued: 'Queued', investigating: 'Investigating', remediating: 'Remediating',
  verifying: 'Verifying', resolved: 'Resolved', escalated: 'Escalated', failed: 'Failed',
}

export function App() {
  const [services, setServices] = useState<Service[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedId, setSelectedId] = useState<string>()
  const [events, setEvents] = useState<Event[]>([])
  const [config, setConfig] = useState<Config>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const selected = useMemo(() => incidents.find(item => item.id === selectedId), [incidents, selectedId])

  const refresh = async () => {
    try {
      const [serviceData, incidentData, configData] = await Promise.all([
        fetchJson<Service[]>('/api/services'), fetchJson<Incident[]>('/api/incidents'), fetchJson<Config>('/api/config'),
      ])
      setServices(serviceData); setIncidents(incidentData); setConfig(configData)
      const activeId = selectedId || incidentData[0]?.id
      if (activeId) {
        setSelectedId(activeId)
        setEvents(await fetchJson<Event[]>(`/api/incidents/${activeId}/events`))
      } else setEvents([])
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to reach API') }
  }

  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 1200); return () => clearInterval(timer) }, [selectedId])

  const trigger = async (scenario: 'recoverable' | 'unsafe') => {
    setBusy(true)
    try {
      const incident = await fetchJson<Incident>('/api/demo/trigger', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario }) })
      setSelectedId(incident.id); await refresh()
    } finally { setBusy(false) }
  }

  const reset = async () => { setBusy(true); try { await fetchJson('/api/demo/reset', { method: 'POST' }); setSelectedId(undefined); await refresh() } finally { setBusy(false) } }

  return <main>
    <header className="topbar">
      <div className="brand"><div className="mark"><Activity size={20}/></div><div><strong>PROJECT_NAME_TBD</strong><span>Autonomous Incident Operations</span></div></div>
      <div className="runtime"><span className="live-dot"/> Agent online <code>{config?.model || 'connecting'}</code></div>
    </header>

    <section className="hero">
      <div><p className="eyebrow">SYSTEM COMMAND</p><h1>Incidents handled.<br/><em>Before they become outages.</em></h1><p>Autonomous investigation, policy-controlled remediation, and auditable verification powered by Google ADK and Gemini.</p></div>
      <div className="controls">
        <button disabled={busy} onClick={() => trigger('recoverable')} className="primary"><Play size={17}/> Trigger recoverable incident</button>
        <button disabled={busy} onClick={() => trigger('unsafe')}><ShieldAlert size={17}/> Trigger unsafe incident</button>
        <button disabled={busy} onClick={reset} className="icon-button" aria-label="Reset demo"><RotateCcw size={17}/></button>
      </div>
    </section>

    {error && <div className="error">API connection error: {error}</div>}

    <section className="services-section"><div className="section-heading"><div><p className="eyebrow">LIVE INFRASTRUCTURE</p><h2>System overview</h2></div><span>{services.filter(s => s.health === 'healthy').length}/{services.length} services healthy</span></div>
      <div className="service-grid">{services.map(service => <article className={`service-card ${service.health}`} key={service.id}>
        <div className="service-title"><span className="service-icon">{service.id === 'database' ? <Database/> : <Server/>}</span><div><h3>{service.name}</h3><p>{service.id}</p></div><span className={`badge ${service.health}`}>{service.health}</span></div>
        <div className="metrics"><div><span>LATENCY</span><strong>{service.latency_ms}<small> ms</small></strong></div><div><span>ERROR RATE</span><strong>{service.error_rate}<small>%</small></strong></div><div><span>CPU</span><strong>{service.cpu_percent}<small>%</small></strong></div></div>
      </article>)}</div>
    </section>

    <section className="workspace">
      <aside className="queue"><div className="panel-title"><div><p className="eyebrow">INCIDENTS</p><h2>Response queue</h2></div><span>{incidents.length}</span></div>
        <div className="queue-list">{incidents.length === 0 && <div className="empty"><CheckCircle2/><p>No incidents yet</p><span>Use a demo control to begin.</span></div>}{incidents.map(item => <button key={item.id} className={`incident-row ${selectedId === item.id ? 'selected' : ''}`} onClick={() => setSelectedId(item.id)}>
          <span className={`severity ${item.status}`}>{item.status === 'escalated' ? <AlertTriangle/> : item.status === 'resolved' ? <CheckCircle2/> : <Zap/>}</span><span><strong>{item.service_id}</strong><small>{new Date(item.created_at).toLocaleTimeString()}</small></span><span className={`badge ${item.status}`}>{statusLabel[item.status]}</span>
        </button>)}</div>
      </aside>

      <section className="timeline-panel"><div className="panel-title"><div><p className="eyebrow">AUTONOMOUS EXECUTION</p><h2>Agent activity</h2></div>{selected && <span className={`badge ${selected.status}`}>{statusLabel[selected.status]}</span>}</div>
        {!selected ? <div className="empty large"><Activity/><p>Waiting for an incident</p><span>The agent timeline will appear here.</span></div> : <div className="timeline">{events.map((event, index) => <div className="timeline-event" key={event.id}>
          <div className="rail"><span className={event.status === 'error' ? 'error-node' : ''}/>{index < events.length - 1 && <i/>}</div><time>{new Date(event.timestamp).toLocaleTimeString()}</time><div><strong>{event.summary}</strong><p>{event.tool ? `Tool · ${event.tool}` : event.event_type.replace('_', ' ')}</p></div>
        </div>)}</div>}
      </section>

      <aside className="detail"><div className="panel-title"><div><p className="eyebrow">AUDIT RECORD</p><h2>Incident detail</h2></div></div>
        {!selected ? <div className="empty"><Server/><p>Select an incident</p></div> : <div className="detail-content">
          <label>TRIGGER</label><p>{selected.trigger}</p><label>PROBABLE CAUSE</label><p>{selected.probable_cause || 'Investigation in progress'}</p><label>ACTIONS</label><ul>{selected.actions.length ? selected.actions.map(a => <li key={a}>{a}</li>) : <li>No automatic action performed</li>}</ul><label>VERIFICATION</label><p>{selected.verification || (selected.escalation ? 'Escalated safely; infrastructure preserved' : 'Pending')}</p><label>TOOLS USED</label><div className="chips">{selected.tools_used.map(tool => <span key={tool}>{tool}</span>)}</div>
        </div>}
      </aside>
    </section>

    <footer><span>Google Cloud Run · Vertex AI · Firestore · Pub/Sub</span><span>Runtime: {config?.agent_runtime} / {config?.persistence_backend}</span></footer>
  </main>
}

