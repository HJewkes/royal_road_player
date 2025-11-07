import { useState, useEffect, useRef } from 'react'
import AudioPlayer from './AudioPlayer'
import ChapterList from './ChapterList'
import PlayerHeader from './PlayerHeader'
import SeriesPanel from './SeriesPanel'
import JobsPanel from './JobsPanel'
import ChunksPanel from './ChunksPanel'
import styles from './PlayerView.module.css'

function PlayerView({ book, currentChapter, onBack, onChapterChange, onBookChange }) {
  const [chapters, setChapters] = useState(book.chapters || [])
  const [activePanel, setActivePanel] = useState(null)
  const [audioRef, setAudioRef] = useState(null)

  useEffect(() => {
    // Reload chapters if book changes
    setChapters(book.chapters || [])
  }, [book])

  const handleChapterSelect = async (chapterNumber, startTime = 0) => {
    const chapter = chapters.find(c => c.chapter_number === chapterNumber)
    if (chapter) {
      onChapterChange({ ...chapter, startTime })
    }
  }

  const closePanel = () => {
    setActivePanel(null)
  }

  const showPanel = (panelName) => {
    setActivePanel(panelName)
  }

  return (
    <section className={styles.view}>
      <PlayerHeader
        book={book}
        currentChapter={currentChapter}
        onBack={onBack}
        onShowSeries={() => showPanel('series')}
        onShowJobs={() => showPanel('jobs')}
        onGenerateAudio={() => showPanel('generate')}
      />

      <div className={styles.playerContainer}>
        <ChapterList
          chapters={chapters}
          currentChapter={currentChapter}
          onChapterSelect={handleChapterSelect}
          onShowChunks={(chapterTitle) => showPanel(`chunks-${chapterTitle}`)}
        />

        <AudioPlayer
          book={book}
          chapter={currentChapter}
          onChapterChange={onChapterChange}
          onAudioRef={setAudioRef}
        />
      </div>

      {/* Panels */}
      {activePanel === 'series' && (
        <SeriesPanel
          book={book}
          onClose={closePanel}
          onBookSelect={(bookId) => {
            closePanel()
            // Load the selected book
            fetch(`/api/books/${bookId}`)
              .then(res => res.json())
              .then(bookData => {
                onBookChange(bookData)
                if (bookData.chapters && bookData.chapters.length > 0) {
                  handleChapterSelect(1, 0)
                }
              })
              .catch(err => console.error('Failed to load book:', err))
          }}
        />
      )}

      {activePanel === 'jobs' && (
        <JobsPanel
          book={book}
          onClose={closePanel}
        />
      )}

      {activePanel && activePanel.startsWith('chunks-') && (
        <ChunksPanel
          book={book}
          chapterTitle={activePanel.replace('chunks-', '')}
          onClose={closePanel}
        />
      )}

      {activePanel && (
        <div className={styles.modalOverlay} onClick={closePanel}></div>
      )}
    </section>
  )
}

export default PlayerView

