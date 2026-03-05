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
    <div className="audio-player-overlay" onClick={onClose}>
      <div className="audio-player" onClick={e => e.stopPropagation()}>
        <audio ref={audioRef} src={src} preload="metadata" />
        
        <div className="audio-player-header">
          <div className="audio-player-title">
            {title || 'Audio Preview'}
          </div>
          <button className="audio-player-close" onClick={onClose}>×</button>
        </div>

        {error ? (
          <div className="audio-player-error">{error}</div>
        ) : isLoading ? (
          <div className="audio-player-loading">
            <div className="spinner" />
            Loading audio...
          </div>
        ) : (
          <div className="audio-player-controls">
            <button 
              className={`audio-play-btn ${isPlaying ? 'playing' : ''}`}
              onClick={togglePlay}
            >
              {isPlaying ? '❚❚' : '▶'}
            </button>
            
            <div className="audio-progress-container">
              <span className="audio-time">{formatTime(currentTime)}</span>
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
              <span className="audio-time">{formatTime(duration)}</span>
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

