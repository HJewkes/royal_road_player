import { useState } from 'react'
import { Search } from 'lucide-react'
import styles from './SearchPanel.module.css'

function SearchPanel({ onBookAdded }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [showResults, setShowResults] = useState(false)

  const performSearch = async () => {
    if (!query.trim()) {
      alert('Please enter a search query')
      return
    }

    setLoading(true)
    setShowResults(true)

    try {
      const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`)
      const data = await response.json()

      if (!data.books || data.books.length === 0) {
        setResults([])
      } else {
        setResults(data.books)
      }
    } catch (error) {
      console.error('Search failed:', error)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      performSearch()
    }
  }

  const addBookToQueue = async (bookUrl) => {
    try {
      const response = await fetch('/api/jobs/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_url: bookUrl }),
      })
      const data = await response.json()

      alert(`Book added to scraping queue! Job ID: ${data.job_id}`)

      // Clear search results
      setShowResults(false)
      setQuery('')
      setResults([])

      // Reload books
      if (onBookAdded) {
        onBookAdded()
      }
    } catch (error) {
      console.error('Failed to add book to queue:', error)
      alert('Failed to add book to queue')
    }
  }

  const escapeHtml = (text) => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  return (
    <div className={styles.searchPanel}>
      <div className={styles.searchControls}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search Royal Road for books..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
        />
        <button className={styles.btnSearch} onClick={performSearch}>
          <Search size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
          Search
        </button>
      </div>
      {showResults && (
        <div className={`${styles.searchResults} ${results.length === 0 && !loading ? styles.hidden : ''}`}>
          <h3>Search Results</h3>
          <div className={styles.searchResultsList}>
            {loading ? (
              <p className="loading">Searching...</p>
            ) : results.length === 0 ? (
              <p>No results found. Try a different search term.</p>
            ) : (
              results.map((book, index) => (
                <div key={index} className={styles.searchResultItem}>
                  <div>
                    <h4 dangerouslySetInnerHTML={{ __html: escapeHtml(book.title) }} />
                    <p>by {escapeHtml(book.author || 'Unknown')}</p>
                  </div>
                  <button
                    className={styles.btnAddToQueue}
                    onClick={() => addBookToQueue(book.url)}
                  >
                    Add to Queue
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SearchPanel

