import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, Check, CheckCircle2, ChevronRight, Clock3,
  Database, GitBranch, Play, RefreshCw, RotateCcw, Server, ShieldCheck,
  Undo2, X, Zap,
} from 'lucide-react'

const API = import.meta.env.VITE_API_URL || ''

type Node = {
  id: string; name: string; kind: string; health: string; state: string;
  version: string; desired_version: string; in_load_balancer: boolean;
  error_rate: number; latency_ms: number;
}
type Topology = { nodes: Node[]; edges: { source: string; target: string }[] }
type Evidence = { key: string; label: string; passed: boolean; observed: unknown; required: unknown }
type Gate = { gate: string; target: string; outcome: 'pass' | 'fail'; summary: string; evidence: Evidence[] }
type Step = { id: string; order: number; target: string; action: string; objective: string; status: string; decision_summary?: string }
type Run = {
  id: string; request: string; status: string; created_at: string; started_at?: string;
  completed_at?: string; plan: Step[]; gate_decisions: Gate[]; human_interventions: number;
  availability_preserved: boolean; report?: Record<string, unknown>;
}
type Event = {
  id: string; timestamp: string; event_type: string; target?: string; summary: string;
  status: string; tool?: string; evidence: Record<string, unknown>;
}
type Config = { agent_runtime: string; persistence_backend: string; event_backend: string; model: string }

