import { useState, useRef, useEffect } from 'react'

interface AudioPlayerProps {
  src: string
  onClose: () => void
  title?: string
}

export function AudioPlayer({ src, onClose, title }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleLoadedMetadata = () => {
      setDuration(audio.duration)
      setIsLoading(false)
    }

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
    }

    const handleEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }

    const handleError = () => {
      setError('Failed to load audio')
      setIsLoading(false)
    }

    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('ended', handleEnded)
    audio.addEventListener('error', handleError)

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('ended', handleEnded)
      audio.removeEventListener('error', handleError)
    }
  }, [])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
    } else {
      audio.play()
    }
    setIsPlaying(!isPlaying)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return

    const newTime = parseFloat(e.target.value)
    audio.currentTime = newTime
    setCurrentTime(newTime)
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="fixed inset-0 bg-surface-overlay backdrop-blur-[4px] z-[200] flex items-center justify-center animate-[fadeIn_var(--duration-fast)_var(--ease-out)]" onClick={onClose}>
      <div className="bg-gradient-to-br from-surface-elevated to-surface-base border border-border rounded-xl p-6 w-[90%] max-w-[480px] shadow-xl animate-[slideUp_var(--duration-normal)_var(--ease-spring)]" onClick={e => e.stopPropagation()}>
        <audio ref={audioRef} src={src} preload="metadata" />

        <div className="flex justify-between items-center mb-5 pb-4 border-b border-border-subtle">
          <div className="font-heading text-lg font-semibold text-text-primary">
            {title || 'Audio Preview'}
          </div>
          <button className="bg-transparent border-none text-text-tertiary text-2xl cursor-pointer p-1 leading-none transition-colors duration-fast ease-out hover:text-text-primary" onClick={onClose}>×</button>
        </div>

        {error ? (
          <div className="flex items-center justify-center gap-3 p-6 text-status-error text-sm">{error}</div>
        ) : isLoading ? (
          <div className="flex items-center justify-center gap-3 p-6 text-text-tertiary text-sm">
            <div className="spinner" />
            Loading audio...
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <button
              className={`audio-play-btn ${isPlaying ? 'playing' : ''}`}
              onClick={togglePlay}
            >
              {isPlaying ? '❚❚' : '▶'}
            </button>

            <div className="flex-1 flex items-center gap-3">
              <span className="font-mono text-xs text-text-tertiary min-w-[40px]">{formatTime(currentTime)}</span>
              <div className="audio-progress-wrapper">
                <input
                  type="range"
                  min={0}
                  max={duration}
                  value={currentTime}
                  onChange={handleSeek}
                  className="audio-progress-slider"
                />
                <div
                  className="audio-progress-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="font-mono text-xs text-text-tertiary min-w-[40px]">{formatTime(duration)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Mini inline player for chapter rows
interface MiniAudioButtonProps {
  chapterId: string
  fictionId: string
  bookNumber: number
  chapterNumber: number
  onPlay: (src: string, title: string) => void
}

export function MiniAudioButton({ 
  fictionId, 
  bookNumber, 
  chapterNumber,
  onPlay 
}: MiniAudioButtonProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    // Construct the audio preview URL
    const src = `/api/audio/preview/${fictionId}/${bookNumber}/${chapterNumber}`
    const title = `Chapter ${chapterNumber} Preview`
    onPlay(src, title)
  }

  return (
    <button 
      className="icon-btn audio-preview-btn"
      onClick={handleClick}
      title="Preview audio"
    >
      ▶
    </button>
  )
}

export default AudioPlayer

