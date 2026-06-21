import { useState, useEffect, useRef } from 'react'
import './App.css'
import { Icons } from './Icons'
import { useWebSocket } from './useWebSocket.js'
import { useAudioPlayback } from './useAudioPlayback.js'
import { useSpeechRecognition } from './useSpeechRecognition.js'
import NyxInterface from './NyxInterface.jsx'
import InterviewRoom from './InterviewRoom.jsx'
import KnowledgeBase from './KnowledgeBase.jsx'
import Diagnostics from './Diagnostics.jsx'
import DevTools from './DevTools.jsx'
import MCQRoom from './MCQRoom.jsx'

function App() {
  const [status, setStatus] = useState('Connecting...')
  const [userSpeech, setUserSpeech] = useState('')
  const [aiResponse, setAiResponse] = useState('')
  const [transcript, setTranscript] = useState([])
  const [feedback, setFeedback] = useState(null)
  const [interviewMode, setInterviewMode] = useState('structured')
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [customScenario, setCustomScenario] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [displayedAiResponse, setDisplayedAiResponse] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [interviewReport, setInterviewReport] = useState(null)
  const [nyxRagEnabled, setNyxRagEnabled] = useState(false)
  const [nyxTtsEnabled, setNyxTtsEnabled] = useState(false)
  const [showKnowledgePanel, setShowKnowledgePanel] = useState(false)
  const [knowledgeSources, setKnowledgeSources] = useState({})
  const [knowledgeStats, setKnowledgeStats] = useState({ chunks: 0, sources: [] })
  const [isIngesting, setIsIngesting] = useState(false)
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  const [showDevTools, setShowDevTools] = useState(false)
  const [ingestProgress, setIngestProgress] = useState(null)

  const videoRef = useRef(null)
  const cameraStreamRef = useRef(null)
  const fileInputRef = useRef(null)
  const transcriptIdRef = useRef(0)
  const isNyxRef = useRef(false)
  const isSessionActiveRef = useRef(false)
  const mcqMessageHandlerRef = useRef(null)

  const { audioRef, isAiSpeaking, enqueueAudio, resetQueue } = useAudioPlayback()

  const isNyx = isSessionActive && interviewMode === 'nyx'
  const isMcq = isSessionActive && interviewMode === 'mcq'

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isNyx ? 'nyx' : '')
  }, [isNyx])

  const processStatus = (msg) => {
    setStatus(msg)
    if (msg.includes('Thinking')) setIsThinking(true)
    else if (msg.includes('Speaking') || msg.includes('Ready') || msg.includes('Connected')) setIsThinking(false)
  }

  const wsSend = (obj) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(obj))
    }
  }

  const { socketRef, sessionIdRef } = useWebSocket({
    onStatus: processStatus,
    onUserSpeech: (data) => {
      setUserSpeech(data.text)
      setFeedback(data.feedback)
      if (isNyxRef.current && isSessionActiveRef.current) {
        setTranscript(prev => [...prev, { _id: transcriptIdRef.current++, role: 'user', text: data.text, feedback: data.feedback }])
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(JSON.stringify({ type: 'chat_message', text: data.text }))
        }
      } else {
        setTranscript(prev => [...prev, { _id: transcriptIdRef.current++, role: 'user', text: data.text, feedback: data.feedback }])
      }
    },
    onAiToken: (token) => {
      setIsThinking(false)
      setTranscript(prev => {
        const lastEntry = prev[prev.length - 1]
        if (lastEntry?.role === 'ai' && !lastEntry.isFinal) {
          return [...prev.slice(0, -1), { ...lastEntry, text: lastEntry.text + token }]
        }
        return [...prev, { _id: transcriptIdRef.current++, role: 'ai', text: token, isFinal: false }]
      })
    },
    onAiResponse: (text) => {
      setAiResponse(text)
      setIsThinking(false)
      setTranscript(prev => {
        const lastEntry = prev[prev.length - 1]
        if (lastEntry?.role === 'ai' && !lastEntry.isFinal) {
          return [...prev.slice(0, -1), { ...lastEntry, text, isFinal: true }]
        }
        return [...prev, { _id: transcriptIdRef.current++, role: 'ai', text, isFinal: true }]
      })
    },
    onAudioChunk: enqueueAudio,
    onReport: setInterviewReport,
    onSessionRestored: (data) => {
      setTranscript(data.turns.map(t => {
        const colon = t.indexOf(': ')
        const entry = colon > 0
          ? { role: t.slice(0, colon).toLowerCase() === 'user' ? 'user' : 'ai', text: t.slice(colon + 2), isFinal: true }
          : { role: 'ai', text: t, isFinal: true }
        entry._id = transcriptIdRef.current++
        return entry
      }))
    },
    onMcqMessage: (data) => {
      mcqMessageHandlerRef.current?.(data)
    },
  })

  const { isRecording, timer, toggleRecording } = useSpeechRecognition({ socketRef, isSessionActive })

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key !== ' ' || ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) return
      event.preventDefault()
      if (!isSessionActive) startSession()
      else toggleRecording()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isSessionActive, isRecording])

  const sendChatMessage = (e) => {
    if (e) e.preventDefault()
    if (!chatInput.trim() || socketRef.current?.readyState !== WebSocket.OPEN) return
    socketRef.current.send(JSON.stringify({ type: 'chat_message', text: chatInput }))
    setTranscript(prev => [...prev, { _id: transcriptIdRef.current++, role: 'user', text: chatInput, isFinal: true }])
    setChatInput('')
  }

  const startSession = () => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return
    if (interviewMode !== 'nyx') setupCamera()
    socketRef.current.send(JSON.stringify({
      type: 'start', session_id: sessionIdRef.current, mode: interviewMode,
      description: customScenario,
      ...(interviewMode === 'nyx' ? { tts_enabled: nyxTtsEnabled, rag_enabled: nyxRagEnabled } : {}),
    }))
    setIsSessionActive(true)
    isSessionActiveRef.current = true
    isNyxRef.current = interviewMode === 'nyx'
    setTranscript([])
    setAiResponse('')
    setUserSpeech('')
    setFeedback(null)
    resetQueue()
  }

  const setupCamera = async () => {
    if (cameraStreamRef.current) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      cameraStreamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
    } catch (err) { console.error('Camera access error:', err) }
  }

  const toggleNyxTts = (val) => {
    setNyxTtsEnabled(val)
    if (socketRef.current?.readyState === WebSocket.OPEN && isSessionActiveRef.current) {
      socketRef.current.send(JSON.stringify({ type: 'toggle_tts', enabled: val }))
    }
  }

  const toggleNyxRag = (val) => {
    setNyxRagEnabled(val)
    if (socketRef.current?.readyState === WebSocket.OPEN && isSessionActiveRef.current) {
      socketRef.current.send(JSON.stringify({ type: 'toggle_rag', enabled: val }))
    }
  }

  const retryLastAnswer = () => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'retry' }))
      setAiResponse(''); setUserSpeech(''); setFeedback(null)
    }
  }

  const stopCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach(t => t.stop())
      cameraStreamRef.current = null
    }
  }

  const leaveInterview = () => {
    if (!window.confirm("Are you sure you want to leave?")) return
    if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify({ type: 'end_interview' }))
    if (isRecording) toggleRecording()
    stopCamera()
    setIsSessionActive(false)
    isSessionActiveRef.current = false
  }

  const fetchKnowledgeStats = async () => {
    try {
      const [statsRes, sourcesRes] = await Promise.all([fetch('/api/knowledge/stats'), fetch('/api/knowledge/sources')])
      const stats = await statsRes.json()
      const sources = await sourcesRes.json()
      if (!stats.error) setKnowledgeStats(stats)
      if (!sources.error) setKnowledgeSources(sources.sources || {})
    } catch (e) { console.error('Failed to fetch knowledge:', e) }
  }

  const deleteSource = async (source) => {
    await fetch(`/api/knowledge/sources/${encodeURIComponent(source)}`, { method: 'DELETE' })
    fetchKnowledgeStats()
  }

  const triggerIngest = async () => {
    setIsIngesting(true)
    setIngestProgress({ running: true, current_file: 0, total_files: 0, file: '', status: 'Starting...', step: 0, total_steps: 1 })
    try {
      await fetch('/api/knowledge/ingest', { method: 'POST' })
      await fetchKnowledgeStats()
    } catch (e) { console.error('Failed to ingest:', e) }
    setIsIngesting(false)
    setIngestProgress(null)
  }

  useEffect(() => {
    if (!isIngesting) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/knowledge/ingest-progress')
        const data = await res.json()
        setIngestProgress(data)
      } catch { /* ignore */ }
    }, 500)
    return () => clearInterval(interval)
  }, [isIngesting])

  const uploadPdf = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try { await fetch('/api/knowledge/upload', { method: 'POST', body: formData }); triggerIngest() }
    catch (e) { console.error('Upload failed:', e) }
  }

  const navItems = [
    { label: 'Interview', mode: 'structured' },
    { label: 'Tutor', mode: 'tutor' },
    { label: 'Assistant', mode: 'nyx' },
    { label: 'MCQ', mode: 'mcq' },
  ]

  const timerText = `${String(Math.floor(timer / 3600)).padStart(2, '0')}:${String(Math.floor((timer % 3600) / 60)).padStart(2, '0')}:${String(timer % 60).padStart(2, '0')}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* TopAppBar */}
      <header style={{
        height: 60, position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px',
        background: 'rgba(23,19,13,0.8)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(79,69,55,0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <span
            onClick={() => { if (isSessionActive) leaveInterview() }}
            style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-warning)', letterSpacing: '-0.02em', cursor: isSessionActive ? 'pointer' : 'default', transition: 'opacity 0.2s' }}
          >
            Nyx Core
          </span>
          <nav style={{ display: 'flex', alignItems: 'center', gap: 24, marginLeft: 32 }}>
            {navItems.map(({ label, mode }) => {
              const active = isSessionActive ? (interviewMode === mode || (mode === 'structured' && !['tutor','nyx'].includes(interviewMode))) : (interviewMode === mode)
              return (
                <button key={mode} onClick={() => { if (isSessionActive) { leaveInterview(); setInterviewMode(mode) } else setInterviewMode(mode) }}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: active ? 700 : 500,
                    color: active ? 'var(--color-warning)' : 'var(--text-muted)',
                    borderBottom: active ? '2px solid var(--color-warning)' : '2px solid transparent',
                    padding: '4px 0', transition: 'all 0.25s ease',
                    opacity: active ? 1 : 0.6,
                    transform: active ? 'scale(1.05)' : 'scale(1)',
                  }}
                >{label}</button>
              )
            })}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingRight: 24, borderRight: '1px solid rgba(79,69,55,0.3)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--tertiary)' }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                backgroundColor: socketRef.current?.readyState === 1 ? 'var(--tertiary)' : 'var(--error)',
                boxShadow: socketRef.current?.readyState === 1 ? '0 0 8px var(--tertiary)' : 'none',
              }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>Connected</span>
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
              {isSessionActive ? timerText : '--:--:--'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {[Icons.BookOpen, Icons.Bot, Icons.Moon].map((Icon, i) => (
              <button key={i} onClick={() => {
                if (i === 0) { setShowKnowledgePanel(true); fetchKnowledgeStats() }
                else if (i === 1) setShowDiagnostics(true)
                else setShowDevTools(true)
              }} style={{
                background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer',
                padding: 8, borderRadius: 4, transition: 'var(--transition-fast)', display: 'flex',
              }}>
                <Icon size={20} />
              </button>
            ))}
          </div>

          <div style={{
            width: 32, height: 32, borderRadius: '50%', overflow: 'hidden',
            border: '1px solid rgba(79,69,55,0.5)', cursor: 'pointer',
            background: 'linear-gradient(135deg, var(--bg-surface-2), var(--bg-surface-3))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)',
          }}>U</div>
        </div>
      </header>

      <div style={{ paddingTop: '60px', display: 'flex', flex: 1, overflow: 'hidden' }}>
        <main style={{ flex: 1, display: 'flex', overflow: 'hidden', backgroundColor: 'var(--bg-app)', position: 'relative' }}>
        {isSessionActive ? (
          isMcq ? (
            <MCQRoom wsSend={wsSend} setMessageHandler={(handler) => { mcqMessageHandlerRef.current = handler }} />
          ) : isNyx ? (
            <NyxInterface
              transcript={transcript}
              isThinking={isThinking}
              chatInput={chatInput}
              setChatInput={setChatInput}
              sendChatMessage={sendChatMessage}
              nyxRagEnabled={nyxRagEnabled}
              setNyxRagEnabled={toggleNyxRag}
              nyxTtsEnabled={nyxTtsEnabled}
              setNyxTtsEnabled={toggleNyxTts}
              isRecording={isRecording}
              toggleRecording={toggleRecording}
              isSessionActive={isSessionActive}
              isAiSpeaking={isAiSpeaking}
            />
          ) : (
            <InterviewRoom
              isThinking={isThinking}
              isAiSpeaking={isAiSpeaking}
              displayedAiResponse={displayedAiResponse}
              videoRef={videoRef}
              isRecording={isRecording}
              userSpeech={userSpeech}
              feedback={feedback}
              transcript={transcript}
              isSessionActive={isSessionActive}
              interviewMode={interviewMode}
              setInterviewMode={setInterviewMode}
              customScenario={customScenario}
              setCustomScenario={setCustomScenario}
              timer={timer}
              retryLastAnswer={retryLastAnswer}
              leaveInterview={leaveInterview}
              toggleRecording={toggleRecording}
              startSession={startSession}
              interviewReport={interviewReport}
              setInterviewReport={setInterviewReport}
            />
          )
        ) : (
          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
            {/* --- Sidebar: Setup heading + Topic textarea + Mode buttons --- */}
            <aside className="landing-sidebar">
              <div>
                <h2 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 4 }}>
                  Setup Session
                </h2>
                <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--secondary)', letterSpacing: '0.05em' }}>
                  {interviewMode === 'nyx' ? 'Nyx Assistant Active' : 'Interview Mode'}
                </p>
              </div>

              <div>
                <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 8, display: 'block' }}>
                  Topic / Scenario Context
                </label>
                <textarea
                  placeholder={
                    interviewMode === 'structured' ? "e.g., Senior Frontend Engineer interview focusing on React performance..." :
                    interviewMode === 'tutor' ? 'e.g., Focus on operating systems' :
                    interviewMode === 'nyx' ? "e.g., Ask me about system design patterns..." :
                    'e.g., Talking to a friend about emotional danger in society...'
                  }
                  value={customScenario}
                  onChange={(e) => setCustomScenario(e.target.value)}
                  rows={3}
                  style={{
                    width: '100%', resize: 'none',
                    backgroundColor: 'rgba(8,8,7,0.6)',
                    border: '1px solid rgba(79,69,55,0.2)',
                    borderBottom: '2px solid rgba(79,69,55,0.3)',
                    color: 'var(--text-primary)', padding: '10px 12px', fontSize: 13,
                    fontFamily: 'var(--font-sans)', outline: 'none', borderRadius: '8px 8px 0 0',
                    transition: 'border-color 0.2s', lineHeight: 1.5,
                  }}
                  onFocus={(e) => e.target.style.borderBottomColor = 'var(--color-warning)'}
                  onBlur={(e) => e.target.style.borderBottomColor = 'rgba(79,69,55,0.3)'}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10, display: 'block' }}>
                  Select Mode
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {[
                    { id: 'structured', icon: 'Sparkles', label: 'Standard' },
                    { id: 'topic', icon: 'BookOpen', label: 'Technical' },
                    { id: 'conversation', icon: 'Bot', label: 'Behavioral' },
                    { id: 'free', icon: 'Settings', label: 'Case Study' },
                    { id: 'tutor', icon: 'Knowledge', label: 'Tutor' },
                    { id: 'mcq', icon: 'Chart', label: 'MCQ' },
                  ].map((m) => {
                    const active = interviewMode === m.id
                    const Icon = Icons[m.icon]
                    return (
                      <button key={m.id} className={`mode-btn${active ? ' active' : ''}`} onClick={() => setInterviewMode(m.id)}>
                        <span className="mode-btn-icon">
                          <Icon size={16} />
                        </span>
                        {m.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </aside>

            {/* --- Main: Welcome + Info Cards + Setup Form --- */}
            <main style={{ flex: 1, overflowY: 'auto', padding: '48px 64px 32px', position: 'relative' }}>
              <div style={{
                position: 'fixed', top: -120, right: -120, width: 600, height: 600,
                background: 'radial-gradient(circle, rgba(246,195,103,0.07) 0%, transparent 70%)',
                pointerEvents: 'none', zIndex: 0,
              }} />
              <div style={{
                position: 'fixed', bottom: -80, left: '30%', width: 400, height: 400,
                background: 'radial-gradient(circle, rgba(173,198,255,0.05) 0%, transparent 70%)',
                pointerEvents: 'none', zIndex: 0,
              }} />

              <div style={{ maxWidth: 960, margin: '0 auto', position: 'relative', zIndex: 1 }}>
                <div style={{ marginBottom: 40 }}>
                  <h1 style={{
                    fontSize: 72, fontWeight: 700, lineHeight: 1.05, letterSpacing: '-0.03em',
                    color: 'var(--text-primary)', margin: '0 0 12px',
                  }}>
                    Welcome to <span style={{
                      color: 'var(--color-warning)',
                      textShadow: '0 0 40px rgba(246,195,103,0.3)',
                    }}>Nyx</span>
                  </h1>
                  <p style={{
                    fontSize: 20, lineHeight: 1.6, color: 'var(--text-muted)',
                    maxWidth: 560, margin: 0,
                  }}>
                    Select a mode from the command center to begin your specialized training sequence.
                    The AI model is primed and awaiting your context.
                  </p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginBottom: 32 }}>
                  {/* Technical Deep Dive — Hero Card */}
                  <div
                    className={`grid-card grid-card-hero${interviewMode === 'topic' ? ' selected' : ''}`}
                    style={{ gridColumn: 'span 2' }}
                    onClick={() => setInterviewMode('topic')}
                  >
                    <div className="glow-blob" style={{ top: -20, right: -20, width: 160, height: 160, background: 'rgba(173,198,255,0.08)' }} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 1 }}>
                      <div style={{ flex: 1 }}>
                        <span style={{ color: 'var(--secondary)', marginBottom: 14, display: 'block' }}>
                          <Icons.BookOpen size={36} />
                        </span>
                        <h3 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 8px' }}>Technical Deep Dive</h3>
                        <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5, maxWidth: 400 }}>
                          Live coding environment with real-time complexity analysis and algorithmic feedback.
                        </p>
                      </div>
                      <div style={{
                        width: 140, height: 80, flexShrink: 0,
                        background: 'rgba(8,8,7,0.6)', borderRadius: 6,
                        border: '1px solid rgba(79,69,55,0.2)',
                        padding: '8px 10px', overflow: 'hidden',
                        fontFamily: 'var(--font-mono)', fontSize: 11, lineHeight: 1.5,
                        color: 'rgba(173,198,255,0.5)',
                      }}>
                        <pre style={{ margin: 0 }}>{`function solve() {
  let p = 0;
  return p;
}`}</pre>
                      </div>
                    </div>
                  </div>

                  {/* Standard Interview */}
                  <div
                    className={`grid-card${interviewMode === 'structured' ? ' selected' : ''}`}
                    onClick={() => setInterviewMode('structured')}
                  >
                    <div className="glow-blob" style={{ top: -20, right: -20, width: 120, height: 120, background: 'rgba(246,195,103,0.06)' }} />
                    <div style={{ position: 'relative', zIndex: 1 }}>
                      <span style={{ color: 'var(--color-warning)', marginBottom: 14, display: 'block' }}>
                        <Icons.Sparkles size={28} />
                      </span>
                      <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px' }}>Standard Interview</h3>
                      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>General screening covering experience, background, and basic competencies.</p>
                    </div>
                  </div>

                  {/* Behavioral */}
                  <div
                    className={`grid-card${interviewMode === 'conversation' ? ' selected' : ''}`}
                    onClick={() => setInterviewMode('conversation')}
                  >
                    <div className="glow-blob" style={{ top: -20, right: -20, width: 120, height: 120, background: 'rgba(246,195,103,0.06)' }} />
                    <div style={{ position: 'relative', zIndex: 1 }}>
                      <span style={{ color: 'var(--color-warning)', marginBottom: 14, display: 'block' }}>
                        <Icons.Bot size={28} />
                      </span>
                      <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px' }}>Behavioral</h3>
                      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>Culture fit and soft skills evaluation based on industry standard frameworks.</p>
                    </div>
                  </div>

                  {/* Case Study */}
                  <div
                    className={`grid-card${interviewMode === 'free' ? ' selected' : ''}`}
                    onClick={() => setInterviewMode('free')}
                  >
                    <div className="glow-blob" style={{ top: -20, right: -20, width: 120, height: 120, background: 'rgba(246,195,103,0.06)' }} />
                    <div style={{ position: 'relative', zIndex: 1 }}>
                      <span style={{ color: 'var(--color-warning)', marginBottom: 14, display: 'block' }}>
                        <Icons.Settings size={28} />
                      </span>
                      <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px' }}>Case Study</h3>
                      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>System design and architecture problem-solving scenarios.</p>
                    </div>
                  </div>

                  {/* Interactive Tutor */}
                  <div
                    className={`grid-card${interviewMode === 'tutor' ? ' selected' : ''}`}
                    onClick={() => setInterviewMode('tutor')}
                  >
                    <div className="glow-blob" style={{ top: -20, right: -20, width: 120, height: 120, background: 'rgba(246,195,103,0.06)' }} />
                    <div style={{ position: 'relative', zIndex: 1 }}>
                      <span style={{ color: 'var(--color-warning)', marginBottom: 14, display: 'block' }}>
                        <Icons.Knowledge size={28} />
                      </span>
                      <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px' }}>Interactive Tutor</h3>
                      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>Guided learning mode with step-by-step concept breakdowns.</p>
                    </div>
                  </div>

                  {/* MCQ Practice — full width bottom row */}
                  <div
                    className={`grid-card${interviewMode === 'mcq' ? ' selected' : ''}`}
                    style={{ gridColumn: '1 / -1' }}
                    onClick={() => setInterviewMode('mcq')}
                  >
                    <div className="glow-blob" style={{ top: -20, right: -20, width: 160, height: 160, background: 'rgba(112,227,132,0.06)' }} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 20, position: 'relative', zIndex: 1 }}>
                      <span style={{ color: 'var(--tertiary)', flexShrink: 0 }}>
                        <Icons.Chart size={32} />
                      </span>
                      <div>
                        <h3 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 4px' }}>MCQ Practice</h3>
                        <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>Adaptive multiple-choice questions generated from your knowledge base. RAG-powered with per-subject difficulty tracking.</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Start button — bottom panel */}
                <div className="glass-panel" style={{
                  padding: '20px 32px', borderRadius: 12,
                  border: '1px solid rgba(79,69,55,0.25)',
                  background: 'rgba(12,12,11,0.5)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      onClick={startSession}
                      style={{
                        padding: '14px 32px', borderRadius: 10, border: 'none',
                        background: interviewMode === 'nyx' ? 'var(--color-warning)' : 'var(--secondary-container)',
                        color: interviewMode === 'nyx' ? '#080807' : '#fff',
                        fontSize: 16, fontWeight: 700, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                        transition: 'all 0.25s ease',
                        boxShadow: interviewMode === 'nyx'
                          ? '0 0 24px rgba(216,168,79,0.25), inset 0 1px 0 rgba(255,255,255,0.1)'
                          : '0 0 20px rgba(0,109,231,0.2)',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 0 40px rgba(216,168,79,0.35)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 0 24px rgba(216,168,79,0.25)' }}
                    >
                      <Icons.Send size={18} /> Start Session
                    </button>
                  </div>
                </div>
              </div>
            </main>
          </div>
        )}
        </main>
      </div>

      <KnowledgeBase
        show={showKnowledgePanel}
        onClose={() => setShowKnowledgePanel(false)}
        knowledgeStats={knowledgeStats}
        knowledgeSources={knowledgeSources}
        isIngesting={isIngesting}
        ingestProgress={ingestProgress}
        onIngest={triggerIngest}
        onUpload={uploadPdf}
        onDelete={deleteSource}
        fileInputRef={fileInputRef}
      />

      <Diagnostics show={showDiagnostics} onClose={() => setShowDiagnostics(false)} />
      <DevTools show={showDevTools} onClose={() => setShowDevTools(false)} />

      <audio ref={audioRef} style={{ display: 'none' }} />
    </div>
  )
}

export default App
