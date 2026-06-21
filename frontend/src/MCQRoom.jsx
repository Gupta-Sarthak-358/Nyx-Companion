import { useState, useEffect } from 'react'
import styles from './MCQRoom.module.css'
import { Icons } from './Icons'

const SUBJECT_META = {
  verbal: { icon: 'BookOpen', desc: 'Reading comprehension, grammar, vocabulary, sentence correction' },
  aptitude: { icon: 'Sparkles', desc: 'Quantitative arithmetic, algebra, logical reasoning, data interpretation' },
  cs_fundamentals: { icon: 'Bot', desc: 'Operating systems, DBMS, computer networks, OOP' },
  dsa: { icon: 'Settings', desc: 'Arrays, linked lists, trees, graphs, DP, sorting & searching' },
  system_design: { icon: 'Knowledge', desc: 'Scalability, databases at scale, caching, load balancing, case studies' },
}

const LETTERS = ['A', 'B', 'C', 'D']

export default function MCQRoom({ wsSend, setMessageHandler }) {
  const [subjects, setSubjects] = useState([])
  const [topics, setTopics] = useState({})
  const [coverage, setCoverage] = useState({})
  const [selectedSubject, setSelectedSubject] = useState(null)
  const [selectedTopic, setSelectedTopic] = useState('')

  const [phase, setPhase] = useState('select') // select | playing | answered | summary
  const [question, setQuestion] = useState(null)
  const [questionId, setQuestionId] = useState(null)
  const [selectedIndex, setSelectedIndex] = useState(null)
  const [result, setResult] = useState(null)
  const [stats, setStats] = useState({ asked: 0, correct: 0 })
  const [difficulty, setDifficulty] = useState(3)
  const [thinking, setThinking] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    Promise.all([
      fetch('/api/mcq/taxonomy').then(r => r.json()),
      fetch('/api/mcq/coverage').then(r => r.json()),
    ]).then(([tax, cov]) => {
      setSubjects(tax.subjects || [])
      setTopics(tax.topics || {})
      setCoverage(cov.covered || {})
    }).catch(() => setLoadError('Failed to load MCQ taxonomy'))
  }, [])

  useEffect(() => {
    if (setMessageHandler) {
      setMessageHandler(handleWsMessage)
    }
    return () => setMessageHandler?.(null)
  }, [setMessageHandler])

  const handleSelectSubject = (subj) => {
    setSelectedSubject(subj)
    setSelectedTopic('')
  }

  const handleStart = () => {
    if (!selectedSubject) return
    setPhase('playing')
    setThinking(true)
    setLoadError(null)
    wsSend({ type: 'mcq_start', subject: selectedSubject, topic: selectedTopic || undefined })
  }

  const handleSelectOption = (idx) => {
    if (phase !== 'playing' || !questionId) return
    setSelectedIndex(idx)
    setPhase('answered')
    wsSend({ type: 'mcq_answer', question_id: questionId, selected_index: idx })
  }

  const handleNext = () => {
    setQuestion(null)
    setQuestionId(null)
    setSelectedIndex(null)
    setResult(null)
    setPhase('playing')
    setThinking(true)
    wsSend({ type: 'mcq_next' })
  }

  const handleEnd = () => {
    setPhase('summary')
    wsSend({ type: 'mcq_end' })
  }

  const handleNew = () => {
    setPhase('select')
    setSelectedSubject(null)
    setSelectedTopic('')
    setQuestion(null)
    setResult(null)
    setStats({ asked: 0, correct: 0 })
    setDifficulty(3)
    setLoadError(null)
  }

  // Exposed via the wsSend callback — the parent calls this on WS message
  const handleWsMessage = (data) => {
    switch (data.type) {
      case 'mcq_question':
        setThinking(false)
        setQuestion(data)
        setQuestionId(data.id)
        setDifficulty(data.difficulty || 3)
        break
      case 'mcq_result':
        setSelectedIndex(null)
        setResult(data)
        setStats(data.stats || { asked: 0, correct: 0 })
        setDifficulty(data.new_difficulty || difficulty)
        break
      case 'mcq_summary':
        setThinking(false)
        setStats(data.stats || { asked: 0, correct: 0 })
        setDifficulty(data.difficulty || 3)
        break
      case 'mcq_error':
        setThinking(false)
        setLoadError(data.message || 'Unknown error')
        setPhase('select')
        break
      default:
        break
    }
  }

  // Expose handleWsMessage so parent can wire it up
  // We do this via a ref trick — attach to the component instance
  // Actually, we'll use a simpler approach: the parent passes an onMcqMessage callback

  const isSubjCovered = selectedSubject ? coverage[selectedSubject] : false

  // Select phase
  if (phase === 'select') {
    return (
      <div className={styles.container}>
        <div className={styles.inner}>
          <h2 className={styles.sectionTitle}>Practice Questions</h2>
          <p className={styles.sectionDesc}>Select a subject and topic to generate adaptive MCQ questions from your knowledge base.</p>

          {loadError && <div className={styles.errorMsg}>{loadError}</div>}

          <div className={styles.subjectGrid}>
            {subjects.map(subj => {
              const meta = SUBJECT_META[subj] || {}
              const covered = coverage[subj]
              const Icon = Icons[meta.icon || 'BookOpen']
              const active = selectedSubject === subj
              return (
                <div
                  key={subj}
                  className={`${styles.subjectCard} ${active ? styles.subjectCardActive : ''}`}
                  onClick={() => handleSelectSubject(subj)}
                >
                  <span className={styles.subjectIcon}><Icon size={24} /></span>
                  <h3 className={styles.subjectName}>{subj.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</h3>
                  <p className={styles.subjectDesc}>{meta.desc || ''}</p>
                  <div className={styles.subjectChunks}>
                    {covered ? 'Material available' : 'No PDFs loaded — drop into knowledge/books/' + subj + '/ and re-ingest'}
                  </div>
                </div>
              )
            })}
          </div>

          {selectedSubject && topics[selectedSubject]?.length > 0 && (
            <div className={styles.topicSection}>
              <label className={styles.topicLabel}>Topic (optional)</label>
              <select
                className={styles.topicSelect}
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
              >
                <option value="">All topics</option>
                {topics[selectedSubject].map(t => (
                  <option key={t} value={t}>{t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>
                ))}
              </select>
            </div>
          )}

          {!isSubjCovered && selectedSubject && (
            <p className={styles.coverageHint}>No PDFs ingested for this subject. Questions may use general knowledge.</p>
          )}

          <button className={styles.startBtn} onClick={handleStart} disabled={!selectedSubject}>
            <Icons.Sparkles size={18} /> Start Practice
          </button>
        </div>
      </div>
    )
  }

  // Summary phase
  if (phase === 'summary') {
    const pct = stats.asked > 0 ? Math.round((stats.correct / stats.asked) * 100) : 0
    return (
      <div className={styles.container}>
        <div className={`${styles.inner} ${styles.summaryCard}`}>
          <h2 className={styles.summaryTitle}>Practice Complete</h2>
          <p className={styles.summarySub}>{selectedSubject?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</p>

          <div className={styles.summaryGrid}>
            <div className={styles.summaryMetric}>
              <div className={styles.summaryMetricValue}>{stats.asked}</div>
              <div className={styles.summaryMetricLabel}>Questions</div>
            </div>
            <div className={styles.summaryMetric}>
              <div className={styles.summaryMetricValue}>{stats.correct}</div>
              <div className={styles.summaryMetricLabel}>Correct</div>
            </div>
            <div className={styles.summaryMetric}>
              <div className={styles.summaryMetricValue}>{pct}%</div>
              <div className={styles.summaryMetricLabel}>Accuracy</div>
            </div>
            <div className={styles.summaryMetric}>
              <div className={styles.summaryMetricValue}>{difficulty}</div>
              <div className={styles.summaryMetricLabel}>Final Difficulty</div>
            </div>
          </div>

          <div className={styles.summaryActions}>
            <button className={styles.btnPrimary} onClick={handleNew}><Icons.Sparkles size={16} /> Start New</button>
            <button className={styles.btnSecondary} onClick={handleEnd}>Close</button>
          </div>
        </div>
      </div>
    )
  }

  // Playing / answered phase
  return (
    <div className={styles.container}>
      <div className={styles.inner}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerInfo}>
            <span className={styles.badge}>{selectedSubject?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
            {selectedTopic && <span className={styles.badge}>{selectedTopic.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>}
            <span className={styles.diffBadge}>Lv.{difficulty}</span>
          </div>
          <span className={styles.stats}>{stats.correct}/{stats.asked}</span>
        </div>

        {/* Thinking state */}
        {thinking && (
          <div className={styles.thinkingText}>Generating question...</div>
        )}

        {/* Question */}
        {question && (
          <div className={styles.questionCard}>
            <div className={styles.questionNumber}>Question {stats.asked + 1}</div>
            <p className={styles.questionText}>{question.question}</p>
          </div>
        )}

        {/* Options */}
        {question?.options && (
          <div className={styles.optionsList}>
            {question.options.map((opt, idx) => {
              let cls = styles.optionBtn
              if (phase === 'answered') {
                if (result?.correct_index === idx) cls += ` ${styles.optionCorrect}`
                else if (selectedIndex === idx && !result?.correct) cls += ` ${styles.optionWrong}`
              } else if (selectedIndex === idx) {
                cls += ` ${styles.optionSelected}`
              }
              return (
                <button
                  key={idx}
                  className={cls}
                  onClick={() => handleSelectOption(idx)}
                  disabled={phase === 'answered'}
                >
                  <span className={styles.optionLetter}>{LETTERS[idx]}</span>
                  {opt}
                </button>
              )
            })}
          </div>
        )}

        {/* Result */}
        {result && phase === 'answered' && (
          <div className={styles.resultCard}>
            <div className={styles.resultHeader}>
              <div className={`${styles.resultIcon} ${result.correct ? styles.resultCorrect : styles.resultWrong}`}>
                {result.correct ? <Icons.Check size={20} /> : '✕'}
              </div>
              <span className={styles.resultLabel}>{result.correct ? 'Correct!' : 'Incorrect'}</span>
            </div>
            <p className={styles.explanation}>{result.explanation}</p>
            <div className={styles.difficultyChange}>
              {result.streak_correct > 0 ? `Streak: ${result.streak_correct} correct` : `Difficulty adjusted to Lv.${result.new_difficulty}`}
            </div>
          </div>
        )}

        {/* Actions */}
        {phase === 'answered' && (
          <div className={styles.actions}>
            <button className={styles.btnSecondary} onClick={handleEnd}>End Practice</button>
            <button className={styles.btnPrimary} onClick={handleNext}><Icons.Send size={16} /> Next Question</button>
          </div>
        )}
      </div>
    </div>
  )
}
