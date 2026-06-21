import styles from './ModeSelector.module.css'
import { Icons } from './Icons'

const MODES = [
  { id: 'structured', title: 'Standard', icon: 'work' },
  { id: 'topic', title: 'Technical', icon: 'code' },
  { id: 'conversation', title: 'Behavioral', icon: 'psychology' },
  { id: 'free', title: 'Case Study', icon: 'cases' },
  { id: 'stars', title: 'STAR Method', icon: 'stars' },
  { id: 'tutor', title: 'Tutor', icon: 'school' },
  { id: 'nyx', title: 'Nyx Assistant', icon: 'smart_toy' },
]

export default function ModeSelector({ interviewMode, setInterviewMode, customScenario, setCustomScenario, startSession, isNyx }) {
  return (
    <nav className={styles.docked}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <span className={styles.botIcon}><Icons.Bot size={24} /></span>
          <h2 className={styles.title}>Setup Session</h2>
        </div>
        <p className={styles.subtitle}>{isNyx ? 'Nyx Assistant Active' : 'Specialized Engine Primed'}</p>
      </div>

      <div className={styles.content}>
        <div className={styles.section}>
          <h3 className={styles.sectionLabel}>Select Mode</h3>
          <div className={styles.grid}>
            {MODES.map((mode) => {
              const active = interviewMode === mode.id
              return (
                <button
                  key={mode.id}
                  type="button"
                  className={`${styles.modeCard} ${active ? styles.activeCard : ''}`}
                  onClick={() => setInterviewMode(mode.id)}
                >
                  <span className={styles.modeIcon}>
                    {mode.icon === 'work' && <Icons.Sparkles size={18} />}
                    {mode.icon === 'code' && <Icons.BookOpen size={18} />}
                    {mode.icon === 'psychology' && <Icons.Bot size={18} />}
                    {mode.icon === 'cases' && <Icons.Settings size={18} />}
                    {mode.icon === 'stars' && <Icons.Sparkles size={18} style={{ color: 'var(--tertiary)' }} />}
                    {mode.icon === 'school' && <Icons.Knowledge size={18} />}
                    {mode.icon === 'smart_toy' && <Icons.Moon size={18} />}
                  </span>
                  <div className={styles.modeTitle}>{mode.title}</div>
                </button>
              )
            })}
          </div>
        </div>

        <div className={styles.section} style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <label className={styles.sectionLabel} htmlFor="scenario">Topic / Scenario Context</label>
          <textarea
            id="scenario"
            className={styles.textarea}
            placeholder="e.g. 'Senior Frontend Engineer interview focusing on React performance...'"
            value={customScenario}
            onChange={(e) => setCustomScenario(e.target.value)}
            rows={6}
          />
        </div>

        <button className={styles.startBtn} onClick={startSession}>
          <Icons.Send size={20} /> Start Session
        </button>
      </div>
    </nav>
  )
}
