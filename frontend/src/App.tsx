import { useState, useEffect } from 'react'
import { BookOpen } from 'lucide-react'
import LibraryView from './components/LibraryView'
import PlayerView from './components/PlayerView'
import ToastContainer from './components/ToastContainer'
import useAudiobookStore from './store/useAudiobookStore'
import useToastStore from './store/useToastStore'
import type { Book, BookStats } from './types'
import styles from './components/App.module.css'

interface SavedState {
  bookId: string
  chapter?: number
  position?: number
  timestamp?: number
}

function App() {
  const [currentView, setCurrentView] = useState<'library' | 'player'>('library')
  const { setCurrentBook, setCurrentChapter } = useAudiobookStore()
  const toast = useToastStore()

  const getLocalStorageState = (): SavedState | null => {
    try {
      const saved = localStorage.getItem('audiobook_player_state')
      return saved ? JSON.parse(saved) as SavedState : null
    } catch {
      return null
    }
  }

  const setLocalStorageState = (bookId: string, chapter: number | null, position: number | null): void => {
    try {
      localStorage.setItem('audiobook_player_state', JSON.stringify({
        bookId,
        chapter: chapter ?? undefined,
        position: position ?? undefined,
        timestamp: Date.now()
      }))
    } catch (e) {
      console.warn('Failed to save to localStorage:', e)
    }
  }

  const updateURL = (bookId: string, chapter: number | null, position: number | null): void => {
    const params = new URLSearchParams()
    params.set('book', bookId)
    if (chapter !== null) {
      params.set('chapter', chapter.toString())
    }
    if (position !== null && position > 0) {
      params.set('position', position.toFixed(1))
    }
    
    const newURL = `${window.location.pathname}?${params.toString()}`
    window.history.replaceState({}, '', newURL)
  }

  const loadBook = async (bookId: string, chapterNumber: number | null, position: number | null): Promise<void> => {
    try {
      const response = await fetch(`/api/books/${bookId}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch book: ${response.statusText}`)
      }
      const bookInfo = await response.json() as { book_id: string; book_title: string; book_url: string | null; author: string | null; filter_book_number: number | null; stats: BookStats; chapters: Array<{ chapter_number: number | null; title: string; number: number | null; url: string | null }> }
      
      // Transform BookInfo to Book format
      const book: Book = {
        id: bookInfo.book_id,
        title: bookInfo.book_title,
        author: bookInfo.author,
        url: bookInfo.book_url || '',
        chapter_count: bookInfo.stats.total_chapters,
        path: '', // Not in BookInfo, will be set from other sources if needed
        stats: bookInfo.stats,
      }
      
      await setCurrentBook(book)
      setCurrentView('player')
      
      // Determine which chapter and position to load
      let targetChapter: number | null = chapterNumber
      let targetPosition: number | null = position
      
      // If not provided, default to first chapter
      // Note: setCurrentBook will fetch chapters and set the first one automatically
      // but we still need to handle the case where a specific chapter is requested
      if (targetChapter === null) {
        // Wait a bit for chapters to load, then check
        // The store will set the first chapter automatically, but we can override if needed
        targetChapter = 1
        targetPosition = 0
      }
      
      // Update URL and localStorage
      if (targetChapter !== null) {
        updateURL(bookId, targetChapter, targetPosition ?? 0)
        setLocalStorageState(bookId, targetChapter, targetPosition ?? 0)
        
        // Set current chapter via store
        await setCurrentChapter(targetChapter, targetPosition ?? 0)
      }
    } catch (error) {
      console.error('Failed to load book:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to load book')
    }
  }

  // Initialize from URL or localStorage
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const bookId = urlParams.get('book')
    const chapter = urlParams.get('chapter')
    const position = urlParams.get('position')

    if (bookId) {
      // Load book from URL
      void loadBook(
        bookId,
        chapter ? parseInt(chapter, 10) : null,
        position ? parseFloat(position) : null
      )
    } else {
      // Check localStorage
      const savedState = getLocalStorageState()
      if (savedState?.bookId) {
        void loadBook(
          savedState.bookId,
          savedState.chapter ?? null,
          savedState.position ?? null
        )
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showLibraryView = (): void => {
    setCurrentView('library')
    setCurrentBook(null as unknown as Book)
    setCurrentChapter(null as unknown as number, 0)
    window.history.replaceState({}, '', window.location.pathname)
    localStorage.removeItem('audiobook_player_state')
  }

  return (
    <div className={styles.container}>
      <ToastContainer />
      <header className={styles.header}>
        <h1 className={styles.title}>
          <BookOpen size={32} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '8px' }} />
          Audiobook Player
        </h1>
      </header>

      <main className={styles.main}>
        {currentView === 'library' && (
          <LibraryView onBookSelect={(bookId, chapterNumber, position) => { return loadBook(bookId, chapterNumber ?? null, position ?? null) }} />
        )}
        {currentView === 'player' && (
          <PlayerView onBack={showLibraryView} />
        )}
      </main>
    </div>
  )
}

export default App

