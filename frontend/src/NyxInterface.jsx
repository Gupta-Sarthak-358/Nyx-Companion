import { useRef, useEffect, useState } from 'react'
import styles from './NyxInterface.module.css'
import { Icons } from './Icons'

const SUGGESTED = [
  "What's the latest knowledge graph summary?",
  'Explain something from my uploaded PDFs',
  'What can you help me with today?',
]

function formatTime(d) {
  const h = d.getHours()
  const m = d.getMinutes()
  const ampm = h >= 12 ? 'PM' : 'AM'
  return `${(h % 12) || 12}:${m.toString().padStart(2, '0')} ${ampm}`
}

function formatContent(text, styles) {
  const parts = text.split(/(```[\s\S]*?```)/)
  return parts.map((part, i) => {
    if (part.startsWith('```') && part.endsWith('```')) {
      const inner = part.slice(3, -3)
      const langMatch = inner.match(/^(\w+)\n/)
      const lang = langMatch ? langMatch[1] : ''
      const code = langMatch ? inner.slice(langMatch[0].length) : inner
      return (
        <div key={i} className={styles.codeBlock}>
          {lang && <div className={styles.codeLang}>{lang}</div>}
          <pre className={styles.codePre}>{code}</pre>
        </div>
      )
    }
    const inlineParts = part.split(/(`[^`]+`)/)
    return (
      <span key={i}>
        {inlineParts.map((ip, j) => {
          if (ip.startsWith('`') && ip.endsWith('`')) {
            return <code key={j} className={styles.inlineCode}>{ip.slice(1, -1)}</code>
          }
          return <span key={j}>{ip}</span>
        })}
      </span>
    )
  })
}

export default function NyxInterface({
  transcript, isThinking, chatInput, setChatInput, sendChatMessage,
  nyxRagEnabled, setNyxRagEnabled, nyxTtsEnabled, setNyxTtsEnabled,
  isRecording, toggleRecording, isSessionActive, isAiSpeaking,
}) {
  const chatEndRef = useRef(null)
  const textareaRef = useRef(null)
  const [knowledgeStats, setKnowledgeStats] = useState(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  useEffect(() => {
    if (transcript.length !== 0) return
    fetch('/api/knowledge/stats')
      .then(r => r.json())
      .then(d => { if (!d.error) setKnowledgeStats(d) })
      .catch(() => {})
  }, [transcript.length])

  const handleSuggestion = (text) => {
    setChatInput(text)
    textareaRef.current?.focus()
  }

  const handleInput = (e) => {
    setChatInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendChatMessage()
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.chatViewport}>
        <div className={styles.chatCenter}>
          {transcript.length === 0 ? (
            <div className={styles.welcomeBlock}>
              <div className={styles.welcomeIcon}>
                <Icons.Bot size={32} style={{ color: 'var(--primary)' }} />
              </div>
              <h2 className={styles.welcomeTitle}>How can I assist you?</h2>
              <p className={styles.welcomeSub}>Connected to Nyx Core with full context memory. Proceed with analysis or standard queries.</p>
              
              <div className={styles.suggestedPrompts}>
                {SUGGESTED.map((s) => (
                  <button key={s} type="button" className={styles.chip} onClick={() => handleSuggestion(s)}>
                    {s}
                  </button>
                ))}
              </div>

              {knowledgeStats && (
                <div className={styles.emptyStats}>
                  <span>{knowledgeStats.chunks || 0} chunks</span>
                  <span>{Object.keys(knowledgeStats.sources || {}).length} sources</span>
                </div>
              )}
            </div>
          ) : (
            transcript.map((entry) => (
              <div key={entry._id} className={`${styles.row} ${entry.role === 'user' ? styles.rowUser : styles.rowNyx}`}>
                {entry.role === 'ai' && (
                  <div className={styles.avatar}>
                    <Icons.Bot size={16} style={{ color: 'var(--primary)' }} />
                  </div>
                )}
                <div className={styles.bubbleWrap}>
                  <div className={entry.role === 'user' ? styles.userBubble : styles.nyxBubble}>
                    <div className={styles.bubbleText}>
                      {formatContent(entry.text, styles)}
                      {isThinking && !entry.isFinal && entry.role === 'ai' && (
                        <div className={styles.streamingCursor} />
                      )}
                    </div>
                  </div>
                  <span className={styles.timestamp}>
                    {entry.role === 'user' ? 'You' : 'Nyx Assistant'} • {formatTime(new Date())}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      <div className={styles.inputArea}>
        <div className={styles.inputCenter}>
          <div className={styles.inputPanel}>
            <textarea
              ref={textareaRef}
              className={styles.textareaField}
              value={chatInput}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Message Nyx Core..."
              rows={1}
            />
            
            <div className={styles.toolbar}>
              <div className={styles.toggleStrip}>
                <label className={styles.toggleWrapper}>
                  <div className={`${styles.switch} ${nyxRagEnabled ? styles.switchOn : ''}`} onClick={() => setNyxRagEnabled(!nyxRagEnabled)}>
                    <div className={styles.switchThumb} />
                  </div>
                  <span className={styles.toggleLabel}><Icons.Knowledge size={14} /> Knowledge</span>
                </label>
                <label className={styles.toggleWrapper}>
                  <div className={`${styles.switch} ${nyxTtsEnabled ? styles.switchOn : ''}`} onClick={() => setNyxTtsEnabled(!nyxTtsEnabled)}>
                    <div className={styles.switchThumb} />
                  </div>
                  <span className={styles.toggleLabel}><Icons.Mic size={14} /> Voice</span>
                </label>
              </div>

              <div className={styles.actionGroup}>
                <button className={styles.attachBtn}><Icons.Settings size={18} /></button>
                <button className={`${styles.micBtn} ${isRecording ? styles.micActive : ''}`} onClick={toggleRecording}>
                  {isRecording && <div className={styles.micPing} />}
                  <Icons.Mic size={18} />
                </button>
                <button className={styles.sendBtn} onClick={sendChatMessage} disabled={!chatInput.trim()}>
                  <Icons.Send size={18} />
                </button>
              </div>
            </div>
          </div>
          <p className={styles.disclaimer}>Nyx Assistant can make mistakes. Verify critical technical analysis.</p>
        </div>
      </div>
    </div>
  )
}