const fetchJson = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${API}${path}`, init)
  if (!response.ok) throw new Error(await response.text())
  return response.status === 204 ? (undefined as T) : response.json()
}

const statusName: Record<string, string> = {
  received: 'Received', planning: 'Planning', preflight: 'Pre-flight', ready: 'Ready',
  executing: 'Executing', verifying: 'Verifying', rolling_back: 'Rolling back',
  replanning: 'Replanning', deferred: 'Deferred', completed: 'Completed',
  completed_with_warnings: 'Completed with warnings', failed: 'Failed', escalated: 'Escalated',
}

const stepIcon = (status: string) => {
  if (status === 'completed') return <Check size={14}/>
  if (status === 'rolled_back') return <Undo2 size={14}/>
  if (status === 'deferred' || status === 'blocked') return <X size={14}/>
  if (status === 'in_progress') return <RefreshCw size={14}/>
  return <ChevronRight size={14}/>
}

function NodeCard({ node }: { node?: Node }) {
  if (!node) return null
  const Icon = node.kind === 'database' ? Database : node.kind === 'load_balancer' ? GitBranch : Server
  return <article className={`node-card ${node.state}`}>
    <div className="node-top"><span className="node-icon"><Icon size={16}/></span><div><strong>{node.name}</strong><small>{node.kind.replace('_', ' ')}</small></div><span className={`pulse ${node.health}`}/></div>
    <div className="node-state">{node.state.replace('_', ' ')}</div>
    <div className="node-meta"><span>v{node.version}</span><span>{node.latency_ms}ms</span><span>{node.error_rate}% err</span></div>
  </article>
}

export function App() {
  const [topology, setTopology] = useState<Topology>({ nodes: [], edges: [] })
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedId, setSelectedId] = useState<string>()
  const [showHistory, setShowHistory] = useState(true)
  const [events, setEvents] = useState<Event[]>([])
  const [config, setConfig] = useState<Config>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const selected = useMemo(
    () => showHistory ? runs.find(run => run.id === selectedId) || runs[0] : undefined,
    [runs, selectedId, showHistory],
  )
  const nodes = useMemo(() => Object.fromEntries(topology.nodes.map(node => [node.id, node])), [topology])
  const gate = useMemo(() => selected?.gate_decisions.find(item => item.gate === 'database_change') || selected?.gate_decisions.at(-1), [selected])
  const progress = selected?.plan.length ? Math.round(selected.plan.filter(step => ['completed', 'rolled_back', 'deferred'].includes(step.status)).length / selected.plan.length * 100) : 0

  const refresh = useCallback(async () => {
    try {
      const [topologyData, runData, configData] = await Promise.all([
        fetchJson<Topology>('/api/topology'), fetchJson<Run[]>('/api/maintenance'), fetchJson<Config>('/api/config'),
      ])
      setTopology(topologyData); setRuns(runData); setConfig(configData)
      const activeId = showHistory ? selectedId || runData[0]?.id : undefined
      if (activeId) {
        setSelectedId(activeId)
        setEvents(await fetchJson<Event[]>(`/api/maintenance/${activeId}/events`))
      } else setEvents([])
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to reach API') }
  }, [selectedId, showHistory])

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0)
    const timer = window.setInterval(() => void refresh(), 800)
    return () => {
      window.clearTimeout(initialRefresh)
      window.clearInterval(timer)
    }
  }, [refresh])

  const start = async () => {
    setBusy(true)
    try {
      const run = await fetchJson<Run>('/api/demo/start', { method: 'POST' })
      setShowHistory(true); setSelectedId(run.id)
      setRuns(previous => [run, ...previous.filter(item => item.id !== run.id)])
      setEvents([])
    } finally { setBusy(false) }
  }

  const reset = async () => {
    setBusy(true)
    try {
      await fetchJson('/api/demo/reset', { method: 'POST' })
      setShowHistory(false); setSelectedId(undefined); setEvents([])
    }
    finally { setBusy(false) }
  }

  return <main>
    <header className="topbar">
      <div className="brand"><div className="clockmark">03:17</div><div><strong>Autonomous Maintenance Window</strong><span>Sleep through the maintenance window.</span></div></div>
      <div className="runtime"><span className="live-dot"/> SYSTEM ARMED <code>{config?.model || 'connecting'}</code></div>
    </header>

    <section className="hero">
      <div className="hero-copy"><p className="eyebrow">AFTER-HOURS CHANGE EXECUTION</p><h1>03:17 is when no sysadmin<br/><em>wants to be awake.</em></h1><p>Gemini reasons. Evidence Gates authorize. Every action is verified—and failed changes roll back automatically.</p></div>
      <div className="hero-actions"><button className="primary" disabled={busy} onClick={start}><Play size={16}/> Start autonomous maintenance</button><button className="reset" disabled={busy} onClick={reset}><RotateCcw size={16}/> Reset environment</button></div>
    </section>

    {error && <div className="error">API connection error: {error}</div>}

    <section className="request-strip">
      <div><p className="eyebrow">APPROVED CHANGE REQUEST</p><p>{selected?.request || "Update the web tier and perform the approved database maintenance during tonight's maintenance window. Preserve availability and rollback failed changes."}</p></div>
      <div className="window-stats"><div><span>WINDOW</span><strong>03:17–04:00</strong></div><div><span>PROGRESS</span><strong>{progress}%</strong></div><div><span>HUMAN INTERVENTIONS</span><strong className="lime">{selected?.human_interventions ?? 0}</strong></div><div><span>STATUS</span><strong className={selected?.status === 'completed_with_warnings' ? 'amber' : 'cyan'}>{selected ? statusName[selected.status] : 'Standing by'}</strong></div></div>
    </section>

    <section className="command-grid">
      <aside className="plan-panel panel">
        <div className="panel-head"><div><p className="eyebrow">LIVE PLAN</p><h2>Execution strategy</h2></div><Zap size={17}/></div>
        <div className="plan-list">{!selected && <div className="empty"><Clock3/><p>Awaiting change window</p></div>}{selected?.plan.map(step => <div className={`plan-step ${step.status}`} key={step.id}>
          <span className="step-status">{stepIcon(step.status)}</span><div><strong>{step.target.toUpperCase()}</strong><p>{step.objective}</p>{step.decision_summary && <small>{step.decision_summary}</small>}</div><span className="step-label">{step.status.replace('_', ' ')}</span>
        </div>)}</div>
      </aside>

      <section className="topology-panel panel">
        <div className="panel-head"><div><p className="eyebrow">LIVE INFRASTRUCTURE</p><h2>Maintenance topology</h2></div><span className="availability"><ShieldCheck size={14}/> Availability {selected?.availability_preserved === false ? 'at risk' : 'preserved'}</span></div>
        <div className="topology">
          <div className="topo-row one"><NodeCard node={nodes['load-balancer']}/></div>
          <div className="connector fork"/>
          <div className="topo-row two"><NodeCard node={nodes.web01}/><NodeCard node={nodes.web02}/></div>
          <div className="connector join"/>
          <div className="topo-row one"><NodeCard node={nodes.worker}/></div>
          <div className="connector straight"/>
          <div className="topo-row one"><NodeCard node={nodes.database}/></div>
        </div>
      </section>

      <aside className={`evidence-panel panel ${gate?.outcome || ''}`}>
        <div className="panel-head"><div><p className="eyebrow">DETERMINISTIC AUTHORITY</p><h2>Evidence Gate</h2></div><ShieldCheck size={18}/></div>
        {!gate ? <div className="empty"><ShieldCheck/><p>Evidence not evaluated yet</p></div> : <>
          <div className="gate-title"><span>{gate.target.toUpperCase()} CHANGE GATE</span><strong>{gate.outcome === 'pass' ? 'PASS' : 'BLOCKED'}</strong></div>
          <div className="evidence-list">{gate.evidence.map(item => <div className={item.passed ? 'passed' : 'failed'} key={item.key}><span>{item.passed ? <Check/> : <X/>}</span><div><strong>{item.label}</strong><small>Observed: {typeof item.observed === 'object' ? JSON.stringify(item.observed) : String(item.observed)}</small></div></div>)}</div>
          <div className="gate-decision"><span>DECISION</span><p>{gate.summary}</p></div>
        </>}
      </aside>
    </section>

    <section className="lower-grid">
      <section className="timeline-panel panel"><div className="panel-head"><div><p className="eyebrow">PROOF OF ACTION</p><h2>Autonomous activity</h2></div><Activity size={17}/></div>
        <div className="timeline">{events.length === 0 && <div className="empty"><Activity/><p>No maintenance activity yet</p></div>}{events.map((event, index) => <div className="timeline-event" key={event.id}>
          <div className="rail"><span className={event.status}/>{index < events.length - 1 && <i/>}</div><time>{new Date(event.timestamp).toLocaleTimeString([], {hour12:false})}</time><div><strong>{event.summary}</strong><p>{event.tool ? `TOOL · ${event.tool}` : event.event_type.replace('_', ' ')}{event.target ? ` · ${event.target.toUpperCase()}` : ''}</p></div>
        </div>)}</div>
      </section>

      <aside className="outcome-panel panel"><div className="panel-head"><div><p className="eyebrow">WINDOW OUTCOME</p><h2>Final maintenance report</h2></div><CheckCircle2 size={18}/></div>
        {!selected?.report ? <div className="empty"><Clock3/><p>Report generated at completion</p></div> : <div className="outcomes">
          <div className="outcome success"><CheckCircle2/><span><small>WEB01</small><strong>UPDATED + VERIFIED</strong></span></div>
          <div className="outcome rollback"><Undo2/><span><small>WEB02</small><strong>ROLLED BACK + VERIFIED</strong></span></div>
          <div className="outcome blocked"><AlertTriangle/><span><small>DATABASE</small><strong>DEFERRED BY EVIDENCE POLICY</strong></span></div>
          <div className="outcome availability-row"><ShieldCheck/><span><small>SERVICE AVAILABILITY</small><strong>PRESERVED</strong></span></div>
          <p className="follow-up">Full audit report persisted · Manual intervention during window: 0</p>
        </div>}
      </aside>
    </section>

    <footer><span>Google Cloud Run · Pub/Sub · Firestore · Vertex AI · Google ADK</span><span>{config?.agent_runtime || 'local'} planner / {config?.persistence_backend || 'memory'} state</span></footer>
  </main>
}
