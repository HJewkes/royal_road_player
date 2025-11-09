import { useState, useEffect } from 'react'
import { Scissors, Loader, Music } from 'lucide-react'
import ChapterList from './ChapterList'
import SeriesPanel from './SeriesPanel'
import ChunkTimeline from './ChunkTimeline'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import { confirm } from '../store/useConfirmModalStore'
import type { Book, BookStats } from '../types'
import styles from './PlayerView.module.css'

interface PlayerViewProps {
  onBack: () => void
  showSeriesPanel?: boolean
  onCloseSeriesPanel?: () => void
}

type PanelType = 'series' | null

function PlayerView({ showSeriesPanel = false, onCloseSeriesPanel }: PlayerViewProps) {
  const { currentBook, currentChapter, chapters, chunkChapter, loadChunkMetadata, setCurrentChapter, queueAllPendingChunksForBook } = useAudiobookStore()
  const toast = useToastStore()
  const [activePanel, setActivePanel] = useState<PanelType>(null)
  const [chunking, setChunking] = useState(false)
  const [queueingAll, setQueueingAll] = useState(false)
  
  // Sync external series panel state
  useEffect(() => {
    if (showSeriesPanel) {
      setActivePanel('series')
    } else if (activePanel === 'series' && !showSeriesPanel) {
      setActivePanel(null)
    }
  }, [showSeriesPanel])
  
  // Notify parent when panel closes internally
  const closePanel = (): void => {
    setActivePanel(null)
    if (onCloseSeriesPanel) {
      onCloseSeriesPanel()
    }
  }


  const handleChunkChapter = async (): Promise<void> => {
    if (!currentChapter) return
    
    if (!currentChapter.scraped) {
      toast.warning('Chapter must be scraped before chunking')
      return
    }

    const confirmMessage = currentChapter.is_chunked
      ? `Re-chunk chapter "${currentChapter.title}"? This will replace existing ${currentChapter.chunk_count || 0} chunks.`
      : `Chunk chapter "${currentChapter.title}"?`

    const confirmed = await confirm(confirmMessage)
    if (!confirmed) {
      return
    }

    setChunking(true)
    try {
      const chapterNumber = currentChapter.chapter_number
      const startTime = currentChapter.startTime || 0
      const result = await chunkChapter(chapterNumber, 1.0)
      toast.success(`Chapter chunked successfully! Created ${result.chunk_count} chunks.`)
      
      // chunkChapter() calls refreshBook() which:
      // 1. Updates the chapters list with the new is_chunked status
      // 2. Updates currentChapter if it matches
      // 3. Loads chunk metadata if the chapter is chunked
      // So we don't need to call setCurrentChapter again - refreshBook handles it
      // But we should ensure the metadata is loaded by waiting for refreshBook to complete
      // and then explicitly loading if needed
      await new Promise(resolve => setTimeout(resolve, 300))
      
      // Verify the chapter was updated and load metadata if needed
      const { currentChapter: updatedChapter } = useAudiobookStore.getState()
      if (updatedChapter?.chapter_number === chapterNumber && updatedChapter.is_chunked) {
        // Double-check metadata is loaded
        const { chunkMetadata } = useAudiobookStore.getState()
        if (!chunkMetadata || chunkMetadata.length === 0) {
          await loadChunkMetadata(chapterNumber)
        }
      } else {
        // If refreshBook didn't update it, do it manually
        await setCurrentChapter(chapterNumber, startTime)
      }
    } catch (error) {
      console.error('Failed to chunk chapter:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to chunk chapter')
    } finally {
      setChunking(false)
    }
  }

  const handleQueueAllPendingChunks = async (): Promise<void> => {
    if (!currentBook) return
    
    // Count chunked chapters
    const chunkedChapters = chapters.filter((c) => c.is_chunked)
    
    if (chunkedChapters.length === 0) {
      toast.warning('No chunked chapters found. Chunk chapters first before queueing.')
      return
    }
    
    const confirmMessage = `Queue all unqueued chunks from ${chunkedChapters.length} chapter${chunkedChapters.length === 1 ? '' : 's'} in "${currentBook.title}"?`
    
    const confirmed = await confirm(confirmMessage)
    if (!confirmed) {
      return
    }
    
    setQueueingAll(true)
    try {
      const result = await queueAllPendingChunksForBook()
      if (result.totalQueued > 0) {
        toast.success(`Queued ${result.totalQueued} chunks from ${result.chaptersProcessed} chapter${result.chaptersProcessed === 1 ? '' : 's'}. Click "Start Processing" in the queue to begin.`)
      } else {
        toast.info('No pending chunks found to queue. All chunks may already be completed or queued.')
      }
    } catch (error) {
      console.error('Failed to queue chunks:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to queue chunks')
    } finally {
      setQueueingAll(false)
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
      <div className={styles.contentContainer}>
        <div className={styles.topSection}>
          <div className={styles.chapterHeader}>
            <ChapterList />
            {currentChapter && currentChapter.scraped && (
              <button
                className={styles.btnChunk}
                onClick={() => { void handleChunkChapter() }}
                disabled={chunking}
                title={currentChapter.is_chunked ? "Re-chunk chapter (will replace existing chunks)" : "Chunk chapter text into segments"}
              >
                {chunking ? (
                  <>
                    <Loader size={14} className={styles.spinner} />
                    Chunking...
                  </>
                ) : (
                  <>
                    <Scissors size={14} />
                    {currentChapter.is_chunked ? 'Re-chunk Chapter' : 'Chunk Chapter'}
                  </>
                )}
              </button>
            )}
            {currentBook && chapters.some((c) => c.is_chunked) && (
              <button
                className={styles.btnQueueAll}
                onClick={() => { void handleQueueAllPendingChunks() }}
                disabled={queueingAll}
                title="Queue all unqueued chunks from all chapters in this book"
              >
                {queueingAll ? (
                  <>
                    <Loader size={14} className={styles.spinner} />
                    Queueing...
                  </>
                ) : (
                  <>
                    <Music size={14} />
                    Queue All Pending Chunks
                  </>
                )}
              </button>
            )}
          </div>
          {currentChapter && currentChapter.is_chunked && (
            <ChunkTimeline
              currentTime={0}
              totalDuration={0}
              currentChunkIndex={0}
            />
          )}
        </div>
      </div>

      {/* Panels */}
      {activePanel === 'series' && currentBook && (
        <SeriesPanel
          book={currentBook}
          onClose={closePanel}
          onBookSelect={handleBookSelect}
        />
      )}

      {activePanel && (
        <div className={styles.modalOverlay} onClick={closePanel}></div>
      )}
    </section>
  )
}

export default PlayerView

