import { ArrowLeft, BookOpen, Settings, Music } from 'lucide-react'
import styles from './PlayerHeader.module.css'

function PlayerHeader({ book, currentChapter, onBack, onShowSeries, onShowJobs, onGenerateAudio }) {
  const handleGenerateAudio = () => {
    const chapterTitle = currentChapter?.title
    const confirmMessage = chapterTitle 
      ? `Generate audio for chapter "${chapterTitle}"?`
      : `Generate audio for all chapters in "${book.title}"?`
    
    if (window.confirm(confirmMessage)) {
      onGenerateAudio()
      
      // Create the job
      fetch('/api/jobs/generate-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_id: book.id,
          chapter_title: chapterTitle || null,
        }),
      })
        .then(res => res.json())
        .then(data => {
          alert(`Audio generation started! Job ID: ${data.job_id}`)
          onShowJobs()
        })
        .catch(err => {
          console.error('Failed to start audio generation:', err)
          alert('Failed to start audio generation')
        })
    }
  }

  return (
    <div className={styles.playerHeader}>
      <button className={styles.btnBack} onClick={onBack}>
        <ArrowLeft size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
        Back to Library
      </button>
      <h2 className={styles.title}>{book.title}</h2>
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
        <button className={styles.btnAction} onClick={handleGenerateAudio}>
          <Music size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
          Generate Audio
        </button>
      </div>
    </div>
  )
}

export default PlayerHeader

