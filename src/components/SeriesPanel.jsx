import { useState, useEffect } from 'react'
import { X, Download, Eye, Music, FileText } from 'lucide-react'
import styles from './SeriesPanel.module.css'

function SeriesPanel({ book, onClose, onBookSelect }) {
  const [seriesBooks, setSeriesBooks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSeriesBooks()
  }, [book])

  const loadSeriesBooks = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/books/${book.id}/series`)
      const data = await response.json()
      setSeriesBooks(data.books || [])
    } catch (error) {
      console.error('Failed to load series books:', error)
    } finally {
      setLoading(false)
    }
  }

  const downloadSeriesBook = async (bookUrl, bookNumber) => {
    try {
      const response = await fetch('/api/jobs/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_url: bookUrl,
          filter_book_number: bookNumber,
        }),
      })
      const data = await response.json()
      
      alert(`Download started! Job ID: ${data.job_id}`)
    } catch (error) {
      console.error('Failed to start download:', error)
      alert('Failed to start download')
    }
  }

  const escapeHtml = (text) => {
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
                        onClick={() => downloadSeriesBook(seriesBook.url, seriesBook.book_number)}
                      >
                        <Download size={14} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
                        Download
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: '10px' }}>
                      <button
                        className={styles.btnView}
                        onClick={() => onBookSelect(seriesBook.id)}
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

