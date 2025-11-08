import { useState } from 'react'
import AudioPlayer from './AudioPlayer'
import ChapterList from './ChapterList'
import PlayerHeader from './PlayerHeader'
import SeriesPanel from './SeriesPanel'
import JobsPanel from './JobsPanel'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import type { Book, Chapter, BookStats } from '../types'
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
      const bookInfo = await response.json() as { book_id: string; book_title: string; book_url: string | null; author: string | null; filter_book_number: number | null; stats: BookStats; chapters: Array<{ chapter_number: number | null; title: string; number: number | null; url: string | null }> }
      
      // Transform BookInfo to Book format
      const bookData: Book = {
        id: bookInfo.book_id,
        title: bookInfo.book_title,
        author: bookInfo.author,
        url: bookInfo.book_url || '',
        chapter_count: bookInfo.stats.total_chapters,
        path: '', // Not in BookInfo, will be set from other sources if needed
        stats: bookInfo.stats,
      }
      
      // setCurrentBook will fetch chapters and set the first one automatically
      await useAudiobookStore.getState().setCurrentBook(bookData)
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

