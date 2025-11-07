import { useState, useEffect } from 'react'
import { BookOpen } from 'lucide-react'
import LibraryView from './components/LibraryView'
import PlayerView from './components/PlayerView'
import styles from './components/App.module.css'

function App() {
  const [currentView, setCurrentView] = useState('library')
  const [currentBook, setCurrentBook] = useState(null)
  const [currentChapter, setCurrentChapter] = useState(null)

  const getLocalStorageState = () => {
    try {
      const saved = localStorage.getItem('audiobook_player_state')
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      return null
    }
  }

  const setLocalStorageState = (bookId, chapter, position) => {
    try {
      localStorage.setItem('audiobook_player_state', JSON.stringify({
        bookId,
        chapter,
        position,
        timestamp: Date.now()
      }))
    } catch (e) {
      console.warn('Failed to save to localStorage:', e)
    }
  }

  const updateURL = (bookId, chapter = null, position = null) => {
    const params = new URLSearchParams()
    params.set('book', bookId)
    if (chapter) {
      params.set('chapter', chapter.toString())
    }
    if (position && position > 0) {
      params.set('position', position.toFixed(1))
    }
    
    const newURL = `${window.location.pathname}?${params.toString()}`
    window.history.replaceState({}, '', newURL)
  }

  const loadBook = async (bookId, chapterNumber = null, position = null) => {
    try {
      const response = await fetch(`/api/books/${bookId}`)
      const book = await response.json()
      
      setCurrentBook(book)
      setCurrentView('player')
      
      // Determine which chapter and position to load
      let targetChapter = chapterNumber
      let targetPosition = position
      
      // If not provided, try to load from server progress
      if (!targetChapter) {
        const progressResponse = await fetch(`/api/progress/${bookId}`)
        const progress = await progressResponse.json()
        if (progress.current_chapter > 0) {
          targetChapter = progress.current_chapter
          targetPosition = progress.position_seconds || 0
        } else if (book.chapters && book.chapters.length > 0) {
          targetChapter = 1
          targetPosition = 0
        }
      }
      
      // Update URL and localStorage
      if (targetChapter) {
        updateURL(bookId, targetChapter, targetPosition || 0)
        setLocalStorageState(bookId, targetChapter, targetPosition || 0)
        
        // Set current chapter
        const chapter = book.chapters?.find(c => c.chapter_number === targetChapter)
        if (chapter) {
          setCurrentChapter({ ...chapter, startTime: targetPosition || 0 })
        }
      }
    } catch (error) {
      console.error('Failed to load book:', error)
      alert('Failed to load book')
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
      loadBook(bookId, chapter ? parseInt(chapter) : null, position ? parseFloat(position) : null)
    } else {
      // Check localStorage
      const savedState = getLocalStorageState()
      if (savedState && savedState.bookId) {
        loadBook(savedState.bookId, savedState.chapter || null, savedState.position || null)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showLibraryView = () => {
    setCurrentView('library')
    setCurrentBook(null)
    setCurrentChapter(null)
    window.history.replaceState({}, '', window.location.pathname)
    localStorage.removeItem('audiobook_player_state')
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>
          <BookOpen size={32} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '8px' }} />
          Audiobook Player
        </h1>
      </header>

      <main className={styles.main}>
        {currentView === 'library' && (
          <LibraryView onBookSelect={loadBook} />
        )}
        {currentView === 'player' && currentBook && (
          <PlayerView
            book={currentBook}
            currentChapter={currentChapter}
            onBack={showLibraryView}
            onChapterChange={setCurrentChapter}
            onBookChange={setCurrentBook}
          />
        )}
      </main>
    </div>
  )
}

export default App

