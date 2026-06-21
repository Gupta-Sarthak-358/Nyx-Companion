import { useEffect } from 'react'
import styles from './ModalShell.module.css'
import { Icons } from './Icons'

export default function ModalShell({ isOpen, onClose, title, children }) {
  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    if (isOpen) window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.window} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>{title}</span>
          <button type="button" className={styles.closeBtn} onClick={onClose}>
            <Icons.Close size={18} />
          </button>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  )
}
