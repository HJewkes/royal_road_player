import { useState } from 'react'
import { Search } from 'lucide-react'
import useToastStore from '../store/useToastStore'
import styles from './SearchPanel.module.css'

interface SearchPanelProps {
  onBookAdded: () => void
}

interface SearchResult {
  title: string
  author: string | null
  url: string
}

function SearchPanel({ onBookAdded }: SearchPanelProps) {
  const toast = useToastStore()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [showResults, setShowResults] = useState(false)

  const performSearch = async (): Promise<void> => {
    if (!query.trim()) {
      toast.warning('Please enter a search query')
      return
    }

    setLoading(true)
    setShowResults(true)

    try {
      const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`)
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`)
      }
      const data = await response.json() as { books?: SearchResult[] }

      if (!data.books || data.books.length === 0) {
        setResults([])
      } else {
        setResults(data.books)
      }
    } catch (error) {
      console.error('Search failed:', error)
      toast.error(error instanceof Error ? error.message : 'Search failed')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter') {
      void performSearch()
    }
  }

  const addBookToQueue = async (bookUrl: string): Promise<void> => {
    try {
      const response = await fetch('/api/jobs/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_url: bookUrl }),
      })
      if (!response.ok) {
        const error = await response.json() as { detail?: string }
        throw new Error(error.detail || 'Failed to add book to queue')
      }
      const data = await response.json() as { job_id?: string }

      toast.success(`Book added to scraping queue! Job ID: ${data.job_id || 'unknown'}`)

      // Clear search results
      setShowResults(false)
      setQuery('')
      setResults([])

      // Reload books
      onBookAdded()
    } catch (error) {
      console.error('Failed to add book to queue:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to add book to queue')
    }
  }

  const escapeHtml = (text: string): string => {
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
          onChange={(e) => { setQuery(e.target.value) }}
          onKeyPress={handleKeyPress}
        />
        <button className={styles.btnSearch} onClick={() => { void performSearch() }}>
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
                    onClick={() => { void addBookToQueue(book.url) }}
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

