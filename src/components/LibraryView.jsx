import { useState, useEffect } from 'react'
import SearchPanel from './SearchPanel'
import styles from './LibraryView.module.css'

function LibraryView({ onBookSelect }) {
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadBooks()
  }, [])

  const loadBooks = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/books')
      const data = await response.json()
      setBooks(data.books || [])
    } catch (error) {
      console.error('Failed to load books:', error)
    } finally {
      setLoading(false)
    }
  }

  const escapeHtml = (text) => {
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
          books.map(book => {
            const stats = book.stats || {}
            const scraping = stats.scraping || {}
            const tts = stats.tts || {}
            const chunks = stats.chunks || {}
            
            const scrapedPct = scraping.total_chapters > 0 
              ? Math.round((scraping.scraped_chapters / scraping.total_chapters) * 100)
              : 0
            const audioPct = scraping.total_chapters > 0
              ? Math.round((tts.generated_chapters / scraping.total_chapters) * 100)
              : 0
            
            return (
              <div
                key={book.id}
                className={styles.bookCard}
                onClick={() => onBookSelect(book.id)}
              >
                <h3 dangerouslySetInnerHTML={{ __html: escapeHtml(book.title) }} />
                <p>{book.chapter_count} chapters</p>
                {book.author && <p>by {escapeHtml(book.author)}</p>}
                
                <div className={styles.bookProgress}>
                  <div className={styles.progressItem}>
                    <span className={styles.progressLabel}>Scraped:</span>
                    <span className={styles.progressValue}>
                      {scraping.scraped_chapters || 0}/{scraping.total_chapters || 0} ({scrapedPct}%)
                    </span>
                    <div className={styles.progressBarMini}>
                      <div className={styles.progressBarFill} style={{ width: `${scrapedPct}%` }}></div>
                    </div>
                  </div>
                  <div className={styles.progressItem}>
                    <span className={styles.progressLabel}>Audio:</span>
                    <span className={styles.progressValue}>
                      {tts.generated_chapters || 0}/{scraping.total_chapters || 0} ({audioPct}%)
                    </span>
                    <div className={styles.progressBarMini}>
                      <div className={styles.progressBarFill} style={{ width: `${audioPct}%` }}></div>
                    </div>
                  </div>
                  <div className={styles.progressItem}>
                    <span className={styles.progressLabel}>Chunks:</span>
                    <span className={styles.progressValue}>{chunks.total_chunks || 0} total</span>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </section>
  )
}

export default LibraryView

