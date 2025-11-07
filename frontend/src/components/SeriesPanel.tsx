import { useState, useEffect } from 'react'
import { X, Download, Eye, Music, FileText } from 'lucide-react'
import useToastStore from '../store/useToastStore'
import type { Book } from '../types'
import styles from './SeriesPanel.module.css'

interface SeriesPanelProps {
  book: Book
  onClose: () => void
  onBookSelect: (bookId: string) => Promise<void>
}

interface SeriesBook {
  id: string
  title: string
  url: string
  book_number?: number
  in_system?: boolean
  has_audio?: boolean
}

function SeriesPanel({ book, onClose, onBookSelect }: SeriesPanelProps) {
  const toast = useToastStore()
  const [seriesBooks, setSeriesBooks] = useState<SeriesBook[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void loadSeriesBooks()
  }, [book])

  const loadSeriesBooks = async (): Promise<void> => {
    try {
      setLoading(true)
      const response = await fetch(`/api/books/${book.id}/series`)
      if (!response.ok) {
        throw new Error(`Failed to fetch series: ${response.statusText}`)
      }
      const data = await response.json() as { books?: SeriesBook[] }
      setSeriesBooks(data.books || [])
    } catch (error) {
      console.error('Failed to load series books:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to load series books')
    } finally {
      setLoading(false)
    }
  }

  const downloadSeriesBook = async (bookUrl: string, bookNumber?: number): Promise<void> => {
    try {
      const response = await fetch('/api/jobs/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_url: bookUrl,
          filter_book_number: bookNumber,
        }),
      })
      if (!response.ok) {
        const error = await response.json() as { detail?: string }
        throw new Error(error.detail || 'Failed to start download')
      }
      const data = await response.json() as { job_id?: string }
      
      toast.success(`Download started! Job ID: ${data.job_id || 'unknown'}`)
    } catch (error) {
      console.error('Failed to start download:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to start download')
    }
  }

  const escapeHtml = (text: string): string => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h3>Other Books in Series</h3>
        <button className={styles.btnClose} onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      <div className={styles.seriesList}>
        {loading ? (
          <p className="loading">Loading series books...</p>
        ) : seriesBooks.length === 0 ? (
          <p>No other books found in this series.</p>
        ) : (
          seriesBooks.map((seriesBook, index) => {
            const inSystem = seriesBook.in_system !== false
            const hasAudio = seriesBook.has_audio || false
            
            return (
              <div key={index} className={styles.seriesBookItem} style={{ opacity: inSystem ? '1' : '0.8' }}>
                <div style={{ flex: 1 }}>
                  <h4 dangerouslySetInnerHTML={{ __html: escapeHtml(seriesBook.title || `Book ${seriesBook.book_number || '?'}`) }} />
                  <p style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>Book {seriesBook.book_number || '?'}</span>
                    <span>•</span>
                    {inSystem ? (
                      hasAudio ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Music size={14} />
                          Has audio
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <FileText size={14} />
                          Text only
                        </span>
                      )
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Download size={14} />
                        Not downloaded
                      </span>
                    )}
                  </p>
                  {!inSystem ? (
                    <div style={{ marginTop: '10px' }}>
                      <button
                        className={styles.btnDownload}
                        onClick={() => { void downloadSeriesBook(seriesBook.url, seriesBook.book_number) }}
                      >
                        <Download size={14} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
                        Download
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: '10px' }}>
                      <button
                        className={styles.btnView}
                        onClick={() => { void onBookSelect(seriesBook.id) }}
                      >
                        <Eye size={14} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
                        View
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default SeriesPanel

