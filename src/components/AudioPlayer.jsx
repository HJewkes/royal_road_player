import { useState, useEffect, useRef } from 'react'
import { SkipBack, Play, Pause, SkipForward } from 'lucide-react'
import ChunkTimeline from './ChunkTimeline'
import styles from './AudioPlayer.module.css'

function AudioPlayer({ book, chapter, onChapterChange, onAudioRef }) {
  const audioRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playbackRate, setPlaybackRate] = useState(1.0)
  const [volume, setVolume] = useState(1.0)
  
  // Chunked audio state
  const [chunkAudios, setChunkAudios] = useState([])
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0)
  const [chunkDurations, setChunkDurations] = useState([])
  const [chunkStartTimes, setChunkStartTimes] = useState([0])
  const [totalDuration, setTotalDuration] = useState(0)
  const [chunkMetadata, setChunkMetadata] = useState(null)
  const [chapterTextLength, setChapterTextLength] = useState(0)

  useEffect(() => {
    if (onAudioRef) {
      onAudioRef(audioRef.current)
    }
  }, [onAudioRef])

  useEffect(() => {
    if (!chapter) return

    const wasPlaying = isPlaying
    loadChapter(chapter, wasPlaying)
  }, [chapter])

  const loadChapter = async (chapterData, shouldPlay = false) => {
    if (!book || !chapterData) return

    try {
      const response = await fetch(`/api/books/${book.id}/chapters/${chapterData.chapter_number}`)
      const chapterDetails = await response.json()

      if (chapterDetails.audio_urls && chapterDetails.audio_urls.length > 0) {
        if (chapterDetails.is_chunked) {
          // Load chunk metadata for timeline
          await loadChunkMetadata(chapterData.title)
          // Load chunked audio
          await loadChunkedAudio(chapterDetails.audio_urls, chapterData.startTime || 0, shouldPlay)
        } else {
          // Single audio file
          setChunkAudios([])
          setChunkMetadata(null)
          audioRef.current.src = chapterDetails.audio_urls[0]
          audioRef.current.load()
          if (chapterData.startTime > 0) {
            audioRef.current.currentTime = chapterData.startTime
          }
          if (shouldPlay) {
            audioRef.current.play()
            setIsPlaying(true)
          }
        }
      } else {
        console.log(`No audio available for chapter ${chapterData.chapter_number}`)
        audioRef.current.pause()
        setIsPlaying(false)
      }
    } catch (error) {
      console.error('Failed to load chapter:', error)
      alert('Failed to load chapter')
    }
  }

  const loadChunkMetadata = async (chapterTitle) => {
    try {
      const response = await fetch(`/api/books/${book.id}/chapters/${encodeURIComponent(chapterTitle)}/chunks`)
      const data = await response.json()
      setChunkMetadata(data.chunks || [])
      setChapterTextLength(data.text_length || 0)
    } catch (error) {
      console.error('Failed to load chunk metadata:', error)
      setChunkMetadata(null)
    }
  }

  const loadChunkedAudio = async (audioUrls, startTime = 0, shouldPlay = false) => {
    setChunkAudios(audioUrls)
    setCurrentChunkIndex(0)
    
    // Preload all chunks to get durations
    await preloadChunkDurations(audioUrls)
    
    // Calculate which chunk to start with
    const { chunkIndex, chunkTime } = findChunkForTime(startTime)
    setCurrentChunkIndex(chunkIndex)
    
    // Load the appropriate chunk
    audioRef.current.src = audioUrls[chunkIndex]
    audioRef.current.load()
    
    audioRef.current.addEventListener('loadedmetadata', () => {
      if (startTime > 0) {
        audioRef.current.currentTime = chunkTime
      }
      if (shouldPlay) {
        audioRef.current.play()
        setIsPlaying(true)
      }
    }, { once: true })
    
    // Set up chunk transition listener
    setupChunkTransitionListener()
  }

  const preloadChunkDurations = async (audioUrls) => {
    const durations = []
    const promises = audioUrls.map((url, index) => {
      return new Promise((resolve) => {
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

  const findChunkForTime = (totalTime) => {
    for (let i = 0; i < chunkStartTimes.length - 1; i++) {
      const chunkStart = chunkStartTimes[i]
      const chunkEnd = chunkStartTimes[i + 1]
      
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

  const getTotalTime = () => {
    if (chunkStartTimes.length === 0) {
      return audioRef.current?.currentTime || 0
    }
    const chunkStart = chunkStartTimes[currentChunkIndex] || 0
    return chunkStart + (audioRef.current?.currentTime || 0)
  }

  const setupChunkTransitionListener = () => {
    const handleEnded = () => {
      if (currentChunkIndex < chunkAudios.length - 1) {
        const nextIndex = currentChunkIndex + 1
        setCurrentChunkIndex(nextIndex)
        audioRef.current.src = chunkAudios[nextIndex]
        audioRef.current.load()
        
        audioRef.current.addEventListener('loadedmetadata', () => {
          audioRef.current.play()
          setupChunkTransitionListener()
        }, { once: true })
      } else {
        // Chapter finished
        handleChapterEnd()
      }
    }
    
    audioRef.current.removeEventListener('ended', handleEnded)
    audioRef.current.addEventListener('ended', handleEnded, { once: true })
  }

  const handleChapterEnd = () => {
    if (!chapter) return
    
    const nextNum = chapter.chapter_number + 1
    const nextChapter = book.chapters?.find(c => c.chapter_number === nextNum)
    
    if (nextChapter && nextChapter.has_audio) {
      onChapterChange({ ...nextChapter, startTime: 0 })
    } else {
      console.log('Reached end of available audio')
      audioRef.current.pause()
      setIsPlaying(false)
    }
  }

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleLoadedMetadata = () => {
      setDuration(audio.duration)
      if (chunkAudios.length > 0 && totalDuration > 0) {
        setDuration(totalDuration)
      }
    }

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
      saveProgress()
    }

    const handleEnded = () => {
      setIsPlaying(false)
    }

    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('ended', handleEnded)

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('ended', handleEnded)
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
    const handleKeyDown = (e) => {
      if (e.code === 'Space' && e.target.tagName !== 'INPUT') {
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
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const togglePlayPause = () => {
    if (audioRef.current.paused) {
      audioRef.current.play()
      setIsPlaying(true)
    } else {
      audioRef.current.pause()
      setIsPlaying(false)
    }
  }

  const playPreviousChapter = () => {
    if (!chapter) return
    const prevNum = chapter.chapter_number - 1
    if (prevNum >= 1) {
      onChapterChange({ ...book.chapters.find(c => c.chapter_number === prevNum), startTime: 0 })
    }
  }

  const playNextChapter = () => {
    if (!chapter) return
    const nextNum = chapter.chapter_number + 1
    const nextChapter = book.chapters?.find(c => c.chapter_number === nextNum)
    if (nextChapter && nextChapter.has_audio) {
      onChapterChange({ ...nextChapter, startTime: 0 })
    } else {
      console.log(`Chapter ${nextNum} doesn't have audio yet`)
      audioRef.current.pause()
      setIsPlaying(false)
    }
  }

  const seekToTotalTime = (totalTime, preservePlayState = true) => {
    const { chunkIndex, chunkTime } = findChunkForTime(totalTime)
    const wasPlaying = preservePlayState && isPlaying
    
    if (chunkIndex !== currentChunkIndex) {
      setCurrentChunkIndex(chunkIndex)
      audioRef.current.src = chunkAudios[chunkIndex]
      audioRef.current.load()
      
      audioRef.current.addEventListener('loadedmetadata', () => {
        audioRef.current.currentTime = chunkTime
        setupChunkTransitionListener()
        if (wasPlaying) {
          audioRef.current.play()
          setIsPlaying(true)
        }
      }, { once: true })
    } else {
      audioRef.current.currentTime = chunkTime
    }
  }

  const seekForward = (seconds) => {
    if (chunkAudios.length > 0 && totalDuration > 0) {
      const currentTime = getTotalTime()
      const newTime = Math.min(totalDuration, currentTime + seconds)
      seekToTotalTime(newTime)
    } else if (audioRef.current.duration) {
      audioRef.current.currentTime = Math.min(audioRef.current.duration, audioRef.current.currentTime + seconds)
    }
  }

  const seekBackward = (seconds) => {
    if (chunkAudios.length > 0 && totalDuration > 0) {
      const currentTime = getTotalTime()
      const newTime = Math.max(0, currentTime - seconds)
      seekToTotalTime(newTime)
    } else if (audioRef.current.duration) {
      audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - seconds)
    }
  }

  const handleProgressChange = (e) => {
    const percent = e.target.value
    
    if (chunkAudios.length > 0 && totalDuration > 0) {
      const totalTime = (percent / 100) * totalDuration
      seekToTotalTime(totalTime)
    } else if (audioRef.current.duration) {
      const time = (percent / 100) * audioRef.current.duration
      audioRef.current.currentTime = time
    }
  }

  const saveProgress = () => {
    if (!book || !chapter) return

    // Throttle saves (every 5 seconds)
    if (window.lastSave && Date.now() - window.lastSave < 5000) return

    try {
      const positionSeconds = chunkAudios.length > 0 
        ? getTotalTime() 
        : audioRef.current.currentTime
      
      const completed = chunkAudios.length > 0
        ? (currentChunkIndex >= chunkAudios.length - 1 && audioRef.current.ended)
        : audioRef.current.ended
      
      fetch('/api/progress', {
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
      
      window.lastSave = Date.now()
    } catch (error) {
      console.error('Failed to save progress:', error)
    }
  }

  const formatTime = (seconds) => {
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
      <audio ref={audioRef} preload="metadata"></audio>

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

      {chunkMetadata && chunkMetadata.length > 0 && (
        <ChunkTimeline
          chunkMetadata={chunkMetadata}
          chapterTextLength={chapterTextLength}
          currentTime={displayTime}
          totalDuration={displayDuration}
          currentChunkIndex={currentChunkIndex}
        />
      )}

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
            onChange={(e) => setPlaybackRate(parseFloat(e.target.value))}
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
            onChange={(e) => setVolume(e.target.value / 100)}
          />
          <span className={styles.volumeValue}>{Math.round(volume * 100)}%</span>
        </div>
      </div>
    </div>
  )
}

export default AudioPlayer

