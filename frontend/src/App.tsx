import { useState, useEffect, createContext, useContext } from 'react'
import Dashboard from './Dashboard'
import BookView, { BookHeaderInfo } from './BookView'
import { Toast, useToast } from './Toast'
import { AudioPlayer } from './AudioPlayer'
import { QueueIndicator } from './QueueIndicator'
import { PipelineStages } from './CircularProgress'
import { QueueStatus } from './types'

// Toast context for global access
interface ToastContextType {
  success: (title: string, message?: string) => void
  error: (title: string, message?: string) => void
  info: (title: string, message?: string) => void
  warning: (title: string, message?: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToastContext() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToastContext must be used within ToastProvider')
  }
  return context
}

// Audio player context
interface AudioContextType {
  playAudio: (src: string, title: string) => void
}

const AudioContext = createContext<AudioContextType | null>(null)

export function useAudioContext() {
  const context = useContext(AudioContext)
  if (!context) {
    throw new Error('useAudioContext must be used within AudioProvider')
  }
  return context
}

function App() {
  const [selectedBook, setSelectedBook] = useState<{
    fictionId: string
    bookNumber: number
  } | null>(null)
  const [bookHeaderInfo, setBookHeaderInfo] = useState<BookHeaderInfo | null>(null)
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null)
  
  // Toast system
  const { toasts, dismissToast, success, error, info, warning } = useToast()
  
  // Audio player state
  const [audioPlayer, setAudioPlayer] = useState<{
    src: string
    title: string
  } | null>(null)

  const playAudio = (src: string, title: string) => {
    setAudioPlayer({ src, title })
  }

  const closeAudio = () => {
    setAudioPlayer(null)
  }

  const handleBack = () => {
    setSelectedBook(null)
    setBookHeaderInfo(null)
  }

  // Read URL params on initial load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const fiction = params.get('fiction')
    const book = params.get('book')
    if (fiction && book) {
      setSelectedBook({ fictionId: fiction, bookNumber: parseInt(book) })
    }
  }, [])

  // Poll queue status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/queue/status')
        if (res.ok) {
          const status = await res.json()
          setQueueStatus(status)
        }
      } catch (e) {
        console.error('Failed to fetch queue status:', e)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [])

  return (
    <ToastContext.Provider value={{ success, error, info, warning }}>
      <AudioContext.Provider value={{ playAudio }}>
        <div className="app">
          <header className="header">
            <h1 
              className={selectedBook ? 'clickable' : ''} 
              onClick={selectedBook ? handleBack : undefined}
              title={selectedBook ? 'Back to Library' : undefined}
            >
              <span>Audiobook</span> Studio
            </h1>
            {queueStatus && <QueueIndicator status={queueStatus} />}
          </header>
          
          {/* Book context sub-header */}
          {selectedBook && bookHeaderInfo && (
            <div className="book-subheader">
              <div className="book-subheader-info">
                <div className="book-subheader-title-row">
                  <span className="book-subheader-title">{bookHeaderInfo.fictionName}</span>
                  {bookHeaderInfo.sourceUrl && (
                    <a 
                      href={bookHeaderInfo.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="book-subheader-rr-link"
                      title="View on Royal Road"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                        <polyline points="15 3 21 3 21 9"></polyline>
                        <line x1="10" y1="14" x2="21" y2="3"></line>
                      </svg>
                    </a>
                  )}
                </div>
                <span className="book-subheader-meta">
                  Book {bookHeaderInfo.bookNumber} · {bookHeaderInfo.chapterCount} ch
                  {bookHeaderInfo.eta && <span className="book-subheader-eta"> · {bookHeaderInfo.eta}</span>}
                </span>
              </div>
              <PipelineStages
                normalized={bookHeaderInfo.normalizedCount}
                chunked={bookHeaderInfo.chunkedCount}
                audioComplete={bookHeaderInfo.audioCompleteCount}
                exported={bookHeaderInfo.exportedCount}
                totalChapters={bookHeaderInfo.chapterCount}
                onNormalize={bookHeaderInfo.onNormalize}
                onChunk={bookHeaderInfo.onChunk}
                onGenerate={bookHeaderInfo.onGenerate}
                onExport={bookHeaderInfo.onExport}
                disabled={bookHeaderInfo.isProcessing}
                compact
              />
            </div>
          )}

          <main className="main">
            {selectedBook ? (
              <BookView
                fictionId={selectedBook.fictionId}
                bookNumber={selectedBook.bookNumber}
                onBack={handleBack}
                onHeaderUpdate={setBookHeaderInfo}
              />
            ) : (
              <Dashboard onSelectBook={(fictionId, bookNumber) => 
                setSelectedBook({ fictionId, bookNumber })
              } />
            )}
          </main>

          {/* Toast notifications */}
          <Toast toasts={toasts} onDismiss={dismissToast} />

          {/* Audio player modal */}
          {audioPlayer && (
            <AudioPlayer
              src={audioPlayer.src}
              title={audioPlayer.title}
              onClose={closeAudio}
            />
          )}
        </div>
      </AudioContext.Provider>
    </ToastContext.Provider>
  )
}

export default App
