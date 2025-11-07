import { useState } from 'react'
import AudioPlayer from './AudioPlayer'
import ChapterList from './ChapterList'
import PlayerHeader from './PlayerHeader'
import SeriesPanel from './SeriesPanel'
import JobsPanel from './JobsPanel'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import type { Book, Chapter } from '../types'
import styles from './PlayerView.module.css'

interface PlayerViewProps {
  onBack: () => void
}

type PanelType = 'series' | 'jobs' | null

function PlayerView({ onBack }: PlayerViewProps) {
  const { currentBook, currentChapter } = useAudiobookStore()
  const toast = useToastStore()
  const [activePanel, setActivePanel] = useState<PanelType>(null)

  const closePanel = (): void => {
    setActivePanel(null)
  }

  const showPanel = (panelName: PanelType): void => {
    setActivePanel(panelName)
  }

  const handleChapterChange = (chapter: Chapter | null): void => {
    // Update store when chapter changes
    if (chapter?.chapter_number !== undefined) {
      void useAudiobookStore.getState().setCurrentChapter(
        chapter.chapter_number,
        chapter.startTime ?? 0
      )
    }
  }

  const handleBookSelect = async (bookId: string): Promise<void> => {
    closePanel()
    try {
      const response = await fetch(`/api/books/${bookId}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch book: ${response.statusText}`)
      }
      const bookData = await response.json() as Book
      await useAudiobookStore.getState().setCurrentBook(bookData)
      if (bookData.chapters && bookData.chapters.length > 0) {
        await useAudiobookStore.getState().setCurrentChapter(1, 0)
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load book')
    }
  }

  return (
    <section className={styles.view}>
      <PlayerHeader
        onBack={onBack}
        onShowSeries={() => { showPanel('series') }}
        onShowJobs={() => { showPanel('jobs') }}
      />

      <div className={styles.playerContainer}>
        <ChapterList />

        <AudioPlayer
          book={currentBook}
          chapter={currentChapter}
          onChapterChange={handleChapterChange}
          onAudioRef={() => {}}
        />
      </div>

      {/* Panels */}
      {activePanel === 'series' && currentBook && (
        <SeriesPanel
          book={currentBook}
          onClose={closePanel}
          onBookSelect={handleBookSelect}
        />
      )}

      {activePanel === 'jobs' && currentBook && (
        <JobsPanel
          book={currentBook}
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

