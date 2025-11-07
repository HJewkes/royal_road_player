import { useState, useEffect, useRef } from 'react'
import { SkipBack, Play, Pause, SkipForward } from 'lucide-react'
import ChunkTimeline from './ChunkTimeline'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import type { Book, Chapter } from '../types'
import styles from './AudioPlayer.module.css'

interface AudioPlayerProps {
  book: Book | null
  chapter: Chapter | null
  onChapterChange: (chapter: Chapter | null) => void
  onAudioRef: (audio: HTMLAudioElement | null) => void
}

interface ChunkTimeInfo {
  chunkIndex: number
  chunkTime: number
}

function AudioPlayer({ book, chapter, onChapterChange, onAudioRef }: AudioPlayerProps) {
  const { loadChunkMetadata } = useAudiobookStore()
  const toast = useToastStore()
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playbackRate, setPlaybackRate] = useState(1.0)
  const [volume, setVolume] = useState(1.0)
  
  // Chunked audio state
  const [chunkAudios, setChunkAudios] = useState<string[]>([])
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0)
  const [, setChunkDurations] = useState<number[]>([])
  const [chunkStartTimes, setChunkStartTimes] = useState<number[]>([0])
  const [totalDuration, setTotalDuration] = useState(0)
  
  // Use refs to track current values for event handlers
  const chunkAudiosRef = useRef<string[]>([])
  const currentChunkIndexRef = useRef<number>(0)
  
  // Keep refs in sync with state
  useEffect(() => {
    chunkAudiosRef.current = chunkAudios
  }, [chunkAudios])
  
  useEffect(() => {
    currentChunkIndexRef.current = currentChunkIndex
  }, [currentChunkIndex])

  useEffect(() => {
    if (onAudioRef && audioRef.current) {
      onAudioRef(audioRef.current)
    }
  }, [onAudioRef])

  useEffect(() => {
    if (!chapter) return

    const wasPlaying = isPlaying
    void loadChapter(chapter, wasPlaying)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapter])

  const loadChapter = async (chapterData: Chapter, shouldPlay = false): Promise<void> => {
    if (!book || !chapterData || !audioRef.current) return

    try {
      const response = await fetch(`/api/books/${book.id}/chapters/${chapterData.chapter_number}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch chapter: ${response.statusText}`)
      }
      const chapterDetails = await response.json() as { audio_urls?: string[]; is_chunked?: boolean }

      if (chapterDetails.audio_urls && chapterDetails.audio_urls.length > 0) {
        if (chapterDetails.is_chunked) {
          // Load chunk metadata for timeline
          await loadChunkMetadata(chapterData.title)
          // Load chunked audio
          await loadChunkedAudio(chapterDetails.audio_urls, chapterData.startTime || 0, shouldPlay)
        } else {
          // Single audio file
          setChunkAudios([])
          const firstUrl = chapterDetails.audio_urls[0]
          if (firstUrl) {
            audioRef.current.src = firstUrl
            audioRef.current.load()
          }
          
          const handleSingleFileEnded = (): void => {
            setIsPlaying(false)
            handleChapterEnd()
          }
          
          audioRef.current.addEventListener('loadedmetadata', () => {
            if (chapterData.startTime && chapterData.startTime > 0) {
              audioRef.current!.currentTime = chapterData.startTime
            }
            if (shouldPlay) {
              // Ensure volume is set before playing to prevent browser fade-in
              audioRef.current!.volume = volume
              const playPromise = audioRef.current!.play()
              if (playPromise !== undefined) {
                playPromise.catch(() => {
                  // Playback failed, but that's okay
                })
              }
              setIsPlaying(true)
            }
            // Set up ended listener for single file
            audioRef.current!.addEventListener('ended', handleSingleFileEnded, { once: true })
          }, { once: true })
        }
      } else {
        console.log(`No audio available for chapter ${chapterData.chapter_number}`)
        audioRef.current.pause()
        setIsPlaying(false)
      }
    } catch (error) {
      console.error('Failed to load chapter:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to load chapter')
    }
  }

  const loadChunkedAudio = async (audioUrls: string[], startTime = 0, shouldPlay = false): Promise<void> => {
    if (!audioRef.current) return
    
    setChunkAudios(audioUrls)
    setCurrentChunkIndex(0)
    
    // Preload all chunks to get durations
    await preloadChunkDurations(audioUrls)
    
    // Calculate which chunk to start with
    const { chunkIndex, chunkTime } = findChunkForTime(startTime)
    setCurrentChunkIndex(chunkIndex)
    
    // Load the appropriate chunk
    const chunkUrl = audioUrls[chunkIndex]
    if (chunkUrl) {
      audioRef.current.src = chunkUrl
      audioRef.current.load()
    }
    
    audioRef.current.addEventListener('loadedmetadata', () => {
      if (startTime > 0) {
        audioRef.current!.currentTime = chunkTime
      }
      if (shouldPlay) {
        // Ensure volume is set before playing to prevent browser fade-in
        audioRef.current!.volume = volume
        const playPromise = audioRef.current!.play()
        if (playPromise !== undefined) {
          playPromise.catch(() => {
            // Playback failed, but that's okay
          })
        }
        setIsPlaying(true)
      }
      // Set up chunk transition listener after metadata is loaded
      setupChunkTransitionListener()
    }, { once: true })
  }

  const preloadChunkDurations = async (audioUrls: string[]): Promise<void> => {
    const durations: number[] = []
    const promises = audioUrls.map((url, index) => {
      return new Promise<number>((resolve) => {
        const tempAudio = new Audio(url)
        tempAudio.addEventListener('loadedmetadata', () => {
          durations[index] = tempAudio.duration
          resolve(tempAudio.duration)
        })
        tempAudio.addEventListener('error', () => {
          durations[index] = 0
          resolve(0)
        })
      })
    })
    
    await Promise.all(promises)
    setChunkDurations(durations)
    
    // Calculate cumulative start times
    let cumulative = 0
    const startTimes = [0]
    for (const duration of durations) {
      cumulative += duration
      startTimes.push(cumulative)
    }
    setChunkStartTimes(startTimes)
    setTotalDuration(cumulative)
  }

  const findChunkForTime = (totalTime: number): ChunkTimeInfo => {
    for (let i = 0; i < chunkStartTimes.length - 1; i++) {
      const chunkStart = chunkStartTimes[i] || 0
      const chunkEnd = chunkStartTimes[i + 1] || 0
      
      if (totalTime >= chunkStart && totalTime < chunkEnd) {
        return {
          chunkIndex: i,
          chunkTime: totalTime - chunkStart
        }
      }
    }
    
    const lastIndex = chunkStartTimes.length - 2
    return {
      chunkIndex: lastIndex >= 0 ? lastIndex : 0,
      chunkTime: 0
    }
  }

  const getTotalTime = (): number => {
    if (chunkStartTimes.length === 0 || !audioRef.current) {
      return audioRef.current?.currentTime || 0
    }
    const chunkStart = chunkStartTimes[currentChunkIndex] || 0
    return chunkStart + (audioRef.current.currentTime || 0)
  }

  const setupChunkTransitionListener = (): void => {
    if (!audioRef.current) return
    
    const handleEnded = (): void => {
      // Use refs to get current values (always up-to-date)
      const currentIndex = currentChunkIndexRef.current
      const currentAudios = chunkAudiosRef.current
      
      if (currentIndex < currentAudios.length - 1 && audioRef.current) {
        const nextIndex = currentIndex + 1
        const nextUrl = currentAudios[nextIndex]
        if (nextUrl) {
          setCurrentChunkIndex(nextIndex)
          audioRef.current.src = nextUrl
          audioRef.current.load()
        }
        
        audioRef.current.addEventListener('loadedmetadata', () => {
          if (!audioRef.current) return
          // Ensure volume is set to full before playing to prevent browser fade-in
          audioRef.current.volume = volume
          // Use play() with a promise to ensure immediate playback without fade
          const playPromise = audioRef.current.play()
          if (playPromise !== undefined) {
            playPromise.catch(() => {
              // Playback failed, but that's okay
            })
          }
          setIsPlaying(true)
          setupChunkTransitionListener()
        }, { once: true })
      } else {
        // Chapter finished
        handleChapterEnd()
      }
    }
    
    // Remove any existing listeners
    if (audioRef.current) {
      audioRef.current.removeEventListener('ended', handleEnded)
      audioRef.current.addEventListener('ended', handleEnded, { once: true })
    }
  }

  const handleChapterEnd = (): void => {
    if (!chapter || !book) return
    
    const nextNum = chapter.chapter_number + 1
    const nextChapter = book.chapters?.find((c) => c.chapter_number === nextNum)
    
    if (nextChapter && nextChapter.has_audio) {
      onChapterChange({ ...nextChapter, startTime: 0 })
    } else {
      console.log('Reached end of available audio')
      if (audioRef.current) {
        audioRef.current.pause()
      }
      setIsPlaying(false)
    }
  }

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleLoadedMetadata = (): void => {
      setDuration(audio.duration)
      if (chunkAudios.length > 0 && totalDuration > 0) {
        setDuration(totalDuration)
      }
    }

    const handleTimeUpdate = (): void => {
      setCurrentTime(audio.currentTime)
      saveProgress()
    }

    // Don't add 'ended' listener here - it's handled by setupChunkTransitionListener
    // for chunked audio, or will be handled naturally for single-file audio
    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('timeupdate', handleTimeUpdate)

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
    }
  }, [chunkAudios, totalDuration])

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate
    }
  }, [playbackRate])

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume
    }
  }, [volume])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.code === 'Space' && (e.target as HTMLElement).tagName !== 'INPUT') {
        e.preventDefault()
        togglePlayPause()
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault()
        seekBackward(10)
      } else if (e.code === 'ArrowRight') {
        e.preventDefault()
        seekForward(10)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => { document.removeEventListener('keydown', handleKeyDown) }
  }, [])

  const togglePlayPause = (): void => {
    if (!audioRef.current) return
    
    if (audioRef.current.paused) {
      // Ensure volume is set before playing to prevent browser fade-in
      audioRef.current.volume = volume
      const playPromise = audioRef.current.play()
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          // Playback failed, but that's okay
        })
      }
      setIsPlaying(true)
    } else {
      audioRef.current.pause()
      setIsPlaying(false)
    }
  }

  const playPreviousChapter = (): void => {
    if (!chapter || !book) return
    const prevNum = chapter.chapter_number - 1
    if (prevNum >= 1) {
      const prevChapter = book.chapters?.find((c) => c.chapter_number === prevNum)
      if (prevChapter) {
        onChapterChange({ ...prevChapter, startTime: 0 })
      }
    }
  }

  const playNextChapter = (): void => {
    if (!chapter || !book) return
    const nextNum = chapter.chapter_number + 1
    const nextChapter = book.chapters?.find((c) => c.chapter_number === nextNum)
    if (nextChapter && nextChapter.has_audio) {
      onChapterChange({ ...nextChapter, startTime: 0 })
    } else {
      console.log(`Chapter ${nextNum} doesn't have audio yet`)
      if (audioRef.current) {
        audioRef.current.pause()
      }
      setIsPlaying(false)
    }
  }

  const seekToTotalTime = (totalTime: number, preservePlayState = true): void => {
    if (!audioRef.current) return
    
    const { chunkIndex, chunkTime } = findChunkForTime(totalTime)
    const wasPlaying = preservePlayState && isPlaying
    
    if (chunkIndex !== currentChunkIndex) {
      const chunkUrl = chunkAudios[chunkIndex]
      if (chunkUrl) {
        setCurrentChunkIndex(chunkIndex)
        audioRef.current.src = chunkUrl
        audioRef.current.load()
      }
      
      audioRef.current.addEventListener('loadedmetadata', () => {
        if (!audioRef.current) return
        audioRef.current.currentTime = chunkTime
        setupChunkTransitionListener()
        if (wasPlaying) {
          // Ensure volume is set before playing to prevent browser fade-in
          audioRef.current.volume = volume
          const playPromise = audioRef.current.play()
          if (playPromise !== undefined) {
            playPromise.catch(() => {
              // Playback failed, but that's okay
            })
          }
          setIsPlaying(true)
        }
      }, { once: true })
    } else {
      audioRef.current.currentTime = chunkTime
    }
  }

  const seekForward = (seconds: number): void => {
    if (!audioRef.current) return
    
    if (chunkAudios.length > 0 && totalDuration > 0) {
      const currentTime = getTotalTime()
      const newTime = Math.min(totalDuration, currentTime + seconds)
      seekToTotalTime(newTime)
    } else if (audioRef.current.duration) {
      audioRef.current.currentTime = Math.min(audioRef.current.duration, audioRef.current.currentTime + seconds)
    }
  }

  const seekBackward = (seconds: number): void => {
    if (!audioRef.current) return
    
    if (chunkAudios.length > 0 && totalDuration > 0) {
      const currentTime = getTotalTime()
      const newTime = Math.max(0, currentTime - seconds)
      seekToTotalTime(newTime)
    } else if (audioRef.current.duration) {
      audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - seconds)
    }
  }

  const handleProgressChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    if (!audioRef.current) return
    
    const percent = parseFloat(e.target.value)
    
    if (chunkAudios.length > 0 && totalDuration > 0) {
      const totalTime = (percent / 100) * totalDuration
      seekToTotalTime(totalTime)
    } else if (audioRef.current.duration) {
      const time = (percent / 100) * audioRef.current.duration
      audioRef.current.currentTime = time
    }
  }

  const saveProgress = (): void => {
    if (!book || !chapter || !audioRef.current) return

    // Throttle saves (every 5 seconds)
    const lastSave = (window as unknown as { lastSave?: number }).lastSave
    if (lastSave && Date.now() - lastSave < 5000) return

    try {
      const positionSeconds = chunkAudios.length > 0 
        ? getTotalTime() 
        : audioRef.current.currentTime
      
      const completed = chunkAudios.length > 0
        ? (currentChunkIndex >= chunkAudios.length - 1 && audioRef.current.ended)
        : audioRef.current.ended
      
      void fetch('/api/progress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_id: book.id,
          chapter_id: chapter.chapter_number,
          position_seconds: positionSeconds,
          completed: completed,
        }),
      })
      
      // Update URL and localStorage
      const params = new URLSearchParams()
      params.set('book', book.id)
      params.set('chapter', chapter.chapter_number.toString())
      if (positionSeconds > 0) {
        params.set('position', positionSeconds.toFixed(1))
      }
      window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
      
      localStorage.setItem('audiobook_player_state', JSON.stringify({
        bookId: book.id,
        chapter: chapter.chapter_number,
        position: positionSeconds,
        timestamp: Date.now()
      }))
      
      ;(window as unknown as { lastSave: number }).lastSave = Date.now()
    } catch (error) {
      console.error('Failed to save progress:', error)
    }
  }

  const formatTime = (seconds: number): string => {
    if (!seconds || isNaN(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const displayTime = chunkAudios.length > 0 && totalDuration > 0
    ? getTotalTime()
    : currentTime

  const displayDuration = chunkAudios.length > 0 && totalDuration > 0
    ? totalDuration
    : duration

  const progressPercent = displayDuration > 0
    ? (displayTime / displayDuration) * 100
    : 0

  return (
    <div className={styles.playerMain}>
      <audio 
        ref={audioRef} 
        preload="metadata"
        crossOrigin="anonymous"
      ></audio>

      <div className={styles.controls}>
        <button className={styles.btnControl} onClick={playPreviousChapter} title="Previous Chapter">
          <SkipBack size={20} />
        </button>
        <button className={styles.btnPlayPause} onClick={togglePlayPause} title="Play/Pause">
          {isPlaying ? <Pause size={24} /> : <Play size={24} />}
        </button>
        <button className={styles.btnControl} onClick={playNextChapter} title="Next Chapter">
          <SkipForward size={20} />
        </button>
        
        <div className={styles.speedControl}>
          <label htmlFor="speed-slider">Speed:</label>
          <input
            type="range"
            id="speed-slider"
            className={styles.speedSlider}
            min="0.5"
            max="2.0"
            step="0.01"
            value={playbackRate}
            onChange={(e) => { setPlaybackRate(parseFloat(e.target.value)) }}
          />
          <span className={styles.speedValue}>{playbackRate.toFixed(1)}x</span>
        </div>

        <div className={styles.volumeControl}>
          <label htmlFor="volume-slider">Volume:</label>
          <input
            type="range"
            id="volume-slider"
            className={styles.volumeSlider}
            min="0"
            max="100"
            value={volume * 100}
            onChange={(e) => { setVolume(parseFloat(e.target.value) / 100) }}
          />
          <span className={styles.volumeValue}>{Math.round(volume * 100)}%</span>
        </div>
      </div>

      <div className={styles.progressContainer}>
        <div className={styles.progressBar}>
          <div className={styles.progressFilled} style={{ width: `${progressPercent}%` }}></div>
          <input
            type="range"
            className={styles.progressSlider}
            min="0"
            max="100"
            value={progressPercent}
            step="0.1"
            onChange={handleProgressChange}
          />
        </div>
        <div className={styles.timeDisplay}>
          <span>{formatTime(displayTime)}</span>
          <span>{formatTime(displayDuration)}</span>
        </div>
      </div>

      <ChunkTimeline
        currentTime={displayTime}
        totalDuration={displayDuration}
        currentChunkIndex={currentChunkIndex}
      />
    </div>
  )
}

export default AudioPlayer

