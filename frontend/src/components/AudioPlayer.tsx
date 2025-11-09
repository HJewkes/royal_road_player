import { useState, useEffect, useRef, useMemo } from 'react'
import { Play, Pause, Volume2, VolumeX, Gauge, HelpCircle, FileText } from 'lucide-react'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import type { Book, Chapter } from '../types'
import styles from './AudioPlayer.module.css'

interface AudioPlayerProps {
  book: Book | null
  // Chapter is now managed internally via playingChapter from store
  onAudioRef?: (audio: HTMLAudioElement | null) => void
}

interface ChunkTimeInfo {
  chunkIndex: number
  chunkTime: number
}

// Component to load and display chunk text on-demand
function ChunkTextDisplay({ 
  bookId, 
  chapterNumber, 
  chunkMetadata, 
  displayedChunkIndex
}: { 
  bookId?: string
  chapterNumber?: number
  chunkMetadata: any[]
  displayedChunkIndex: number | null
}) {
  const [chunkText, setChunkText] = useState<string | null>(null)
  const [loadingText, setLoadingText] = useState(false)
  const [currentChunkIndex, setCurrentChunkIndex] = useState<number | null>(null)
  
  // Determine which chunk to display
  const chunkToDisplay = useMemo(() => {
    if (displayedChunkIndex !== null && displayedChunkIndex >= 0 && displayedChunkIndex < chunkMetadata.length) {
      return chunkMetadata[displayedChunkIndex]
    }
    
    // Fallback: find first chunk with audio timing
    const firstChunkWithAudio = chunkMetadata.findIndex(
      (c: any) => c.audio_start_time !== null && c.audio_start_time !== undefined
    )
    if (firstChunkWithAudio >= 0) {
      return chunkMetadata[firstChunkWithAudio]
    }
    
    // Last resort: just use first chunk
    return chunkMetadata.length > 0 ? chunkMetadata[0] : null
  }, [chunkMetadata, displayedChunkIndex])
  
  // Load text when chunk changes
  useEffect(() => {
    if (!chunkToDisplay || !bookId || !chapterNumber) {
      setChunkText(null)
      setCurrentChunkIndex(null)
      return
    }
    
    const chunkIdx = chunkToDisplay.index
    if (currentChunkIndex === chunkIdx && chunkText !== null) {
      // Already loaded for this chunk
      return
    }
    
    // Check if text is already in metadata
    if (chunkToDisplay.text) {
      setChunkText(chunkToDisplay.text)
      setCurrentChunkIndex(chunkIdx)
      return
    }
    
    // Load text on-demand
    setLoadingText(true)
    setCurrentChunkIndex(chunkIdx)
    fetch(`/api/books/${bookId}/chapters/${chapterNumber}/chunks/${chunkIdx}/text`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`Failed to load chunk text: ${res.statusText}`)
        }
        return res.json()
      })
      .then(data => {
        setChunkText(data.text || 'No text available')
        setLoadingText(false)
      })
      .catch(err => {
        console.error('Failed to load chunk text:', err)
        setChunkText('Failed to load text')
        setLoadingText(false)
      })
  }, [chunkToDisplay, bookId, chapterNumber, currentChunkIndex, chunkText])
  
  if (!chunkToDisplay) return null
  
  // Always use compact mode (streamlined display)
  return (
    <>
      {!loadingText && (
        <span className={styles.chunkIdFixed}>Chunk {chunkToDisplay.index}</span>
      )}
      <div className={styles.chunkTextContent}>
        {loadingText ? 'Loading...' : (chunkText || 'No text available')}
      </div>
    </>
  )
}

