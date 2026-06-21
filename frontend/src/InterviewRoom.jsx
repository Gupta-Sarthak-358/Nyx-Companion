import { useRef, useEffect, useState } from 'react'
import styles from './InterviewRoom.module.css'
import { Icons } from './Icons'

export default function InterviewRoom({
  isThinking, isAiSpeaking, displayedAiResponse, videoRef, isRecording,
  userSpeech, feedback, transcript, isSessionActive, interviewMode,
  setInterviewMode, customScenario, setCustomScenario, timer,
  retryLastAnswer, leaveInterview, toggleRecording, startSession,
  interviewReport, setInterviewReport,
}) {
  const [activeTab, setActiveTab] = useState('feedback') // setup | feedback | history

  useEffect(() => {
    if (isSessionActive) setActiveTab('feedback')
  }, [isSessionActive])

  const relevance = feedback?.relevance || 0
  const depth = feedback?.depth || 0

  const getRadius = 40
  const getCircumference = 2 * Math.PI * getRadius

  return (
    <div className={styles.roomWrapper}>
      {/* SideNavBar / Live Feedback Drawer */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.sidebarHeaderIcon}>
            <Icons.Bot size={24} style={{ color: 'var(--secondary)' }} />
          </div>
          <div>
            <h2 className={styles.sidebarHeaderTitle}>Live Feedback</h2>
            <p className={styles.sidebarHeaderSub}>Nyx Assistant Active</p>
          </div>
        </div>

        <nav className={styles.tabBar}>
          <button className={`${styles.tab} ${activeTab === 'setup' ? styles.tabActive : ''}`} onClick={() => setActiveTab('setup')}>
            <Icons.Settings size={16} /> Setup
          </button>
          <button className={`${styles.tab} ${activeTab === 'feedback' ? styles.tabActive : ''}`} onClick={() => setActiveTab('feedback')}>
            <Icons.Sparkles size={16} /> Feedback
          </button>
          <button className={`${styles.tab} ${activeTab === 'history' ? styles.tabActive : ''}`} onClick={() => setActiveTab('history')}>
            <Icons.BookOpen size={16} /> History
          </button>
        </nav>

        <div className={styles.sidebarContent}>
          {activeTab === 'setup' && (
            <div className={styles.setupPanel}>
              <h3 className={styles.sectionLabel}>Context Parameters</h3>
              <textarea
                className={styles.setupTextarea}
                value={customScenario}
                onChange={(e) => setCustomScenario(e.target.value)}
                placeholder="Adjust scenario context..."
              />
              <button className={styles.switchBtn} onClick={() => setInterviewMode('nyx')}>
                <Icons.Bot size={16} /> Switch to Nyx Assistant
              </button>
            </div>
          )}

          {activeTab === 'feedback' && (
            <div className={styles.feedbackList}>
              <h3 className={styles.sectionLabel}>Performance Metrics</h3>
              <div className={styles.metricsGrid}>
                {/* Relevance */}
                <div className={styles.metricCard}>
                  <div className={styles.metricVisual}>
                    <svg className={styles.progressRing} viewBox="0 0 100 100">
                      <circle className={styles.ringBg} cx="50" cy="50" r={getRadius} />
                      <circle
                        className={styles.ringFill}
                        cx="50" cy="50" r={getRadius}
                        style={{
                          strokeDasharray: getCircumference,
                          strokeDashoffset: getCircumference - (relevance / 100) * getCircumference,
                          stroke: 'var(--tertiary)',
                        }}
                      />
                    </svg>
                    <div className={styles.ringText}>{relevance}%</div>
                  </div>
                  <span className={styles.metricLabel}>Relevance</span>
                </div>

                {/* Depth */}
                <div className={styles.metricCard}>
                  <div className={styles.metricVisual}>
                    <svg className={styles.progressRing} viewBox="0 0 100 100">
                      <circle className={styles.ringBg} cx="50" cy="50" r={getRadius} />
                      <circle
                        className={styles.ringFill}
                        cx="50" cy="50" r={getRadius}
                        style={{
                          strokeDasharray: getCircumference,
                          strokeDashoffset: getCircumference - (depth / 100) * getCircumference,
                          stroke: 'var(--primary)',
                        }}
                      />
                    </svg>
                    <div className={styles.ringText}>{depth}%</div>
                  </div>
                  <span className={styles.metricLabel}>Depth</span>
                </div>
              </div>

              <h3 className={styles.sectionLabel} style={{ marginTop: 24 }}>Real-time Suggestions</h3>
              <div className={styles.suggestions}>
                {feedback?.suggestions?.map((s, i) => (
                  <div key={i} className={styles.suggestionItem} style={{ borderLeftColor: i % 2 === 0 ? 'var(--secondary)' : 'var(--primary)' }}>
                    {s}
                  </div>
                )) || (
                  <div className={styles.emptySuggestions}>Awaiting transcription telemetry...</div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'history' && (
            <div className={styles.historyList}>
              {transcript.map((t, i) => (
                <div key={t._id || i} className={styles.historyRow} style={{ borderLeftColor: t.role === 'user' ? 'var(--tertiary)' : 'var(--primary)' }}>
                  <div className={styles.historyRole}>{t.role === 'user' ? 'Operator' : 'Nyx'}</div>
                  <div className={styles.historyText}>{t.text}</div>
                </div>
              ))}
              {transcript.length === 0 && <div className={styles.emptyHistory}>No logs recorded.</div>}
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className={styles.mainStage}>
        <div className={styles.videoGrid}>
          {/* AI Feed */}
          <div className={styles.videoPanel}>
            <div className={styles.panelGradient} />
            <div className={styles.avatarContainer}>
              <div className={`${styles.aiAvatar} ${isThinking ? styles.pulsing : ''}`}>
                <Icons.NyxCore size={64} style={{ color: 'var(--secondary)' }} />
              </div>
              <div className={styles.pulseRing} />
            </div>

            {/* Audio Visualizer */}
            <div className={styles.audioVisualizer}>
              {[...Array(21)].map((_, i) => (
                <div key={i} className={styles.audioBar} style={{ animationDelay: `${(i * 0.05).toFixed(2)}s` }} />
              ))}
            </div>

            <div className={styles.subtitleOverlay}>
              <p>{displayedAiResponse || "Analysis engine primed. Awaiting input."}</p>
            </div>
          </div>

          {/* User Feed */}
          <div className={styles.videoPanel}>
            <video ref={videoRef} autoPlay playsInline muted className={styles.webcamFeed} />
            <div className={styles.panelGradient} style={{ background: 'linear-gradient(to top, #080807, transparent)' }} />
            <div className={styles.faceGuide}>
              <span className={styles.guideLabel}>Optimal Positioning</span>
            </div>
            <div className={styles.hudElements}>
              {isRecording && <div className={styles.recBadge}><span className={styles.recDot} /> REC</div>}
            </div>
            <div className={styles.subtitleOverlay}>
              <p style={{ color: 'var(--text-muted)' }}>"{userSpeech || "Continuous speech stream..."}"</p>
            </div>
          </div>
        </div>
      </main>

      {/* Bottom Dock */}
      <nav className={styles.dock}>
        <div className={styles.dockBtnWrapper}>
          <button className={`${styles.dockBtn} ${isRecording ? styles.btnRecording : styles.btnMic}`} onClick={toggleRecording}>
            <Icons.Mic size={24} style={{ fill: isRecording ? 'currentColor' : 'none' }} />
          </button>
          <span className={styles.dockLabel}>Mic</span>
        </div>
        <div className={styles.dockDivider} />
        <div className={styles.dockBtnWrapper}>
          <button className={styles.dockBtn} onClick={retryLastAnswer}>
            <Icons.Retry size={24} style={{ color: 'var(--primary)' }} />
          </button>
          <span className={styles.dockLabel}>Retry</span>
        </div>
        <div className={styles.dockBtnWrapper}>
          <button className={styles.dockBtn} onClick={() => {}}>
            <Icons.Settings size={24} />
          </button>
          <span className={styles.dockLabel}>Reset</span>
        </div>
        <div className={styles.dockDivider} />
        <div className={styles.dockBtnWrapper}>
          <button className={styles.dockBtn} onClick={leaveInterview}>
            <Icons.Leave size={24} style={{ color: 'var(--error)' }} />
          </button>
          <span className={styles.dockLabel}>Leave</span>
        </div>
      </nav>

      {/* Report Modal */}
      {interviewReport && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalWindow}>
            <h2 className={styles.modalTitle}>Performance Assessment</h2>
            <div className={styles.modalContent}>
              <p>Overall Score: {interviewReport.overall_score}</p>
              {/* ... existing report logic mapped to new styles ... */}
            </div>
            <button className={styles.modalClose} onClick={() => setInterviewReport(null)}>Close Analysis</button>
          </div>
        </div>
      )}
    </div>
  )
}
