import { useState, useRef, useEffect } from 'react'
import { Modal, ModalContent, ModalHeader, ModalTitle, ModalBody, ModalCloseButton, Spinner, Button, ButtonText, cn } from '@titan-design/react-ui'

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
    <Modal isOpen={true} onClose={onClose} size="sm" backdropBlur>
      <ModalContent className="bg-gradient-to-br from-surface-elevated to-surface-base">
        <audio ref={audioRef} src={src} preload="metadata" />

        <ModalHeader className="border-b border-border-subtle">
          <ModalTitle className="text-lg font-semibold text-text-primary">
            {title || 'Audio Preview'}
          </ModalTitle>
          <ModalCloseButton />
        </ModalHeader>

        <ModalBody>
          {error ? (
            <div className="flex items-center justify-center gap-3 p-6 text-status-error text-sm">{error}</div>
          ) : isLoading ? (
            <div className="flex items-center justify-center gap-3 p-6 text-text-tertiary text-sm">
              <Spinner size="md" color="primary" />
              Loading audio...
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <button
                className={cn(
                  "w-14 h-14 rounded-full bg-gradient-to-br from-brand-primary to-brand-primary-dark text-background-base border-none text-lg cursor-pointer flex items-center justify-center transition-all duration-fast shadow-md flex-shrink-0 hover:scale-105 hover:shadow-lg",
                  isPlaying && "from-brand-secondary to-brand-secondary-dark"
                )}
                onClick={togglePlay}
              >
                {isPlaying ? '❚❚' : '▶'}
              </button>

              <div className="flex-1 flex items-center gap-3">
                <span className="font-mono text-xs text-text-tertiary min-w-[40px]">{formatTime(currentTime)}</span>
                <div className="flex-1 h-2 bg-black/40 rounded-full relative overflow-hidden">
                  <input
                    type="range"
                    min={0}
                    max={duration}
                    value={currentTime}
                    onChange={handleSeek}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-[2]"
                  />
                  <div
                    className="absolute left-0 top-0 bottom-0 bg-gradient-to-r from-brand-primary-dark to-brand-primary rounded-full"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="font-mono text-xs text-text-tertiary min-w-[40px]">{formatTime(duration)}</span>
              </div>
            </div>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
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
  const handlePress = (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    const src = `/api/audio/preview/${fictionId}/${bookNumber}/${chapterNumber}`
    const title = `Chapter ${chapterNumber} Preview`
    onPlay(src, title)
  }

  return (
    <Button variant="outline" size="sm" className="text-brand-secondary border-brand-secondary/30 hover:bg-brand-secondary/10" onPress={handlePress}>
      <ButtonText>&#9654;</ButtonText>
    </Button>
  )
}

export default AudioPlayer

