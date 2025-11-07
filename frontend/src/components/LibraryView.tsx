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
            const scraping = stats?.scraping
            const tts = stats?.tts
            const chunks = stats?.chunks
            
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
                  {scraping && scraping.scraped_chapters !== undefined && scraping.total_chapters !== undefined && (
                    <div className={styles.statItem}>
                      <span className={styles.statLabel}>Scraped:</span>
                      <span className={styles.statValue}>
                        {scraping.scraped_chapters} / {scraping.total_chapters}
                      </span>
                    </div>
                  )}
                  {tts && tts.generated_chapters !== undefined && tts.total_chapters !== undefined && (
                    <div className={styles.statItem}>
                      <span className={styles.statLabel}>Audio:</span>
                      <span className={styles.statValue}>
                        {tts.generated_chapters} / {tts.total_chapters}
                      </span>
                    </div>
                  )}
                  {chunks && chunks.total_chunks !== undefined && (
                    <div className={styles.statItem}>
                      <span className={styles.statLabel}>Chunks:</span>
                      <span className={styles.statValue}>{chunks.total_chunks}</span>
                    </div>
                  )}
                </div>
                {scraping && scraping.scraped_chapters !== undefined && scraping.total_chapters !== undefined && scraping.total_chapters > 0 && (
                  <div className={styles.progressBar}>
                    <div
                      className={styles.progressBarFill}
                      style={{
                        width: `${(scraping.scraped_chapters / scraping.total_chapters) * 100}%`
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

