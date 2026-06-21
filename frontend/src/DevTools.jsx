import { useState, useEffect } from 'react'
import ModalShell from './ModalShell'

export default function DevTools({ show, onClose }) {
  const [sessions, setSessions] = useState([])
  const [selected, setSelected] = useState(null)
  const [sessionData, setSessionData] = useState(null)
  const [ragLog, setRagLog] = useState([])
  const [tab, setTab] = useState('sessions')

  useEffect(() => {
    if (!show) return
    fetch('/api/sessions').then(r => r.json()).then(d => setSessions(d.sessions || [])).catch(() => {})
    fetch('/api/rag/log').then(r => r.json()).then(d => setRagLog(d.entries || [])).catch(() => {})
  }, [show])

  const loadSession = async (id) => {
    setSelected(id)
    const res = await fetch(`/api/sessions/${encodeURIComponent(id)}`)
    const data = await res.json()
    setSessionData(data.session || null)
  }

  const exportSession = () => {
    if (!sessionData) return
    const blob = new Blob([JSON.stringify(sessionData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session-${selected}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const tabStyle = (active) => ({
    background: 'none', border: 'none', color: active ? 'var(--text-primary)' : 'var(--text-muted)',
    padding: 'var(--space-2) var(--space-4)', cursor: 'pointer', fontSize: 'var(--text-sm)',
    borderBottom: active ? '2px solid var(--brand-color)' : '2px solid transparent',
    transition: 'var(--transition-fast)',
  })

  return (
    <ModalShell isOpen={show} onClose={onClose} title="Developer Tools">
      <div style={{ display: 'flex', gap: '0', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-default)' }}>
        <button style={tabStyle(tab === 'sessions')} onClick={() => setTab('sessions')}>Sessions</button>
        <button style={tabStyle(tab === 'rag')} onClick={() => setTab('rag')}>RAG Queries</button>
        <button style={tabStyle(tab === 'metrics')} onClick={() => setTab('metrics')}>Metrics</button>
      </div>

      {tab === 'sessions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {sessions.length === 0 && (
            <p style={{ color: 'var(--text-disabled)', fontStyle: 'italic', textAlign: 'center', fontSize: 'var(--text-sm)' }}>
              No saved sessions.
            </p>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', maxHeight: '180px', overflowY: 'auto' }}>
            {sessions.map(id => (
              <div key={id}
                onClick={() => loadSession(id)}
                style={{
                  display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: 'var(--text-xs)',
                  fontFamily: 'var(--font-mono)', color: selected === id ? 'var(--text-primary)' : 'var(--text-muted)',
                  background: selected === id ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
                }}
              >
                <span>{id}</span>
                <span>&rarr;</span>
              </div>
            ))}
          </div>
          {sessionData && (
            <div style={{ borderTop: '1px solid var(--border-default)', paddingTop: 'var(--space-3)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', fontFamily: 'var(--font-mono)' }}>
                  {selected?.slice(0, 12)}...
                </span>
                <button onClick={exportSession} style={{
                  background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)',
                  color: 'var(--text-primary)', padding: 'var(--space-1) var(--space-3)',
                  borderRadius: 'var(--radius-md)', fontSize: 'var(--text-xs)', cursor: 'pointer',
                }}>Export JSON</button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                <span style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  Mode: {sessionData.current_mode || 'unknown'}
                </span>
                <span style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  Turns: {sessionData.history_turns?.length || 0}
                </span>
              </div>
              <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '2px', fontSize: 'var(--text-xs)' }}>
                {(sessionData.history_turns || []).map((turn, i) => (
                  <div key={i} style={{ padding: 'var(--space-1) var(--space-2)', borderRadius: '4px', background: 'rgba(255,255,255,0.02)', wordBreak: 'break-word' }}>
                    {turn}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'rag' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', maxHeight: '60vh', overflowY: 'auto' }}>
          {ragLog.length === 0 && (
            <p style={{ color: 'var(--text-disabled)', fontStyle: 'italic', textAlign: 'center', fontSize: 'var(--text-sm)' }}>
              No RAG queries yet.
            </p>
          )}
          {ragLog.slice(-20).reverse().map((entry, i) => (
            <div key={entry.timestamp || i} style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)', fontSize: 'var(--text-xs)' }}>
              <div style={{ color: 'var(--text-primary)', fontWeight: 'var(--weight-semibold)' }}>Q: {entry.query}</div>
              <div style={{ color: 'var(--text-muted)' }}>A: {entry.response?.slice(0, 300)}{entry.response?.length > 300 ? '...' : ''}</div>
              <div style={{ display: 'flex', gap: 'var(--space-3)', color: 'rgba(255,255,255,0.3)', marginTop: 'var(--space-1)' }}>
                <span>{entry.chunks?.length || 0} chunks</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {[...new Set((entry.chunks || []).map(c => c.source))].filter(Boolean).join(', ')}
                </span>
                {entry.rating && (
                  <span style={{
                    padding: '0 6px', borderRadius: '3px', fontSize: '10px',
                    background: entry.rating === 'thumbs_up' ? 'rgba(45,164,78,0.2)' : 'rgba(224,40,40,0.2)',
                    color: entry.rating === 'thumbs_up' ? 'var(--color-success)' : 'var(--color-danger)',
                  }}>
                    {entry.rating === 'thumbs_up' ? 'helpful' : 'not helpful'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'metrics' && <MetricsView />}
    </ModalShell>
  )
}

function MetricsView() {
  const [metrics, setMetrics] = useState(null)

  useEffect(() => {
    const f = () => fetch('/api/metrics').then(r => r.json()).then(setMetrics).catch(() => {})
    f()
    const interval = setInterval(f, 5000)
    return () => clearInterval(interval)
  }, [])

  if (!metrics) return <p style={{ color: 'var(--text-disabled)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>Loading metrics...</p>

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
      <tbody>
        {Object.entries(metrics).map(([key, val]) => (
          <tr key={key} style={{ borderBottom: '1px solid var(--border-muted)' }}>
            <td style={{ padding: 'var(--space-2) 0', color: 'var(--text-muted)' }}>{key}</td>
            <td style={{ padding: 'var(--space-2) 0', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {typeof val === 'number' ? Math.round(val) : JSON.stringify(val)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
