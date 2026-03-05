import { useState, useEffect } from 'react'
import { useToastContext } from './App'
import { DashboardSkeleton } from './Skeleton'
import { PipelineStages } from './CircularProgress'

interface FictionInfo {
  fiction_id: string
  name: string
}

interface SeriesBookInfo {
  book_number: number
  chapter_count: number
  is_downloaded: boolean
  chapters_normalized: number
  chapters_chunked: number
  chapters_complete: number
  progress_percent: number
  status: string
  chapters_on_royal_road?: number | null
}

interface FictionPreview {
  fiction_id: string
  title: string
  author: string | null
  url: string
  book_count: number
  books: Array<{ book_number: number; chapter_count: number }>
}

interface DashboardProps {
  onSelectBook: (fictionId: string, bookNumber: number) => void
}

function Dashboard({ onSelectBook }: DashboardProps) {
  const toast = useToastContext()
  const [fictions, setFictions] = useState<FictionInfo[]>([])
  const [seriesBooks, setSeriesBooks] = useState<Record<string, SeriesBookInfo[]>>({})
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [refreshingFiction, setRefreshingFiction] = useState<string | null>(null)
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set())

  // Add series state
  const [showAddSeries, setShowAddSeries] = useState(false)
  const [newSeriesUrl, setNewSeriesUrl] = useState('')
  const [addingError, setAddingError] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<FictionPreview | null>(null)
  

  // Initial load - fetch full series info (hits Royal Road cache)
  useEffect(() => {
    loadFictionsWithFullSeries()
  }, [])

  // Polling - use fast local-only endpoint
  useEffect(() => {
    const interval = setInterval(loadLocalStatus, 5000)
    return () => clearInterval(interval)
  }, [fictions])

  const loadFictionsWithFullSeries = async () => {
    try {
      const res = await fetch('/api/fictions')
      if (!res.ok) return
      
      const fictionInfos: FictionInfo[] = await res.json()
      // Sort by fiction_id numerically (lower IDs first = older series first)
      fictionInfos.sort((a, b) => parseInt(a.fiction_id) - parseInt(b.fiction_id))
      setFictions(fictionInfos)

      // Load series info in parallel (uses cached Royal Road data)
      const seriesPromises = fictionInfos.map(async (fiction) => {
        const seriesRes = await fetch(`/api/series/${fiction.fiction_id}`)
        if (seriesRes.ok) {
          const books = await seriesRes.json()
          return { fictionId: fiction.fiction_id, books }
        }
        return null
      })

      const results = await Promise.all(seriesPromises)
      const newSeriesBooks: Record<string, SeriesBookInfo[]> = {}
      for (const result of results) {
        if (result) {
          newSeriesBooks[result.fictionId] = result.books
        }
      }
      setSeriesBooks(newSeriesBooks)
    } catch (e) {
      console.error('Failed to load fictions:', e)
    } finally {
      setLoading(false)
    }
  }

  const loadLocalStatus = async () => {
    if (fictions.length === 0) return
    
    try {
      // Fast local-only endpoint - doesn't hit Royal Road
      const promises = fictions.map(async (fiction) => {
        const res = await fetch(`/api/series-local/${fiction.fiction_id}`)
        if (res.ok) {
          const books = await res.json()
          return { fictionId: fiction.fiction_id, books }
        }
        return null
      })

      const results = await Promise.all(promises)
      
      setSeriesBooks(prev => {
        const updated = { ...prev }
        for (const result of results) {
          if (result) {
            // Merge with existing data - keep undownloaded books from full series
            const existing = updated[result.fictionId] || []
            const localBooks = result.books as SeriesBookInfo[]
            const localBookNums = new Set(localBooks.map(b => b.book_number))
            
            // Keep undownloaded books from cache, update downloaded ones
            const merged = [
              ...localBooks,
              ...existing.filter(b => !b.is_downloaded && !localBookNums.has(b.book_number))
            ].sort((a, b) => a.book_number - b.book_number)
            
            updated[result.fictionId] = merged
          }
        }
        return updated
      })
    } catch (e) {
      console.error('Failed to load local status:', e)
    }
  }

  const checkRoyalRoad = async (fictionId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setRefreshingFiction(fictionId)
    try {
      const res = await fetch(`/api/series/${fictionId}?refresh=true`)
      if (!res.ok) throw new Error('Failed to fetch')
      const books: SeriesBookInfo[] = await res.json()
      setSeriesBooks(prev => ({ ...prev, [fictionId]: books }))

      const newChapterBooks = books.filter(
        b => b.is_downloaded && b.chapters_on_royal_road != null && b.chapters_on_royal_road > b.chapter_count
      )
      if (newChapterBooks.length > 0) {
        const msg = newChapterBooks
          .map(b => `Book ${b.book_number}: ${b.chapters_on_royal_road! - b.chapter_count} new`)
          .join('; ')
        toast.info('New chapters available', msg)
      } else {
        toast.success('Royal Road checked', 'All books are up to date')
      }
    } catch (err) {
      toast.error('Check failed', 'Could not fetch Royal Road data')
      console.error('Royal Road check failed:', err)
    } finally {
      setRefreshingFiction(null)
    }
  }

  const downloadBook = async (fictionId: string, bookNumber: number) => {
    const key = `${fictionId}_${bookNumber}`
    setDownloading(key)
    try {
      const res = await fetch('/api/scraper/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber }),
      })
      if (!res.ok) {
        const errorText = await res.text()
        toast.error('Download failed', errorText)
        console.error('Download failed:', errorText)
      } else {
        toast.success('Download started', `Book ${bookNumber} is being downloaded`)
      }
      // Refresh after a delay to allow download to start
      setTimeout(() => loadLocalStatus(), 2000)
    } catch (e) {
      toast.error('Download failed', 'Network error occurred')
      console.error('Failed to download book:', e)
    } finally {
      setDownloading(null)
    }
  }


  const handlePreviewSeries = async () => {
    if (!newSeriesUrl.trim()) return

    // Basic URL validation
    if (!newSeriesUrl.includes('royalroad.com/fiction/')) {
      setAddingError('Please enter a valid Royal Road fiction URL')
      return
    }

    setAddingError(null)
    setPreviewLoading(true)
    setPreview(null)

    try {
      const res = await fetch('/api/fictions/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newSeriesUrl.trim() }),
      })

      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.detail || 'Failed to fetch series')
      }

      const previewData: FictionPreview = await res.json()
      setPreview(previewData)
      toast.info('Preview loaded', `Found "${previewData.title}"`)
    } catch (e) {
      setAddingError(e instanceof Error ? e.message : 'Failed to preview series')
      toast.error('Preview failed', e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleAddSeries = async () => {
    if (!preview) return

    try {
      const res = await fetch('/api/fictions/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newSeriesUrl.trim() }),
      })

      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.detail || 'Failed to add series')
      }

      // Success - reset and refresh
      toast.success('Series added', `"${preview.title}" has been added to your library`)
      setShowAddSeries(false)
      setNewSeriesUrl('')
      setPreview(null)
      loadFictionsWithFullSeries()  // Refresh to get full series info
    } catch (e) {
      setAddingError(e instanceof Error ? e.message : 'Failed to add series')
      toast.error('Failed to add series', e instanceof Error ? e.message : 'Unknown error')
    }
  }

  const handleCancelAdd = () => {
    setShowAddSeries(false)
    setNewSeriesUrl('')
    setPreview(null)
    setAddingError(null)
  }

  const toggleSection = (fictionId: string) => {
    setCollapsedSections(prev => {
      const next = new Set(prev)
      if (next.has(fictionId)) {
        next.delete(fictionId)
      } else {
        next.add(fictionId)
      }
      return next
    })
  }

  if (loading) {
    return <DashboardSkeleton />
  }

  return (
    <div className="dashboard">
      {/* Add Series Header */}
      <div className="dashboard-header">
        <h2 className="dashboard-title">Library</h2>
        <button
          className="btn btn-add-series"
          onClick={() => setShowAddSeries(!showAddSeries)}
        >
          {showAddSeries ? 'Cancel' : '+ Add Series'}
        </button>
      </div>

      {/* Add Series Panel */}
      {showAddSeries && (
        <div className="add-series-panel">
          <div className="add-series-input-group">
            <input
              type="text"
              placeholder="https://www.royalroad.com/fiction/..."
              value={newSeriesUrl}
              onChange={(e) => setNewSeriesUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handlePreviewSeries() }}
              className="add-series-input"
              autoFocus
            />
            <button
              className="btn btn-preview"
              onClick={() => void handlePreviewSeries()}
              disabled={!newSeriesUrl.trim() || previewLoading}
            >
              {previewLoading ? '...' : '→ Preview'}
            </button>
          </div>

          {addingError && (
            <p className="add-series-error">{addingError}</p>
          )}

          {preview && (
            <div className="series-preview">
              <div className="preview-header">
                <h3>{preview.title}</h3>
                {preview.author && <span className="preview-author">by {preview.author}</span>}
              </div>
              <div className="preview-stats">
                <span>{preview.book_count} book{preview.book_count !== 1 ? 's' : ''}</span>
                <span>•</span>
                <span>{preview.books.reduce((sum, b) => sum + b.chapter_count, 0)} total chapters</span>
              </div>
              <div className="preview-books">
                {preview.books.map(book => (
                  <span key={book.book_number} className="preview-book-badge">
                    Book {book.book_number}: {book.chapter_count} ch
                  </span>
                ))}
              </div>
              <div className="preview-actions">
                <button
                  className="btn btn-secondary"
                  onClick={handleCancelAdd}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => void handleAddSeries()}
                >
                  Add to Library
                </button>
              </div>
            </div>
          )}

          {!preview && !previewLoading && (
            <p className="add-series-hint">
              Paste a Royal Road fiction URL to preview and add a series
            </p>
          )}
        </div>
      )}

      {fictions.map((fiction, fictionIndex) => {
        const books = seriesBooks[fiction.fiction_id] || []
        const downloadedBooks = books.filter(b => b.is_downloaded)
        const totalNormalized = downloadedBooks.reduce((sum, b) => sum + b.chapters_normalized, 0)
        const totalChunked = downloadedBooks.reduce((sum, b) => sum + b.chapters_chunked, 0)
        const totalComplete = downloadedBooks.reduce((sum, b) => sum + b.chapters_complete, 0)
        const totalExported = downloadedBooks.filter(b => b.status === 'exported').reduce((sum, b) => sum + b.chapter_count, 0)
        const totalChapters = downloadedBooks.reduce((sum, b) => sum + b.chapter_count, 0)
        const isCollapsed = collapsedSections.has(fiction.fiction_id)

        return (
          <div 
            key={fiction.fiction_id} 
            className={`series-card ${isCollapsed ? 'collapsed' : ''}`}
            style={{ animationDelay: `${fictionIndex * 100}ms` }}
          >
            {/* Series Header */}
            <div 
              className="series-header"
              onClick={() => toggleSection(fiction.fiction_id)}
            >
              <div className="series-header-left">
                <span className="collapse-icon">▼</span>
                <div className="series-info">
                  <h2 className="series-title">{fiction.name}</h2>
                  <div className="series-meta">
                    <span className="series-stat">{downloadedBooks.length}/{books.length} books</span>
                    <span className="series-stat-divider">·</span>
                    <span className="series-stat">{totalChapters} chapters</span>
                  </div>
                </div>
              </div>

              <button
                className="btn btn-sm btn-check-rr"
                onClick={(e) => void checkRoyalRoad(fiction.fiction_id, e)}
                disabled={refreshingFiction === fiction.fiction_id}
                title="Check Royal Road for new chapters"
              >
                {refreshingFiction === fiction.fiction_id ? '...' : '↻ Check RR'}
              </button>
              
              {totalChapters > 0 && (
                <PipelineStages
                  normalized={totalNormalized}
                  chunked={totalChunked}
                  audioComplete={totalComplete}
                  exported={totalExported}
                  totalChapters={totalChapters}
                  compact
                />
              )}
            </div>

            {/* Book List */}
            <div className="series-books">
              {books.map((book, bookIndex) => {
                const downloadKey = `${fiction.fiction_id}_${book.book_number}`
                const isDownloading = downloading === downloadKey

                return (
                  <div 
                    key={downloadKey} 
                    className={`book-row-unified ${!book.is_downloaded ? 'not-downloaded' : ''}`}
                    onClick={() => book.is_downloaded && onSelectBook(fiction.fiction_id, book.book_number)}
                    style={{ animationDelay: `${(fictionIndex * 3 + bookIndex) * 50}ms` }}
                  >
                    <div className="book-row-info">
                      <span className="book-number-badge">Book {book.book_number}</span>
                      <span className="book-chapter-count">{book.chapter_count} chapters</span>
                    </div>

                    <PipelineStages
                      normalized={book.is_downloaded ? book.chapters_normalized : 0}
                      chunked={book.is_downloaded ? book.chapters_chunked : 0}
                      audioComplete={book.is_downloaded ? book.chapters_complete : 0}
                      exported={book.is_downloaded && book.status === 'exported' ? book.chapter_count : 0}
                      totalChapters={book.chapter_count}
                      compact
                      needsDownload={!book.is_downloaded}
                      onDownload={() => downloadBook(fiction.fiction_id, book.book_number)}
                      isDownloading={isDownloading}
                    />
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}

      {fictions.length === 0 && !showAddSeries && (
        <div className="empty-state">
          <div className="empty-icon-stack">
            <div className="empty-book" />
            <div className="empty-book" />
            <div className="empty-book" />
          </div>
          <h3>Your library awaits</h3>
          <p>Add a Royal Road fiction URL to begin building your audiobook collection</p>
          <button
            className="btn btn-primary btn-lg"
            onClick={() => setShowAddSeries(true)}
          >
            + Add Your First Series
          </button>
        </div>
      )}
    </div>
  )
}

export default Dashboard