function AudioPlayer({ book, onAudioRef }: AudioPlayerProps) {
  const { loadPlayingChunkMetadata, playingChapter, chapters, setPlayingChapter, currentBook, currentChapter, playingChunkMetadata } = useAudiobookStore()
  const toast = useToastStore()
  const chapter = playingChapter // Use playingChapter from store instead of prop
  const [displayedChunkIndex, setDisplayedChunkIndex] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const nextAudioRef = useRef<HTMLAudioElement>(null)  // Second audio element for seamless transitions
  const activeAudioRef = useRef<HTMLAudioElement | null>(null)  // Track which audio is currently active
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playbackRate, setPlaybackRate] = useState(1.0)
  const [volume, setVolume] = useState(1.0)
  const [showSpeedMenu, setShowSpeedMenu] = useState(false)
  const [showVolumeSlider, setShowVolumeSlider] = useState(false)
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false)
  const [showChunkText, setShowChunkText] = useState(false)
  const [isClosingChunkText, setIsClosingChunkText] = useState(false)
  const [skipDuration, setSkipDuration] = useState(10) // Default 10 seconds
  const speedControlRef = useRef<HTMLDivElement>(null)
  const keyboardHelpRef = useRef<HTMLDivElement>(null)
  const chunkTextRef = useRef<HTMLDivElement>(null)
  
  // Speed presets (common speeds used in modern players)
  const speedPresets = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
  
  // Skip duration presets (common skip durations)
  const skipPresets = [5, 10, 15, 30, 60]
  
  // Chunked audio state
  const [chunkAudios, setChunkAudios] = useState<string[]>([])
  const [allAudioUrls, setAllAudioUrls] = useState<string[]>([]) // Store all audio URLs for text lookup (even for concatenated audio)
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0)
  // @ts-ignore - chunkDurations is used via setChunkDurations callback in updateChunkDuration
  const [chunkDurations, setChunkDurations] = useState<number[]>([]) // Used in updateChunkDuration via setChunkDurations callback
  const [chunkStartTimes, setChunkStartTimes] = useState<number[]>([0])
  const [totalDuration, setTotalDuration] = useState(0)
  
  // Preload next chunks by warming browser cache (no Audio elements to avoid interference)
  const preloadedUrls = useRef<Set<string>>(new Set())
  
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
    if (onAudioRef && activeAudioRef.current) {
      onAudioRef(activeAudioRef.current)
    } else if (onAudioRef && audioRef.current) {
      onAudioRef(audioRef.current)
    }
  }, [onAudioRef])

  const chapterRef = useRef<Chapter | null>(null)
  
  useEffect(() => {
    if (!chapter) return
    
    // Prevent multiple loads of the same chapter
    if (chapterRef.current?.chapter_number === chapter.chapter_number && 
        chapterRef.current?.book_id === chapter.book_id) {
      return
    }
    
    chapterRef.current = chapter
    const wasPlaying = isPlaying
    void loadChapter(chapter, wasPlaying)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapter])

  // Restore progress from localStorage or URL
  const getSavedPosition = (chapterNumber: number, fallbackStartTime = 0): number => {
    try {
      // First check URL
      const urlParams = new URLSearchParams(window.location.search)
      const urlChapter = urlParams.get('chapter')
      const urlPosition = urlParams.get('position')
      
      if (urlChapter && parseInt(urlChapter, 10) === chapterNumber && urlPosition) {
        const position = parseFloat(urlPosition)
        if (!isNaN(position) && position >= 0) {
          return position
        }
      }
      
      // Fall back to localStorage
      const saved = localStorage.getItem('audiobook_player_state')
      if (saved) {
        const state = JSON.parse(saved) as { bookId?: string; chapter?: number; position?: number }
        if (state.bookId === book?.id && state.chapter === chapterNumber && state.position !== undefined) {
          const position = state.position
          if (!isNaN(position) && position >= 0) {
            return position
          }
        }
      }
    } catch (error) {
      console.error('Failed to restore position:', error)
    }
    
    // Use fallback startTime
    return fallbackStartTime
  }

  const loadChapter = async (chapterData: Chapter, shouldPlay = false): Promise<void> => {
    if (!book || !chapterData || !audioRef.current) return

    try {
      // Restore saved position (from URL, localStorage, or chapterData.startTime)
      const savedPosition = getSavedPosition(chapterData.chapter_number, chapterData.startTime || 0)
      
      const response = await fetch(`/api/books/${book.id}/chapters/${chapterData.chapter_number}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch chapter: ${response.statusText}`)
      }
      const chapterDetails = await response.json() as { audio_urls?: string[]; is_chunked?: boolean }

      if (chapterDetails.audio_urls && chapterDetails.audio_urls.length > 0) {
        if (chapterDetails.is_chunked) {
          // Try to use concatenated audio first (seamless playback, no fade-in)
          try {
            const concatResponse = await fetch(
              `/api/books/${book.id}/chapters/${chapterData.chapter_number}/concatenate`,
              { method: 'POST' }
            )
            
            if (concatResponse.ok) {
              const concatData = await concatResponse.json() as { audio_url?: string }
              if (concatData.audio_url) {
                // Load chunk metadata for timeline (still needed for display)
                await loadPlayingChunkMetadata(chapterData.chapter_number)
                // Store audio URLs for text lookup (even though we're using concatenated file)
                setAllAudioUrls(chapterDetails.audio_urls || [])
                // Use concatenated file as single audio file
                setChunkAudios([])
                audioRef.current.src = concatData.audio_url
                audioRef.current.load()
                
                const handleSingleFileEnded = (): void => {
                  setIsPlaying(false)
                  void handleChapterEnd()
                }
                
                audioRef.current.addEventListener('loadedmetadata', async () => {
                  // Set volume to 1.0 immediately to prevent fade-in
                  audioRef.current!.volume = 1.0
                  
                  // For concatenated audio, initialize chunkStartTimes for chunk tracking
                  // Load chunk metadata if not already loaded
                  const currentChunkMetadata = useAudiobookStore.getState().playingChunkMetadata
                  if (!currentChunkMetadata || currentChunkMetadata.length === 0) {
                    await loadPlayingChunkMetadata(chapterData.chapter_number)
                  }
                  
                  // Get updated chunk metadata after loading
                  const updatedChunkMetadata = useAudiobookStore.getState().playingChunkMetadata
                  
                  // Initialize chunkStartTimes for concatenated audio
                  // Use stored durations from metadata if available, otherwise estimate
                  // IMPORTANT: Only include chunks that have audio files (matching audioUrls order)
                  const totalDur = audioRef.current!.duration || 0
                  if (totalDur > 0 && updatedChunkMetadata && updatedChunkMetadata.length > 0 && book) {
                    // Get audio URLs to know which chunks are actually in the concatenated file
                    const chapterDetails = await fetch(`/api/books/${book.id}/chapters/${chapterData.chapter_number}`).then(r => r.json())
                    const audioUrls = chapterDetails.audio_urls || []
                    
                    // Build a map of chunk index to metadata for quick lookup
                    const chunkMap = new Map<number, typeof updatedChunkMetadata[0]>()
                    updatedChunkMetadata.forEach(chunk => {
                      if (chunk) chunkMap.set(chunk.index, chunk)
                    })
                    
                    // Extract chunk indices from audio URLs (they're sorted by chunk index)
                    // URL format: /audio/.../chapters/01/chunks/{chunkIndex}/audio.wav
                    const chunkIndices: number[] = []
                    audioUrls.forEach((url: string) => {
                      const match = url.match(/chunks\/(\d+)\/audio\.wav/)
                      if (match && match[1]) {
                        chunkIndices.push(parseInt(match[1], 10))
                      }
                    })
                    
                    const newStartTimes = [0]
                    let cumulative = 0
                    let hasStoredDurations = false
                    
                    // Build start times only for chunks that have audio files
                    for (const chunkIndex of chunkIndices) {
                      const chunk = chunkMap.get(chunkIndex)
                      if (chunk && chunk.audio_duration_seconds && chunk.audio_duration_seconds > 0) {
                        cumulative += chunk.audio_duration_seconds
                        hasStoredDurations = true
                      } else {
                        // Fallback: estimate by dividing total duration evenly
                        const avgChunkDuration = totalDur / chunkIndices.length
                        cumulative += avgChunkDuration
                      }
                      newStartTimes.push(cumulative)
                    }
                    
                    setChunkStartTimes(newStartTimes)
                    // Use calculated total if we have stored durations, otherwise use audio duration
                    setTotalDuration(hasStoredDurations ? cumulative : totalDur)
                  }
                  
                  if (savedPosition > 0) {
                    // Set up a one-time seeked listener to update chunk when seek completes
                    const handleSeeked = (): void => {
                      if (playingChunkMetadata && playingChunkMetadata.length > 0 && audioRef.current) {
                        const currentTime = audioRef.current.currentTime
                        const result = findChunkForTime(currentTime)
                        if (result && result.chunkIndex >= 0 && result.chunkIndex < playingChunkMetadata.length) {
                          setDisplayedChunkIndex(result.chunkIndex)
                        }
                      }
                      audioRef.current!.removeEventListener('seeked', handleSeeked)
                    }
                    audioRef.current!.addEventListener('seeked', handleSeeked, { once: true })
                    audioRef.current!.currentTime = savedPosition
                  }
                  if (shouldPlay) {
                    // Play immediately - volume is already set
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
                return  // Successfully loaded concatenated audio
              }
            }
          } catch (concatError) {
            // Fall through to chunked audio loading
          }
          
          // Fallback: Load chunked audio (original behavior)
          // Load chunk metadata for timeline and text display
          await loadPlayingChunkMetadata(chapterData.chapter_number)
          setDisplayedChunkIndex(null) // Reset displayed chunk
          // Store audio URLs for text lookup
          setAllAudioUrls(chapterDetails.audio_urls || [])
          // Load chunked audio with saved position
          await loadChunkedAudio(chapterDetails.audio_urls, savedPosition, shouldPlay)
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
            void handleChapterEnd()
          }
          
          audioRef.current.addEventListener('loadedmetadata', () => {
            // Set volume to 1.0 immediately to prevent fade-in
            audioRef.current!.volume = 1.0
            if (savedPosition > 0) {
              audioRef.current!.currentTime = savedPosition
            }
            if (shouldPlay) {
              // Play immediately - volume is already set
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
        audioRef.current.pause()
        setIsPlaying(false)
      }
          } catch (error) {
            toast.error(error instanceof Error ? error.message : 'Failed to load chapter')
          }
  }

  const loadingRef = useRef(false)
  
  const loadChunkedAudio = async (audioUrls: string[], startTime = 0, shouldPlay = false): Promise<void> => {
    if (!audioRef.current) return
    
          // Prevent multiple simultaneous loads
          if (loadingRef.current) {
            return
          }
    
          loadingRef.current = true

          try {
      setChunkAudios(audioUrls)
      setAllAudioUrls(audioUrls) // Store for text lookup
      setCurrentChunkIndex(0)
      
      // Initialize chunkStartTimes from stored durations if available
      // IMPORTANT: Match chunks to audioUrls order (only chunks with audio files)
      if (playingChunkMetadata && playingChunkMetadata.length > 0 && audioUrls.length > 0) {
        // Build a map of chunk index to metadata for quick lookup
        const chunkMap = new Map<number, typeof playingChunkMetadata[0]>()
        playingChunkMetadata.forEach(chunk => {
          if (chunk) chunkMap.set(chunk.index, chunk)
        })
        
        // Extract chunk indices from audio URLs (they're sorted by chunk index)
        // URL format: /audio/.../chapters/01/chunks/{chunkIndex}/audio.wav
        const chunkIndices: number[] = []
        audioUrls.forEach((url: string) => {
          const match = url.match(/chunks\/(\d+)\/audio\.wav/)
          if (match && match[1]) {
            chunkIndices.push(parseInt(match[1], 10))
          }
        })
        
        const newStartTimes = [0]
        let cumulative = 0
        let hasStoredDurations = false
        
        // Build start times only for chunks that have audio files, in audioUrls order
        for (const chunkIndex of chunkIndices) {
          const chunk = chunkMap.get(chunkIndex)
          if (chunk && chunk.audio_duration_seconds && chunk.audio_duration_seconds > 0) {
            cumulative += chunk.audio_duration_seconds
            hasStoredDurations = true
          }
          newStartTimes.push(cumulative)
        }
        
        if (hasStoredDurations) {
          setChunkStartTimes(newStartTimes)
          setTotalDuration(cumulative)
        }
      }
      
      // Preload chunk durations (don't wait - it will update as it loads)
      void preloadChunkDurations(audioUrls).catch((error) => {
        console.error('Error preloading chunk durations:', error)
      })
      
            // Calculate which chunk to start with (use index 0 initially, will update when durations load)
            let chunkIndex = 0
            let chunkTime = 0

            if (startTime > 0) {
              const result = findChunkForTime(startTime)
              if (result) {
                chunkIndex = result.chunkIndex
                chunkTime = result.chunkTime
              }
            }
      
      setCurrentChunkIndex(chunkIndex)
      
            // Load the appropriate chunk
            const chunkUrl = audioUrls[chunkIndex]
            if (chunkUrl) {
        // Set volume BEFORE loading to prevent fade-in
        audioRef.current.volume = 1.0
        audioRef.current.src = chunkUrl
        audioRef.current.load()
        // Set volume again immediately after load()
        audioRef.current.volume = 1.0
            } else {
              loadingRef.current = false
              return
            }
      
      // Set volume on canplay event (fires early)
      audioRef.current.addEventListener('canplay', () => {
        if (audioRef.current) {
          audioRef.current.volume = 1.0
        }
      }, { once: true })
      
            audioRef.current.addEventListener('loadedmetadata', () => {
              const duration = audioRef.current?.duration || 0
        
        // Update duration for this chunk (using the already-loaded audio element)
        if (duration > 0) {
          updateChunkDuration(chunkIndex, duration)
        }
        
        // Set volume again before any playback
        if (audioRef.current) {
          audioRef.current.volume = 1.0
        }
        
        if (startTime > 0) {
          audioRef.current!.currentTime = chunkTime
        }
        if (shouldPlay) {
          // Set volume one more time before playing to prevent browser fade-in
          audioRef.current!.volume = 1.0
          // Play immediately - volume is already set
          const playPromise = audioRef.current!.play()
          if (playPromise !== undefined) {
            playPromise.catch((error) => {
              console.error('Playback failed:', error)
            })
          }
          setIsPlaying(true)
        }
        // Set up chunk transition listener after metadata is loaded
        setupChunkTransitionListener()
        loadingRef.current = false
      }, { once: true })
      
      audioRef.current.addEventListener('error', (e) => {
        console.error(`Error loading chunk ${chunkIndex}:`, e)
        toast.error(`Failed to load chunk ${chunkIndex}`)
        loadingRef.current = false
      }, { once: true })
    } catch (error) {
      console.error('Error in loadChunkedAudio:', error)
      loadingRef.current = false
    }
  }

  const preloadChunkDurations = async (audioUrls: string[]): Promise<void> => {
    // Initialize with zeros - we'll load durations lazily as chunks are played
    const durations: number[] = new Array(audioUrls.length).fill(0)
    setChunkDurations(durations)
    setChunkStartTimes([0])
    setTotalDuration(0)
    
    // Preload next 5 chunks starting from chunk 1 (chunk 0 is current)
    // This will preload chunks 1-5 (indices 1-5)
    preloadNextChunks(audioUrls, 1, 5)
  }
  
  const preloadNextChunks = (audioUrls: string[], startIndex: number, count: number): void => {
    // Preload by warming browser cache using fetch - NO Audio elements at all
    // This completely prevents any interference with the main audio player
    for (let i = 0; i < count && startIndex + i < audioUrls.length; i++) {
      const chunkIndex = startIndex + i
      const url = audioUrls[chunkIndex]
      if (!url) {
        continue
      }
      
      // Check if already preloaded
      if (preloadedUrls.current.has(url)) {
        continue
      }
      
      preloadedUrls.current.add(url)
      
      // Warm cache by fetching the audio file (browser will cache it)
      // Use HEAD request to avoid downloading full file
      fetch(url, { method: 'HEAD', cache: 'force-cache' })
        .catch(() => {
          // Ignore errors - cache warming is best effort
        })
      
      // Don't create any Audio elements - durations will load from main player as chunks play
      // This completely eliminates any possibility of interference
    }
  }
  
  // Don't create new Audio objects - use the one that's already loaded
  // This function is called when the audio element's metadata loads
  // Prefer stored durations from metadata, fallback to calculated duration
  // IMPORTANT: chunkIndex here is the array position in chunkAudios/allAudioUrls, NOT the chunk.index
  const updateChunkDuration = (chunkIndex: number, duration: number): void => {
    if (duration <= 0 || isNaN(duration)) return
    
    // chunkIndex is the array position (0-based), we need to find the actual chunk index
    const audioUrlsToUse = allAudioUrls.length > 0 ? allAudioUrls : chunkAudios
    if (chunkIndex >= audioUrlsToUse.length) {
      console.warn(`updateChunkDuration: chunkIndex ${chunkIndex} >= audioUrlsToUse.length ${audioUrlsToUse.length}`)
      return
    }
    
    const audioUrl = audioUrlsToUse[chunkIndex]
    if (!audioUrl) return
    
    // Extract actual chunk index from URL
    const match = audioUrl.match(/chunks\/(\d+)\/audio\.wav/)
    if (!match || !match[1]) {
      console.warn(`updateChunkDuration: Could not extract chunk index from URL: ${audioUrl}`)
      return
    }
    
    const actualChunkIndex = parseInt(match[1], 10)
    
    // Check if we have stored duration from metadata (preferred)
    const chunk = playingChunkMetadata?.find(c => c.index === actualChunkIndex)
    const storedDuration = chunk?.audio_duration_seconds
    const durationToUse = (storedDuration && storedDuration > 0) ? storedDuration : duration
    
    setChunkDurations((prev) => {
      const updated = [...prev]
      // Ensure array is large enough
      while (updated.length <= chunkIndex) {
        updated.push(0)
      }
      if (updated[chunkIndex] === durationToUse) return prev // Already set
      
      updated[chunkIndex] = durationToUse
      
      // Rebuild chunkStartTimes from audioUrls order (matching the initialization logic)
      if (playingChunkMetadata && audioUrlsToUse.length > 0) {
        const chunkMap = new Map<number, typeof playingChunkMetadata[0]>()
        playingChunkMetadata.forEach(c => {
          if (c) chunkMap.set(c.index, c)
        })
        
        const chunkIndices: number[] = []
        audioUrlsToUse.forEach((url: string) => {
          const urlMatch = url.match(/chunks\/(\d+)\/audio\.wav/)
          if (urlMatch && urlMatch[1]) {
            chunkIndices.push(parseInt(urlMatch[1], 10))
          }
        })
        
        const newStartTimes = [0]
        let cumulative = 0
        
        for (let i = 0; i < chunkIndices.length; i++) {
          const chunkIdx = chunkIndices[i]
          if (chunkIdx === undefined) continue
          const chunkMeta = chunkMap.get(chunkIdx)
          // Use stored duration if available, otherwise use updated array if we have it
          const dur = (chunkMeta && chunkMeta.audio_duration_seconds && chunkMeta.audio_duration_seconds > 0) 
            ? chunkMeta.audio_duration_seconds 
            : (updated[i] || 0)
          cumulative += dur
          newStartTimes.push(cumulative)
        }
        
        setChunkStartTimes(newStartTimes)
        setTotalDuration(cumulative)
      } else {
        // Fallback: build from updated array (old behavior, less accurate)
        let cumulative = 0
        const newStartTimes = [0]
        for (let i = 0; i < updated.length; i++) {
          cumulative += (updated[i] || 0)
          newStartTimes.push(cumulative)
        }
        setChunkStartTimes(newStartTimes)
        setTotalDuration(cumulative)
      }
      
      return updated
    })
  }

  // Simple binary search using backend-provided audio_start_time/audio_end_time
  const findChunkForTime = (totalTime: number): ChunkTimeInfo | null => {
    if (!playingChunkMetadata || playingChunkMetadata.length === 0) {
      return null  // Return null if metadata not loaded yet
    }

    // Filter to chunks with audio timing info
    const chunksWithAudio = playingChunkMetadata.filter(
      c => c.audio_start_time !== null && c.audio_start_time !== undefined &&
           c.audio_end_time !== null && c.audio_end_time !== undefined
    )
    
    if (chunksWithAudio.length === 0) {
      return null  // Return null if no chunks with audio timing
    }
    
    // Binary search for the chunk containing this time
    let left = 0
    let right = chunksWithAudio.length - 1
    
    while (left <= right) {
      const mid = Math.floor((left + right) / 2)
      const chunk = chunksWithAudio[mid]
      if (!chunk) break
      
      const start = chunk.audio_start_time!
      const end = chunk.audio_end_time!
      
      if (totalTime >= start && totalTime < end) {
        // Found the chunk! Now find its index in the full playingChunkMetadata array
        const fullIndex = playingChunkMetadata.findIndex(c => c.index === chunk.index)
        return {
          chunkIndex: fullIndex >= 0 ? fullIndex : 0,
          chunkTime: totalTime - start
        }
      } else if (totalTime < start) {
        right = mid - 1
      } else {
        left = mid + 1
      }
    }
    
    // Time is beyond all chunks - return last chunk with audio
    const lastChunk = chunksWithAudio[chunksWithAudio.length - 1]
    if (!lastChunk) {
      return null
    }
    const fullIndex = playingChunkMetadata.findIndex(c => c.index === lastChunk.index)
    return {
      chunkIndex: fullIndex >= 0 ? fullIndex : 0,
      chunkTime: 0
    }
  }

  const getTotalTime = (): number => {
    const audio = activeAudioRef.current || audioRef.current
    if (chunkStartTimes.length === 0 || !audio) {
      return audio?.currentTime || 0
    }
    const chunkStart = chunkStartTimes[currentChunkIndex] || 0
    return chunkStart + (audio.currentTime || 0)
  }

  const setupChunkTransitionListener = (): void => {
    const currentActiveAudio = activeAudioRef.current || audioRef.current
    if (!currentActiveAudio) return
    
    const handleEnded = async (): Promise<void> => {
      // Use refs to get current values (always up-to-date)
      const currentIndex = currentChunkIndexRef.current
      const currentAudios = chunkAudiosRef.current
      
      if (currentIndex < currentAudios.length - 1) {
        const nextIndex = currentIndex + 1
        const nextUrl = currentAudios[nextIndex]
        if (nextUrl && (audioRef.current || nextAudioRef.current)) {
          // Use two audio elements for seamless transition - no src change on playing element
          // This prevents Chrome's fade-in behavior when changing src
          const currentAudio = activeAudioRef.current || audioRef.current
          const nextAudio = (activeAudioRef.current === audioRef.current) ? nextAudioRef.current : audioRef.current
          
          if (!nextAudio) {
            console.error('No next audio element available')
            return
          }
          
          // Load next chunk in the inactive audio element
          nextAudio.volume = 1.0
          nextAudio.src = nextUrl
          nextAudio.currentTime = 0
          
          // Wait for next audio to be ready, then switch seamlessly
          const handleNextReady = (): void => {
            if (!currentAudio || !nextAudio) return
            
            // Pause current audio
            currentAudio.pause()
            
            // Switch to next audio - it's already loaded and ready
            nextAudio.volume = 1.0
            nextAudio.currentTime = 0
            
            // Play immediately - no src change on this element, so no fade-in
            const playPromise = nextAudio.play()
            if (playPromise !== undefined) {
              playPromise.then(() => {
                if (nextAudio) {
                  nextAudio.volume = 1.0
                }
                // Update active ref
                activeAudioRef.current = nextAudio
              }).catch(() => {
                // Ignore
              })
            }
            
            // Update duration
            const duration = nextAudio.duration || 0
            if (duration > 0) {
              updateChunkDuration(nextIndex, duration)
            }
            
            // Remove listener
            nextAudio.removeEventListener('canplay', handleNextReady)
          }
          
          nextAudio.addEventListener('canplay', handleNextReady, { once: true })
          
          // Also update duration when metadata loads
          nextAudio.addEventListener('loadedmetadata', () => {
            if (!nextAudio) return
            const duration = nextAudio.duration || 0
            if (duration > 0) {
              updateChunkDuration(nextIndex, duration)
            }
          }, { once: true })
          
          setCurrentChunkIndex(nextIndex)
          setIsPlaying(true)
          
          // Preload next chunks ahead (no Audio elements created)
          preloadNextChunks(currentAudios, nextIndex + 1, 5)
          
          // Set up listener for next transition on the new active audio
          setupChunkTransitionListener()
        }
      } else {
        // Chapter finished - auto-advance to next chapter
        void handleChapterEnd()
      }
    }
    
    // Remove any existing listeners from both audio elements
    const activeAudioForListener = activeAudioRef.current || audioRef.current
    if (activeAudioForListener) {
      activeAudioForListener.removeEventListener('ended', handleEnded)
      activeAudioForListener.addEventListener('ended', () => { void handleEnded() }, { once: true })
    }
    // Also set up listener on the other audio element
    const otherAudio = (activeAudioForListener === audioRef.current) ? nextAudioRef.current : audioRef.current
    if (otherAudio) {
      otherAudio.removeEventListener('ended', handleEnded)
    }
  }

  const handleChapterEnd = async (): Promise<void> => {
    if (!chapter || !book) return
    
    setIsPlaying(false)
    const nextNum = chapter.chapter_number + 1
    const nextChapter = chapters.find((c) => c.chapter_number === nextNum)
    
    if (nextChapter && nextChapter.has_audio) {
      // Auto-advance to next chapter
      await setPlayingChapter(nextChapter.chapter_number, 0)
      // The useEffect will pick up the chapter change and load it
    } else {
      // No next chapter, stop playback
      if (audioRef.current) {
        audioRef.current.pause()
      }
      setIsPlaying(false)
    }
  }

  useEffect(() => {
    // Use active audio element, fallback to audioRef
    const audio = activeAudioRef.current || audioRef.current
    if (!audio) return

    const handleLoadedMetadata = (): void => {
      setDuration(audio.duration)
      if (chunkAudios.length > 0 && totalDuration > 0) {
        setDuration(totalDuration)
      }
      
      // Trigger a timeupdate event to update displayed chunk (if saved position was set)
      // The timeupdate handler will take care of updating displayedChunkIndex
      if (audio.currentTime > 0) {
        // Manually trigger timeupdate logic if we have a saved position
        const currentTime = audio.currentTime
        if (chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0) {
          const result = findChunkForTime(currentTime)
          if (result && result.chunkIndex >= 0 && result.chunkIndex < playingChunkMetadata.length) {
            setDisplayedChunkIndex(result.chunkIndex)
          }
        }
      }
    }

          const handleTimeUpdate = (): void => {
            const currentTime = audio.currentTime
            setCurrentTime(currentTime)
            saveProgress()

            // Update displayed chunk index based on current playback time
            // Works for both chunked audio and concatenated audio (if playingChunkMetadata is loaded)
            if (chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0) {
              // Update if we have a valid time (including 0)
              if (currentTime >= 0 && !isNaN(currentTime)) {
                const result = findChunkForTime(currentTime)
                
                if (result && result.chunkIndex >= 0 && result.chunkIndex < playingChunkMetadata.length) {
                  if (displayedChunkIndex !== result.chunkIndex) {
                    setDisplayedChunkIndex(result.chunkIndex)
                  }
                }
              }
            } else {
              // Single file or no chunks - clear displayed chunk
              if (displayedChunkIndex !== null) {
                setDisplayedChunkIndex(null)
              }
            }
          }
          
          const handleSeeked = (): void => {
            const currentTime = audio.currentTime
            if (chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0) {
              const result = findChunkForTime(currentTime)
              if (result && result.chunkIndex >= 0 && result.chunkIndex < playingChunkMetadata.length) {
                setDisplayedChunkIndex(result.chunkIndex)
              }
            }
          }

    // Don't add 'ended' listener here - it's handled by setupChunkTransitionListener
    // for chunked audio, or will be handled naturally for single-file audio
    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('seeked', handleSeeked)

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('seeked', handleSeeked)
    }
  }, [chunkAudios, totalDuration])

  // Update displayed chunk when playingChunkMetadata loads (for initial display on refresh)
  // This will set a fallback chunk, but the timeupdate handler will update it when audio starts
  useEffect(() => {
    if (chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0 && displayedChunkIndex === null) {
      const audio = activeAudioRef.current || audioRef.current
      // Only set fallback if audio isn't ready or is at time 0
      if (!audio || audio.readyState < 2 || audio.currentTime === 0) {
        // Set to first chunk with audio as fallback
        const firstChunkWithAudio = playingChunkMetadata.findIndex(
          c => c.audio_start_time !== null && c.audio_start_time !== undefined
        )
        if (firstChunkWithAudio >= 0) {
          setDisplayedChunkIndex(firstChunkWithAudio)
        }
      }
    }
  }, [playingChunkMetadata, chapter, displayedChunkIndex])

  useEffect(() => {
    // Update playback rate on active audio
    const audio = activeAudioRef.current || audioRef.current
    if (audio) {
      audio.playbackRate = playbackRate
    }
    // Also update the other audio element
    const otherAudio = (audio === audioRef.current) ? nextAudioRef.current : audioRef.current
    if (otherAudio) {
      otherAudio.playbackRate = playbackRate
    }
  }, [playbackRate])

  useEffect(() => {
    // Note: We keep volume state for the UI slider, but always set audio to 1.0 to prevent fade-in
    // The slider controls the volume state for display, but audio plays at full volume
    const audio = activeAudioRef.current || audioRef.current
    if (audio) {
      audio.volume = 1.0  // Always full volume, no fade-in
    }
    // Also update the other audio element
    const otherAudio = (audio === audioRef.current) ? nextAudioRef.current : audioRef.current
    if (otherAudio) {
      otherAudio.volume = 1.0
    }
  }, [volume])  // Re-run when volume changes to ensure it stays at 1.0

  // Close speed menu when clicking outside
  useEffect(() => {
    if (!showSpeedMenu) return
    
    const handleClickOutside = (e: MouseEvent): void => {
      const target = e.target as HTMLElement
      if (speedControlRef.current && !speedControlRef.current.contains(target)) {
        setShowSpeedMenu(false)
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => { document.removeEventListener('mousedown', handleClickOutside) }
  }, [showSpeedMenu])

  // Close keyboard help when clicking outside
  useEffect(() => {
    if (!showKeyboardHelp) return
    
    const handleClickOutside = (e: MouseEvent): void => {
      const target = e.target as HTMLElement
      if (keyboardHelpRef.current && !keyboardHelpRef.current.contains(target)) {
        // Don't close if clicking the help button
        if (!target.closest(`.${styles.btnKeyboardHelp}`)) {
          setShowKeyboardHelp(false)
        }
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => { document.removeEventListener('mousedown', handleClickOutside) }
  }, [showKeyboardHelp])

  // Close chunk text panel when clicking outside
  useEffect(() => {
    if (!showChunkText) return
    
    const handleClickOutside = (e: MouseEvent): void => {
      const target = e.target as HTMLElement
      if (chunkTextRef.current && !chunkTextRef.current.contains(target)) {
        // Don't close if clicking the chunk text button
        if (!target.closest(`.${styles.btnChunkText}`)) {
          if (showChunkText && !isClosingChunkText) {
            setIsClosingChunkText(true)
            setTimeout(() => {
              setShowChunkText(false)
              setIsClosingChunkText(false)
            }, 300)
          }
        }
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => { document.removeEventListener('mousedown', handleClickOutside) }
  }, [showChunkText, isClosingChunkText])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      // Don't handle if typing in an input
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') {
        return
      }
      
      if (e.code === 'Space') {
        e.preventDefault()
        togglePlayPause()
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault()
        seekBackward(skipDuration)
      } else if (e.code === 'ArrowRight') {
        e.preventDefault()
        seekForward(skipDuration)
      } else if (e.key === '?' || (e.key === 'h' && e.shiftKey)) {
        // Show keyboard help
        e.preventDefault()
        setShowKeyboardHelp(!showKeyboardHelp)
      } else if (e.key === 'Escape') {
        // Close modals/inputs
        if (showKeyboardHelp) {
          setShowKeyboardHelp(false)
        }
        if (showSpeedMenu) {
          setShowSpeedMenu(false)
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => { document.removeEventListener('keydown', handleKeyDown) }
  }, [showKeyboardHelp, showChunkText, showSpeedMenu])

  const togglePlayPause = (): void => {
    const audio = activeAudioRef.current || audioRef.current
    if (!audio) return
    
    if (audio.paused) {
      // Set volume to 1.0 immediately to prevent browser fade-in
      audio.volume = 1.0
      // Play immediately - volume is already set
      const playPromise = audio.play()
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          // Playback failed, but that's okay
        })
      }
      setIsPlaying(true)
    } else {
      audio.pause()
      setIsPlaying(false)
    }
  }


  const seekToTotalTime = (totalTime: number, preservePlayState = true): void => {
    if (!audioRef.current) return
    
    const result = findChunkForTime(totalTime)
    if (!result) {
      console.warn('Could not find chunk for time, metadata may not be loaded')
      return
    }
    
    const { chunkIndex, chunkTime } = result
    const wasPlaying = preservePlayState && isPlaying
    
    if (chunkIndex !== currentChunkIndex) {
      const chunkUrl = chunkAudios[chunkIndex]
      if (chunkUrl) {
        // Set volume BEFORE loading to prevent fade-in
        audioRef.current.volume = 1.0
        setCurrentChunkIndex(chunkIndex)
        audioRef.current.src = chunkUrl
        audioRef.current.load()
        // Set volume again immediately after load()
        audioRef.current.volume = 1.0
      }
      
      // Set volume on canplay event (fires early)
      audioRef.current.addEventListener('canplay', () => {
        if (audioRef.current) {
          audioRef.current.volume = 1.0
        }
      }, { once: true })
      
      audioRef.current.addEventListener('loadedmetadata', () => {
        if (!audioRef.current) return
        // Set volume to 1.0 again before any playback to prevent fade-in
        audioRef.current.volume = 1.0
        audioRef.current.currentTime = chunkTime
        setupChunkTransitionListener()
        if (wasPlaying) {
          // Set volume one more time before playing
          audioRef.current.volume = 1.0
          // Play immediately - volume is already set
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
  
  // Removed seekToChunk - ChunkTimeline is no longer in AudioPlayer
  // If needed for chapter management, it should be implemented in PlayerView

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

  // Separate throttles for localStorage (frequent) and URL (less frequent)
  const lastLocalStorageSave = useRef<number>(0)
  const lastURLSave = useRef<number>(0)
  
  const saveProgress = (): void => {
    if (!book || !chapter) return
    
    const audio = activeAudioRef.current || audioRef.current
    if (!audio) return

    try {
      const positionSeconds = chunkAudios.length > 0 
        ? getTotalTime() 
        : audio.currentTime
      
      const now = Date.now()
      
      // Save to localStorage more frequently (every 2 seconds)
      if (now - lastLocalStorageSave.current >= 2000) {
        localStorage.setItem('audiobook_player_state', JSON.stringify({
          bookId: book.id,
          chapter: chapter.chapter_number,
          position: positionSeconds,
          timestamp: now
        }))
        lastLocalStorageSave.current = now
      }
      
      // Update URL less frequently (every 5 seconds) to avoid too many history entries
      if (now - lastURLSave.current >= 5000) {
        const params = new URLSearchParams()
        params.set('book', book.id)
        params.set('chapter', chapter.chapter_number.toString())
        if (positionSeconds > 0) {
          params.set('position', positionSeconds.toFixed(1))
        }
        window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
        lastURLSave.current = now
      }
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

  // For chunked audio, use total duration if available, otherwise fall back to current chunk duration
  const displayTime = chunkAudios.length > 0
    ? (totalDuration > 0 ? getTotalTime() : (audioRef.current?.currentTime || 0))
    : currentTime

  const displayDuration = chunkAudios.length > 0
    ? (totalDuration > 0 ? totalDuration : (audioRef.current?.duration || 0))
    : duration

  const progressPercent = displayDuration > 0
    ? (displayTime / displayDuration) * 100
    : 0

  // Set volume immediately when audio element is created to prevent fade-in
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = 1.0  // Always use full volume, no fade-in
    }
  }, [])
  
  // Initialize active audio ref on mount
  useEffect(() => {
    if (audioRef.current && !activeAudioRef.current) {
      activeAudioRef.current = audioRef.current
    }
  }, [])
  
  // Don't render if no book
  if (!book) {
    return null
  }

  return (
    <>
      <audio 
        ref={audioRef} 
        preload="metadata"
        crossOrigin="anonymous"
      ></audio>
      <audio 
        ref={nextAudioRef} 
        preload="metadata"
        crossOrigin="anonymous"
        style={{ display: 'none' }}
      ></audio>

      {/* Player Controls Container */}
      <div className={styles.playerControlsContainer}>
            {/* Controls Row */}
            <div className={styles.controls}>
              {/* Primary Playback Controls */}
              <div className={styles.primaryControls}>
                <button className={`${styles.btnPlayPause} ${isPlaying ? styles.btnPlayPausePlaying : ''}`} onClick={togglePlayPause} title="Play/Pause">
                  {isPlaying ? <Pause size={18} /> : <Play size={18} />}
                </button>
              </div>

              {/* Book and Chapter Title - In the middle */}
              {currentBook && (
                <div className={styles.titleSection}>
                  <h2 className={styles.bookTitle}>{currentBook.title}</h2>
                  {currentChapter && <h3 className={styles.chapterTitle}>{currentChapter.title}</h3>}
                </div>
              )}

              {/* Secondary Controls (Speed & Volume) */}
              <div className={styles.secondaryControls}>
            {/* Speed Control - Icon button with dropdown */}
            <div className={styles.speedControlContainer} ref={speedControlRef}>
              <button 
                className={styles.speedButton}
                onClick={() => setShowSpeedMenu(!showSpeedMenu)}
                title={`Playback Speed: ${playbackRate.toFixed(2)}x`}
              >
                <Gauge size={16} />
                <span className={styles.speedButtonValue}>{playbackRate.toFixed(2)}x</span>
              </button>
              {showSpeedMenu && (
                <div className={styles.speedMenu}>
                  {speedPresets.map((speed) => (
                    <button
                      key={speed}
                      className={`${styles.speedOption} ${playbackRate === speed ? styles.speedOptionActive : ''}`}
                      onClick={() => {
                        setPlaybackRate(speed)
                        setShowSpeedMenu(false)
                      }}
                    >
                      {speed.toFixed(2)}x
                    </button>
                  ))}
                  <div className={styles.speedCustom}>
                    <label>Custom:</label>
                    <input
                      type="range"
                      className={styles.speedCustomSlider}
                      min="0.5"
                      max="2.0"
                      step="0.05"
                      value={playbackRate}
                      onChange={(e) => { setPlaybackRate(parseFloat(e.target.value)) }}
                    />
                    <span>{playbackRate.toFixed(2)}x</span>
                  </div>
                </div>
              )}
            </div>

            {/* Volume Control - Icon button with slider */}
            <div 
              className={styles.volumeControlContainer}
              onMouseEnter={() => setShowVolumeSlider(true)}
              onMouseLeave={(e) => {
                // Check if mouse is moving to slider container or its children
                const relatedTarget = e.relatedTarget as HTMLElement
                if (relatedTarget) {
                  const sliderContainer = relatedTarget.closest(`.${styles.volumeSliderContainer}`)
                  const controlContainer = relatedTarget.closest(`.${styles.volumeControlContainer}`)
                  // Don't hide if moving to slider or staying within control container
                  if (sliderContainer || controlContainer) {
                    return
                  }
                }
                setShowVolumeSlider(false)
              }}
            >
              <button 
                className={styles.volumeButton}
                onClick={() => {
                  if (volume > 0) {
                    setVolume(0)
                  } else {
                    setVolume(1.0)
                  }
                }}
                title={`Volume: ${Math.round(volume * 100)}%`}
              >
                {volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </button>
              {showVolumeSlider && (
                <div 
                  className={styles.volumeSliderContainer}
                  onMouseEnter={() => setShowVolumeSlider(true)}
                  onMouseLeave={(e) => {
                    // Check if mouse is moving back to button or control container
                    const relatedTarget = e.relatedTarget as HTMLElement
                    if (relatedTarget) {
                      const controlContainer = relatedTarget.closest(`.${styles.volumeControlContainer}`)
                      if (controlContainer) {
                        return
                      }
                    }
                    setShowVolumeSlider(false)
                  }}
                >
                  <input
                    type="range"
                    className={styles.volumeSlider}
                    min="0"
                    max="100"
                    value={volume * 100}
                    onChange={(e) => { setVolume(parseFloat(e.target.value) / 100) }}
                  />
                  <div className={styles.volumeValue}>{Math.round(volume * 100)}%</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Progress Bar - Below controls with timestamps on ends */}
        <div className={styles.progressContainerBelow}>
          <div className={styles.timeDisplayLeftContainer}>
            <span className={styles.timeDisplayLeft}>{formatTime(displayTime)}</span>
          </div>
          <div className={styles.progressBar}>
            <div className={styles.progressFilled} style={{ width: `${progressPercent}%` }}></div>
            {/* Chunk boundary markers */}
            {chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0 && totalDuration > 0 && (
              <div className={styles.chunkMarkers}>
                {playingChunkMetadata
                  .filter(c => c.audio_start_time !== null && c.audio_start_time !== undefined && c.audio_start_time < totalDuration)
                  .map((chunk) => {
                    const percent = ((chunk.audio_start_time || 0) / totalDuration) * 100
                    return (
                      <div
                        key={chunk.index}
                        className={styles.chunkMarker}
                        style={{ left: `${percent}%` }}
                        title={`Chunk ${chunk.index}`}
                      />
                    )
                  })}
              </div>
            )}
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
          <div className={styles.timeDisplayRightContainer}>
            <span className={styles.timeDisplayRight}>{formatTime(displayDuration)}</span>
            <div className={styles.utilityButtons}>
              {/* Chunk Text Toggle - Small icon button */}
              {chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0 && (
                <button
                  className={styles.btnChunkText}
                  onClick={() => {
                    if (showChunkText) {
                      // Start closing animation
                      setIsClosingChunkText(true)
                      setTimeout(() => {
                        setShowChunkText(false)
                        setIsClosingChunkText(false)
                      }, 300) // Match animation duration
                    } else {
                      setShowChunkText(true)
                      setIsClosingChunkText(false)
                    }
                  }}
                  title="Show current text"
                >
                  <FileText size={12} />
                </button>
              )}
              <button
                className={styles.btnKeyboardHelp}
                onClick={() => { setShowKeyboardHelp(!showKeyboardHelp) }}
                title="Keyboard shortcuts (?)"
              >
                <HelpCircle size={12} />
              </button>
            </div>
          </div>
        </div>

        {/* Keyboard Shortcuts Help */}
        {showKeyboardHelp && (
          <div className={styles.keyboardHelp} ref={keyboardHelpRef}>
            <div className={styles.keyboardHelpHeader}>
              <h4>Keyboard Shortcuts</h4>
              <button
                className={styles.keyboardHelpClose}
                onClick={() => { setShowKeyboardHelp(false) }}
              >
                ×
              </button>
            </div>
            <div className={styles.keyboardHelpContent}>
              <div className={styles.keyboardHelpItem}>
                <kbd>Space</kbd>
                <span>Play/Pause</span>
              </div>
              <div className={styles.keyboardHelpItem}>
                <kbd>←</kbd>
                <span>Seek backward {skipDuration}s</span>
              </div>
              <div className={styles.keyboardHelpItem}>
                <kbd>→</kbd>
                <span>Seek forward {skipDuration}s</span>
              </div>
              <div className={styles.keyboardHelpDivider}></div>
              <div className={`${styles.keyboardHelpItem} ${styles.keyboardHelpItemFullWidth}`}>
                <span>Skip duration:</span>
                <div className={styles.skipDurationControls}>
                  {skipPresets.map((preset) => (
                    <button
                      key={preset}
                      className={`${styles.skipDurationButton} ${skipDuration === preset ? styles.skipDurationButtonActive : ''}`}
                      onClick={() => { setSkipDuration(preset) }}
                      title={`Set skip duration to ${preset}s`}
                    >
                      {preset}s
                    </button>
                  ))}
                </div>
              </div>
              <div className={styles.keyboardHelpItem}>
                <kbd>?</kbd>
                <span>Show/hide shortcuts</span>
              </div>
              <div className={styles.keyboardHelpItem}>
                <kbd>Esc</kbd>
                <span>Close dialogs</span>
              </div>
            </div>
          </div>
        )}

        {/* Chunk Text Panel - Inside player controls */}
        {(showChunkText || isClosingChunkText) && chapter && chapter.is_chunked && playingChunkMetadata && playingChunkMetadata.length > 0 && (
          <div className={`${styles.chunkTextPanelWrapper} ${isClosingChunkText ? styles.chunkTextPanelWrapperClosing : ''}`} ref={chunkTextRef}>
            <div className={styles.chunkTextPanel}>
              <ChunkTextDisplay
                bookId={currentBook?.id}
                chapterNumber={chapter.chapter_number}
                chunkMetadata={playingChunkMetadata}
                displayedChunkIndex={displayedChunkIndex}
              />
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default AudioPlayer

