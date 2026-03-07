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

  // Atmosphere/grain toggle
  const [atmosphereOn, setAtmosphereOn] = useState(true)
  const toggleAtmosphere = () => {
    const html = document.documentElement
    if (atmosphereOn) {
      html.classList.remove('atmosphere-warm', 'grain')
    } else {
      html.classList.add('atmosphere-warm', 'grain')
    }
    setAtmosphereOn(!atmosphereOn)
  }
  
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
        <div className="min-h-screen flex flex-col">
          <header className="sticky top-0 z-[100] flex justify-between items-center px-8 py-5 h-[73px] box-border bg-gradient-to-b from-background-base/98 to-background-base/92 border-b border-border-subtle backdrop-blur-[20px] backdrop-saturate-[180%] shadow-[inset_0_1px_0_rgba(255,255,255,0.03),0_1px_0_rgba(255,255,255,0.02)]">
            <h1
              className={`font-heading text-2xl font-semibold italic text-text-primary tracking-[0.02em] flex items-center gap-3 transition-opacity duration-fast ease-out ${selectedBook ? 'cursor-pointer hover:opacity-80' : ''}`}
              onClick={selectedBook ? handleBack : undefined}
              title={selectedBook ? 'Back to Library' : undefined}
            >
              <span className="bg-gradient-to-br from-text-primary via-brand-primary to-brand-primary-light bg-clip-text [-webkit-text-fill-color:transparent]">Audiobook</span> Studio
            </h1>
            <div className="flex items-center gap-3">
              <button
                className={`text-xs font-mono px-3 py-1.5 rounded-full border transition-all duration-fast ease-out ${atmosphereOn ? 'border-brand-primary/30 text-brand-primary-light bg-brand-primary/10' : 'border-border-subtle text-text-tertiary bg-transparent hover:border-border-strong hover:text-text-secondary'}`}
                onClick={toggleAtmosphere}
                title={atmosphereOn ? 'Disable atmosphere effects' : 'Enable atmosphere effects'}
              >
                {atmosphereOn ? '✦ Atmos' : '○ Atmos'}
              </button>
              {queueStatus && <QueueIndicator status={queueStatus} />}
            </div>
          </header>

          {/* Book context sub-header */}
          {selectedBook && bookHeaderInfo && (
            <div className="flex items-center justify-between gap-4 px-8 py-3 bg-surface-base/98 border-b border-border-subtle sticky top-[73px] z-[99] backdrop-blur-[16px] backdrop-saturate-[180%] shadow-[0_1px_0_rgba(0,0,0,0.1)]">
              <div className="flex items-baseline gap-3 min-w-0 flex-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-heading text-base font-medium text-text-primary whitespace-nowrap overflow-hidden text-ellipsis">{bookHeaderInfo.fictionName}</span>
                  {bookHeaderInfo.sourceUrl && (
                    <a
                      href={bookHeaderInfo.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center text-text-secondary opacity-60 transition-all duration-fast ease-out shrink-0 p-1 rounded-sm hover:text-brand-primary-light hover:opacity-100 hover:bg-brand-primary/10"
                      title="View on Royal Road"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="block">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                        <polyline points="15 3 21 3 21 9"></polyline>
                        <line x1="10" y1="14" x2="21" y2="3"></line>
                      </svg>
                    </a>
                  )}
                </div>
                <span className="font-mono text-xs text-text-tertiary whitespace-nowrap shrink-0">
                  Book {bookHeaderInfo.bookNumber} · {bookHeaderInfo.chapterCount} ch
                  {bookHeaderInfo.eta && <span className="text-brand-primary-light"> · {bookHeaderInfo.eta}</span>}
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

          <main className="flex-1 px-8 pt-8 pb-6 max-w-[1200px] mx-auto w-full">
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
