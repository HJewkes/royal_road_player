import { useState, useEffect } from 'react'
import SearchPanel from './SearchPanel'
import type { Book } from '../types'
import styles from './LibraryView.module.css'

interface LibraryViewProps {
  onBookSelect: (bookId: string, chapterNumber?: number | null, position?: number | null) => Promise<void>
}

function LibraryView({ onBookSelect }: LibraryViewProps) {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void loadBooks()
  }, [])

  const loadBooks = async (): Promise<void> => {
    try {
      setLoading(true)
      const response = await fetch('/api/books')
      if (!response.ok) {
        throw new Error(`Failed to fetch books: ${response.statusText}`)
      }
      const data = await response.json() as { books?: Book[] }
      setBooks(data.books || [])
    } catch (error) {
      console.error('Failed to load books:', error)
    } finally {
      setLoading(false)
    }
  }

  const escapeHtml = (text: string): string => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  if (loading) {
    return <p className="loading">Loading books...</p>
  }

  return (
    <section className={styles.view}>
      <h2 className={styles.title}>Your Library</h2>
      
      <SearchPanel onBookAdded={loadBooks} />
      
      <div className={styles.booksGrid}>
        {books.length === 0 ? (
          <p>No books found. Scrape some chapters first!</p>
        ) : (
          books.map((book) => {
            const stats = book.stats
            
            return (
              <div
                key={book.id}
                className={styles.bookCard}
                onClick={() => { void onBookSelect(book.id, null, null) }}
              >
                <h3 dangerouslySetInnerHTML={{ __html: escapeHtml(book.title) }} />
                {book.author && (
                  <p className={styles.author}>by {escapeHtml(book.author)}</p>
                )}
                <div className={styles.stats}>
                  <div className={styles.statItem}>
                    <span className={styles.statLabel}>Chapters:</span>
                    <span className={styles.statValue}>{book.chapter_count}</span>
                  </div>
                  {stats && (
                    <>
                      <div className={styles.statItem}>
                        <span className={styles.statLabel}>Scraped:</span>
                        <span className={styles.statValue}>
                          {stats.chapters_with_text} / {stats.total_chapters}
                        </span>
                      </div>
                      <div className={styles.statItem}>
                        <span className={styles.statLabel}>Audio:</span>
                        <span className={styles.statValue}>
                          {stats.chapters_with_audio} / {stats.total_chapters}
                        </span>
                      </div>
                      {stats.total_chunks > 0 && (
                        <div className={styles.statItem}>
                          <span className={styles.statLabel}>Chunks:</span>
                          <span className={styles.statValue}>{stats.total_chunks}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
                {stats && stats.total_chapters > 0 && (
                  <div className={styles.progressBar}>
                    <div
                      className={styles.progressBarFill}
                      style={{
                        width: `${(stats.chapters_with_text / stats.total_chapters) * 100}%`
                      }}
                    />
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </section>
  )
}

export default LibraryView

