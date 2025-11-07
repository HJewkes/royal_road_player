import { ArrowLeft, BookOpen, Settings } from 'lucide-react'
import useAudiobookStore from '../store/useAudiobookStore'
import styles from './PlayerHeader.module.css'

interface PlayerHeaderProps {
  onBack: () => void
  onShowSeries: () => void
  onShowJobs: () => void
}

function PlayerHeader({ onBack, onShowSeries, onShowJobs }: PlayerHeaderProps) {
  const { currentBook, currentChapter } = useAudiobookStore()

  return (
    <div className={styles.playerHeader}>
      <button className={styles.btnBack} onClick={onBack}>
        <ArrowLeft size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
        Back to Library
      </button>
      {currentBook && <h2 className={styles.title}>{currentBook.title}</h2>}
      {currentChapter && <h3 className={styles.subtitle}>{currentChapter.title}</h3>}
      <div className={styles.headerActions}>
        <button className={styles.btnAction} onClick={onShowSeries}>
          <BookOpen size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
          Series
        </button>
        <button className={styles.btnAction} onClick={onShowJobs}>
          <Settings size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
          Jobs
        </button>
      </div>
    </div>
  )
}

export default PlayerHeader

