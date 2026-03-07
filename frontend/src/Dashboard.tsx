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
  chapters_on_source?: number | null
}

interface PatreonSeriesInfo {
  series_index: number
  name: string
  first_date: string
  last_date: string
  book_count: number
  chapter_count: number
  books: Array<{ book_number: number; chapter_count: number; first_date: string; last_date: string }>
}

interface FictionPreview {
  fiction_id: string
  title: string
  author: string | null
  url: string
  book_count: number
  books: Array<{ book_number: number; chapter_count: number }>
  source?: string
  series?: PatreonSeriesInfo[]
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
  const [selectedBooks, setSelectedBooks] = useState<Set<number>>(new Set())
  const [targetFictionId, setTargetFictionId] = useState<string>('')
  const [newFictionName, setNewFictionName] = useState('')
  

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
      fictionInfos.sort((a, b) => {
        const aNum = parseInt(a.fiction_id.replace(/\D/g, '')) || 0
        const bNum = parseInt(b.fiction_id.replace(/\D/g, '')) || 0
        return aNum - bNum
      })
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

  const checkSource = async (fictionId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setRefreshingFiction(fictionId)
    try {
      const res = await fetch(`/api/series/${fictionId}?refresh=true`)
      if (!res.ok) throw new Error('Failed to fetch')
      const books: SeriesBookInfo[] = await res.json()
      setSeriesBooks(prev => ({ ...prev, [fictionId]: books }))

      const newChapterBooks = books.filter(
        b => b.is_downloaded && b.chapters_on_source != null && b.chapters_on_source > b.chapter_count
      )
      if (newChapterBooks.length > 0) {
        const msg = newChapterBooks
          .map(b => `Book ${b.book_number}: ${b.chapters_on_source! - b.chapter_count} new`)
          .join('; ')
        toast.info('New chapters available', msg)
      } else {
        toast.success('Source checked', 'All books are up to date')
      }
    } catch (err) {
      toast.error('Check failed', 'Could not fetch source data')
      console.error('Source check failed:', err)
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
    if (!newSeriesUrl.includes('royalroad.com/fiction/') && !newSeriesUrl.includes('patreon.com/c/')) {
      setAddingError('Please enter a Royal Road or Patreon URL')
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
      setSelectedBooks(new Set(previewData.books.map(b => b.book_number)))
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
      if (preview.source === 'patreon') {
        // Patreon: import selected books into target fiction
        const fictionId = targetFictionId === '__new__'
          ? newFictionName.trim().toLowerCase().replace(/\s+/g, '_')
          : targetFictionId
        const fictionName = targetFictionId === '__new__'
          ? newFictionName.trim()
          : fictions.find(f => f.fiction_id === targetFictionId)?.name || preview.title

        if (!fictionId) {
          setAddingError('Please select or name a target fiction')
          return
        }

        const res = await fetch('/api/fictions/import-patreon', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            patreon_url: newSeriesUrl.trim(),
            fiction_id: fictionId,
            fiction_name: fictionName,
            book_numbers: Array.from(selectedBooks).sort(),
          }),
        })

        if (!res.ok) {
          const error = await res.json()
          throw new Error(error.detail || 'Failed to import books')
        }

        toast.success('Import started', `Downloading ${selectedBooks.size} book(s) from Patreon`)
      } else {
        // Royal Road: standard add flow
        const res = await fetch('/api/fictions/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: newSeriesUrl.trim() }),
        })

        if (!res.ok) {
          const error = await res.json()
          throw new Error(error.detail || 'Failed to add series')
        }

