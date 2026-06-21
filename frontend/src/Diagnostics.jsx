import { useState, useEffect, useCallback } from 'react'
import ModalShell from './ModalShell'
import { Icons } from './Icons'

function Diagnostics({ show, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const fetchDiagnostics = useCallback(async () => {
    setError(null)
    try {
      const res = await fetch('/api/diagnostics')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    if (show) fetchDiagnostics()
  }, [show, fetchDiagnostics])

  return (
    <ModalShell isOpen={show} onClose={onClose} title="System Diagnostics">
      {error && (
        <div style={{ color: 'var(--color-danger)', padding: 'var(--space-3) 0', fontSize: 'var(--text-sm)' }}>
          Failed to load: {error}
        </div>
      )}

      {data?.checks && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
          <div>
            <h4 style={{ margin: '0 0 var(--space-3) 0', color: 'var(--text-muted)', fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Core Services
            </h4>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
              <tbody>
                {['llm', 'whisper', 'piper', 'embedding', 'reranker', 'chroma'].map((key) => {
                  const c = data.checks[key]
                  if (!c) return null
                  const ok = c.ok !== false
                  return (
                    <tr key={key} style={{ borderBottom: '1px solid var(--border-muted)' }}>
                      <td style={{ padding: 'var(--space-3) 0', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{key}</td>
                      <td style={{ padding: 'var(--space-3) 0', textAlign: 'right' }}>
                        {ok ? (
                          <span style={{ color: 'var(--color-success)', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end' }}>
                            <Icons.Check size={16} /> Operational
                          </span>
                        ) : (
                          <span style={{ color: 'var(--color-danger)' }}>Non-Responsive{c.error ? `: ${c.error}` : ''}</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
                <tr style={{ borderBottom: '1px solid var(--border-muted)' }}>
                  <td style={{ padding: 'var(--space-3) 0', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>sessions</td>
                  <td style={{ padding: 'var(--space-3) 0', textAlign: 'right', color: 'var(--text-muted)' }}>{data.checks.sessions?.count ?? 0} active</td>
                </tr>
              </tbody>
            </table>
          </div>

          {data?.checks?.metrics && (
            <div>
              <h4 style={{ margin: '0 0 var(--space-3) 0', color: 'var(--text-muted)', fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Latency (ms)
              </h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
                <tbody>
                  {Object.entries(data.checks.metrics).map(([key, val]) => (
                    <tr key={key} style={{ borderBottom: '1px solid var(--border-muted)' }}>
                      <td style={{ padding: 'var(--space-2) 0', color: 'var(--text-muted)' }}>{key}</td>
                      <td style={{ padding: 'var(--space-2) 0', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                        {typeof val === 'number' ? Math.round(val) : JSON.stringify(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-4)', paddingTop: 'var(--space-4)', borderTop: '1px solid var(--border-default)' }}>
        <button
          onClick={fetchDiagnostics}
          style={{
            background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', color: 'var(--text-primary)',
            padding: 'var(--space-2) var(--space-4)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-sm)',
            cursor: 'pointer', fontFamily: 'var(--font-sans)', transition: 'var(--transition-fast)',
          }}
        >
          Refresh
        </button>
      </div>
    </ModalShell>
  )
}

export default Diagnostics
