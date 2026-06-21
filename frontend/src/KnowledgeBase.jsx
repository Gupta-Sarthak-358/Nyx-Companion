import { useState, useEffect } from 'react'
import ModalShell from './ModalShell'
import { Icons } from './Icons'

export default function KnowledgeBase({
  show, onClose, knowledgeStats, knowledgeSources,
  isIngesting, onIngest, onUpload, onDelete, fileInputRef, ingestProgress,
}) {
  const [ragLog, setRagLog] = useState([])
  const [showAllSources, setShowAllSources] = useState(false)

  useEffect(() => {
    if (!show) return
    fetch('/api/rag/log')
      .then(r => r.json())
      .then(d => setRagLog(d.entries || []))
      .catch(() => {})
  }, [show])

  const pct = ingestProgress?.total_files > 0
    ? Math.round(((ingestProgress.current_file - 1) + (ingestProgress.step / ingestProgress.total_steps)) / ingestProgress.total_files * 100)
    : 0

  const rateEntry = async (timestamp, rating) => {
    await fetch('/api/rag/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ timestamp, rating }),
    })
    setRagLog(prev => prev.map(e => e.timestamp === timestamp ? { ...e, rating } : e))
  }

  const sourcesList = Object.entries(knowledgeSources)

  return (
    <ModalShell isOpen={show} onClose={onClose} title="Knowledge Base">
      {/* Header Stats */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid rgba(79, 69, 55, 0.2)' }}>
        <div style={{ display: 'flex', gap: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            <Icons.Bot size={16} style={{ color: 'var(--primary)' }} />
            <span>{knowledgeStats.chunks || 0} Chunks</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            <Icons.BookOpen size={16} style={{ color: 'var(--secondary)' }} />
            <span>{sourcesList.length} Sources</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--tertiary)' }}>
            <Icons.Check size={16} />
            <span>Status: Ready</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button className="glass-panel" onClick={onIngest} style={{ padding: '8px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontFamily: 'var(--font-mono)', border: '1px solid var(--border-muted)', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icons.Retry size={14} /> Re-ingest All
          </button>
          <label className="glow-border" style={{ padding: '8px 16px', borderRadius: 4, background: 'var(--primary)', color: '#080807', cursor: 'pointer', fontSize: 12, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icons.Upload size={14} /> Upload PDF
            <input type="file" accept=".pdf" ref={fileInputRef} onChange={onUpload} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
        {/* Ingestion Progress */}
        {isIngesting && ingestProgress && (
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid rgba(79, 69, 55, 0.2)', padding: 20, borderRadius: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 12 }}>
              <h3 style={{ fontSize: 14, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', margin: 0 }}>Ingesting: "{ingestProgress.file || 'Initializing...'}"</h3>
              <span style={{ fontSize: 24, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--primary)' }}>{pct}%</span>
            </div>
            <div style={{ height: 8, background: 'var(--bg-surface-3)', borderRadius: 99, overflow: 'hidden' }}>
              <div className="animate-progress" style={{ height: '100%', width: `${pct}%`, borderRadius: 99, transition: 'width 0.3s ease' }} />
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, textAlign: 'right' }}>
              Processing chunk {ingestProgress.step || 0} of {ingestProgress.total_steps || '...'}
            </p>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
          {/* Active Sources Table */}
          <section>
            <h2 style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <Icons.BookOpen size={24} style={{ color: 'var(--primary)' }} /> Active Sources
            </h2>
            <div style={{ background: 'var(--bg-surface-1)', border: '1px solid rgba(79, 69, 55, 0.2)', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                <thead style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid rgba(79, 69, 55, 0.1)', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  <tr>
                    <th style={{ padding: '12px 16px' }}>Source Name</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right' }}>Chunks</th>
                    <th style={{ padding: '12px 16px' }}>Pages</th>
                    <th style={{ padding: '12px 16px' }}></th>
                  </tr>
                </thead>
                <tbody style={{ fontSize: 14 }}>
                  {sourcesList.slice(0, 5).map(([name, info]) => (
                    <tr key={name} style={{ borderBottom: '1px solid rgba(79, 69, 55, 0.1)', transition: 'background 0.2s' }}>
                      <td style={{ padding: '12px 16px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Icons.BookOpen size={14} style={{ color: 'var(--primary-container)' }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>{name}</span>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{info.chunks}</td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>{info.pages || '1-?'}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button onClick={() => onDelete(name)} style={{ background: 'none', border: 'none', color: 'var(--outline)', cursor: 'pointer', padding: 4, borderRadius: 4 }}>
                          <Icons.Close size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ padding: 12, textAlign: 'center', borderTop: '1px solid rgba(79, 69, 55, 0.1)' }}>
                <button style={{ background: 'none', border: 'none', fontSize: 12, color: 'var(--primary)', cursor: 'pointer', fontWeight: 600 }}>View All Sources</button>
              </div>
            </div>
          </section>

          {/* RAG Query Log */}
          <section>
            <h2 style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <Icons.Retry size={24} style={{ color: 'var(--secondary)' }} /> RAG Query Log
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {ragLog.slice(-4).reverse().map((entry, i) => (
                <div key={entry.timestamp || i} style={{ background: 'var(--bg-surface-1)', border: '1px solid rgba(79, 69, 55, 0.2)', padding: 16, borderRadius: 8, position: 'relative' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <p style={{ margin: 0, fontWeight: 500, fontSize: 14, color: 'var(--text-primary)' }}>"{entry.query}"</p>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => rateEntry(entry.timestamp, 'thumbs_up')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: entry.rating === 'thumbs_up' ? 'var(--tertiary)' : 'var(--outline)' }}><Icons.Check size={16} /></button>
                      <button onClick={() => rateEntry(entry.timestamp, 'thumbs_down')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: entry.rating === 'thumbs_down' ? 'var(--error)' : 'var(--outline)' }}><Icons.Close size={16} /></button>
                    </div>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.5 }} className="line-clamp-2">{entry.response}</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {[...new Set((entry.chunks || []).map(c => c.source))].filter(Boolean).map(src => (
                      <span key={src} style={{ padding: '2px 8px', borderRadius: 4, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', fontSize: 10, fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Icons.Bot size={10} /> {src}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              {ragLog.length === 0 && <div style={{ textAlign: 'center', color: 'var(--text-disabled)', padding: 32 }}>No queries yet.</div>}
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button style={{ background: 'none', border: 'none', fontSize: 12, color: 'var(--secondary)', cursor: 'pointer', fontWeight: 600 }}>View Full History</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </ModalShell>
  )
}