        toast.success('Series added', `"${preview.title}" has been added to your library`)
      }

      setShowAddSeries(false)
      setNewSeriesUrl('')
      setPreview(null)
      setSelectedBooks(new Set())
      setTargetFictionId('')
      setNewFictionName('')
      setTimeout(() => loadFictionsWithFullSeries(), 2000)
    } catch (e) {
      setAddingError(e instanceof Error ? e.message : 'Failed to add series')
      toast.error('Failed', e instanceof Error ? e.message : 'Unknown error')
    }
  }

  const handleCancelAdd = () => {
    setShowAddSeries(false)
    setNewSeriesUrl('')
    setPreview(null)
    setAddingError(null)
    setSelectedBooks(new Set())
    setTargetFictionId('')
    setNewFictionName('')
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
    <div className="animate-[fadeIn_var(--duration-slow)_var(--ease-out)]">
      {/* Add Series Header */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="font-body text-sm font-medium text-text-tertiary uppercase tracking-[0.2em]">Library</h2>
        <button
          className="bg-interactive-hover text-text-secondary border border-border py-3 px-5 text-sm font-body font-medium cursor-pointer rounded-md transition-all duration-normal ease-out tracking-[0.02em] hover:border-brand-primary-light hover:text-brand-primary-light hover:bg-brand-primary-subtle"
          onClick={() => setShowAddSeries(!showAddSeries)}
        >
          {showAddSeries ? 'Cancel' : '+ Add Series'}
        </button>
      </div>

      {/* Add Series Panel */}
      {showAddSeries && (
        <div className="bg-gradient-to-br from-surface-elevated to-surface-base border border-border rounded-xl p-8 mb-8 shadow-lg animate-[slideDown_var(--duration-normal)_var(--ease-out)]">
          <div className="flex gap-4 mb-5">
            <input
              type="text"
              placeholder="Royal Road or Patreon URL"
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
            <p className="text-status-error text-sm m-0 py-3 flex items-center gap-2">{addingError}</p>
          )}

          {preview && (
            <div className="bg-black/20 border border-border-subtle rounded-lg p-6 mt-5 animate-[fadeIn_var(--duration-fast)_var(--ease-out)]">
              <div className="mb-4">
                <h3 className="font-heading text-xl font-semibold text-text-primary m-0 mb-1">{preview.title}</h3>
                {preview.author && <span className="text-sm text-text-tertiary italic">by {preview.author}</span>}
              </div>
              <div className="flex gap-4 text-sm text-text-secondary mb-5 font-mono">
                <span>{selectedBooks.size}/{preview.book_count} book{preview.book_count !== 1 ? 's' : ''} selected</span>
                <span>•</span>
                <span>{preview.books.filter(b => selectedBooks.has(b.book_number)).reduce((sum, b) => sum + b.chapter_count, 0)} chapters</span>
              </div>
              <div className="flex flex-wrap gap-2 mb-6">
                {preview.books.map(book => {
                  const isSelected = selectedBooks.has(book.book_number)
                  return (
                    <span
                      key={book.book_number}
                      className="bg-interactive-hover border border-border-subtle rounded-full py-2 px-4 font-mono text-xs text-text-secondary font-medium"
                      onClick={() => {
                        setSelectedBooks(prev => {
                          const next = new Set(prev)
                          if (next.has(book.book_number)) {
                            next.delete(book.book_number)
                          } else {
                            next.add(book.book_number)
                          }
                          return next
                        })
                      }}
                      style={{
                        cursor: 'pointer',
                        opacity: isSelected ? 1 : 0.4,
                        textDecoration: isSelected ? 'none' : 'line-through',
                      }}
                      title={isSelected ? 'Click to exclude' : 'Click to include'}
                    >
                      Book {book.book_number}: {book.chapter_count} ch
                    </span>
                  )
                })}
              </div>
              {/* Patreon: target fiction selector */}
              {preview.source === 'patreon' && (
                <div style={{ margin: '10px 0' }}>
                  <label style={{ fontSize: '0.85em', opacity: 0.7, display: 'block', marginBottom: '4px' }}>
                    Add books to:
                  </label>
                  <select
                    value={targetFictionId}
                    onChange={(e) => setTargetFictionId(e.target.value)}
                    className="add-series-input"
                    style={{ width: '100%', padding: '6px 8px' }}
                  >
                    <option value="">— Select fiction —</option>
                    {fictions.map(f => (
                      <option key={f.fiction_id} value={f.fiction_id}>{f.name}</option>
                    ))}
                    <option value="__new__">+ New fiction...</option>
                  </select>
                  {targetFictionId === '__new__' && (
                    <input
                      type="text"
                      placeholder="Fiction name (e.g., Soccer Supremo)"
                      value={newFictionName}
                      onChange={(e) => setNewFictionName(e.target.value)}
                      className="add-series-input"
                      style={{ width: '100%', marginTop: '6px' }}
                    />
                  )}
                </div>
              )}

              <div className="flex gap-4 justify-end pt-5 border-t border-border-subtle">
                <button
                  className="btn btn-secondary"
                  onClick={handleCancelAdd}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => void handleAddSeries()}
                  disabled={selectedBooks.size === 0 || (preview.source === 'patreon' && !targetFictionId) || (targetFictionId === '__new__' && !newFictionName.trim())}
                >
                  {preview.source === 'patreon' ? `Import ${selectedBooks.size} Book(s)` : 'Add to Library'}
                </button>
              </div>
            </div>
          )}

          {!preview && !previewLoading && (
            <p className="text-text-tertiary text-sm m-0 italic">
              Paste a Royal Road or Patreon URL to preview and add a series
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
                <div className="min-w-0">
                  <h2 className="font-heading text-lg font-medium italic text-text-primary m-0 whitespace-nowrap overflow-hidden text-ellipsis">{fiction.name}</h2>
                  <div className="flex items-center gap-2 mt-[2px]">
                    <span className="font-mono text-xs text-text-tertiary">{downloadedBooks.length}/{books.length} books</span>
                    <span className="text-text-tertiary opacity-50">·</span>
                    <span className="font-mono text-xs text-text-tertiary">{totalChapters} chapters</span>
                  </div>
                </div>
              </div>

              <button
                className="btn btn-sm btn-check-rr"
                onClick={(e) => void checkSource(fiction.fiction_id, e)}
                disabled={refreshingFiction === fiction.fiction_id}
                title="Check for new chapters"
              >
                {refreshingFiction === fiction.fiction_id ? '...' : '↻ Check'}
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
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-semibold text-brand-primary-light">Book {book.book_number}</span>
                      <span className="font-mono text-xs text-text-tertiary">{book.chapter_count} chapters</span>
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
          <h3 className="font-heading text-text-primary m-0 mb-3 text-2xl font-medium">Your library awaits</h3>
          <p className="m-0 mb-8 text-base max-w-[340px] mx-auto leading-relaxed">Add a Royal Road or Patreon URL to begin building your audiobook collection</p>
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
