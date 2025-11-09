import { useState, useEffect, useRef } from 'react'
import { Music, Loader } from 'lucide-react'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import { confirm } from '../store/useConfirmModalStore'
import type { ChunkMetadata } from '../types'
import styles from './ChunkTimeline.module.css'

// Component to handle chunk row with text display
function ChunkRow({ chunk, duration, statusColor, isGenerating, canGenerate, onGenerate, onSeekToChunk, bookId, chapterNumber }: {
  chunk: ChunkMetadata
  duration: number
  statusColor: string
  isGenerating: boolean
  canGenerate: boolean
  onGenerate: (index: number) => void
  onSeekToChunk?: (chunkIndex: number) => void
  bookId?: string
  chapterNumber?: number
}) {
  const [showText, setShowText] = useState(false)
  const [chunkText, setChunkText] = useState<string | null>(chunk.text || null)
  const [loadingText, setLoadingText] = useState(false)
  
  const handleChunkClick = (): void => {
    if (chunk.status === 'completed' && onSeekToChunk) {
      onSeekToChunk(chunk.index)
    }
  }
  
  const handleToggleText = async () => {
    if (showText) {
      setShowText(false)
      return
    }
    
    // If text already loaded, just show it
    if (chunkText) {
      setShowText(true)
      return
    }
    
    // Load text on-demand
    if (!bookId || !chapterNumber) {
      console.warn('Cannot load chunk text: missing bookId or chapterNumber')
      return
    }
    
    setLoadingText(true)
    setShowText(true)
    
    try {
      const response = await fetch(`/api/books/${bookId}/chapters/${chapterNumber}/chunks/${chunk.index}/text`)
      if (!response.ok) {
        throw new Error(`Failed to load chunk text: ${response.statusText}`)
      }
      const data = await response.json()
      setChunkText(data.text || 'No text available')
    } catch (err) {
      console.error('Failed to load chunk text:', err)
      setChunkText('Failed to load text')
    } finally {
      setLoadingText(false)
    }
  }
  
  return (
    <>
      <tr 
        className={chunk.status === 'completed' ? styles.completedRow : ''}
      >
                  <td 
                    className={`${styles.chunkIndexCell} ${chunk.status === 'completed' && onSeekToChunk ? styles.clickableChunkIndex : ''}`}
                    onClick={handleChunkClick}
                    title={chunk.status === 'completed' && onSeekToChunk ? 'Click to start playback from this chunk' : undefined}
                    style={{ cursor: chunk.status === 'completed' && onSeekToChunk ? 'pointer' : 'default' }}
                  >
                    {chunk.index}
                  </td>
                  <td className={styles.positionCell}>{(chunk.text_start || 0).toLocaleString()}</td>
                  <td className={styles.positionCell}>{(chunk.text_end || 0).toLocaleString()}</td>
                  <td className={styles.lengthCell}>{(chunk.text_length || 0).toLocaleString()}</td>
        <td className={styles.durationCell}>
          {chunk.status === 'completed' ? (
            duration > 0 ? formatDuration(duration) : <span className={styles.loading}>Loading...</span>
          ) : (
            '-'
          )}
        </td>
        <td className={styles.statusCell}>
          <span 
            className={styles.statusBadge}
            style={{ 
              backgroundColor: statusColor,
              opacity: chunk.status === 'completed' ? 0.8 : 0.6
            }}
          >
            {chunk.status || 'pending'}
          </span>
        </td>
        <td className={styles.actionsCell}>
          <button
            className={styles.btnViewText}
            onClick={handleToggleText}
            title={showText ? "Hide text" : "Show text"}
            disabled={loadingText}
          >
            {loadingText ? 'Loading...' : (showText ? 'Hide Text' : 'View Text')}
          </button>
          {canGenerate && (
            <button
              className={styles.btnGenerateChunk}
              onClick={() => { onGenerate(chunk.index) }}
              disabled={isGenerating}
              title={`Generate chunk ${chunk.index}`}
            >
              {isGenerating ? (
                <>
                  <Loader size={12} className={styles.spinner} />
                  Generating...
                </>
              ) : (
                <>
                  <Music size={12} />
                  Generate
                </>
              )}
            </button>
          )}
        </td>
      </tr>
      {showText && chunkText && (
        <tr>
          <td colSpan={7} className={styles.chunkTextCell}>
            <div className={styles.chunkTextContent}>
              <strong>Chunk {chunk.index} Text:</strong>
              <pre className={styles.chunkTextPre}>{chunkText}</pre>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function formatDuration(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '0:00'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

interface ChunkTimelineProps {
  currentTime: number
  totalDuration: number
  currentChunkIndex: number
  onSeekToChunk?: (chunkIndex: number) => void  // Callback to seek to a specific chunk
}

interface Gap {
  start: number
  end: number
  length: number
}

function ChunkTimeline({ currentTime, totalDuration, currentChunkIndex, onSeekToChunk }: ChunkTimelineProps) {
  const { chunkMetadata, chapterTextLength, generateSingleChunk, generateChunks, currentChapter, loadChunkMetadata, currentBook } = useAudiobookStore()
  const toast = useToastStore()
  const [chunkDurations, setChunkDurations] = useState<Record<number, number>>({})
  const [generatingChunks, setGeneratingChunks] = useState<Set<number>>(new Set())
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Don't load durations here - it creates too many Audio objects and hits Chrome's WebMediaPlayer limit
  // Durations will be shown from the AudioPlayer component as chunks are played
  // This component will just show "-" for durations to avoid creating hundreds of Audio objects
  useEffect(() => {
    // Clear any existing durations to avoid stale data
    setChunkDurations({})
  }, [chunkMetadata])

  // Poll for queue status and refresh chunk metadata when processing
  useEffect(() => {
    if (!currentChapter) return

    let isProcessing = false

    const checkQueueAndRefresh = async (): Promise<void> => {
      try {
        const response = await fetch('/api/queue/status')
        if (response.ok) {
          const queueStatus = await response.json() as { 
            is_processing: boolean
            running: number
            current_job: { chapter_number: number } | null 
          }
          
          const wasProcessing = isProcessing
          isProcessing = queueStatus.is_processing || queueStatus.running > 0
          
          // If processing and current chapter matches, refresh chunk metadata
          if (isProcessing && queueStatus.current_job?.chapter_number === currentChapter.chapter_number) {
            await loadChunkMetadata(currentChapter.chapter_number)
          }
          
          // Start/stop polling based on processing state
          if (isProcessing && !wasProcessing) {
            // Started processing - start polling
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current)
            }
            pollingIntervalRef.current = setInterval(() => {
              void checkQueueAndRefresh()
            }, 5000) // Poll every 5 seconds when processing (was 2 seconds)
          } else if (!isProcessing && wasProcessing) {
            // Stopped processing - stop polling
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current)
              pollingIntervalRef.current = null
            }
          }
        }
      } catch (error) {
        // Silently fail - queue might not be active
        console.debug('Queue status check failed:', error)
      }
    }

    // Check immediately
    void checkQueueAndRefresh()

    // Also check periodically (every 5 seconds) to detect when processing starts
    const checkInterval = setInterval(() => {
      void checkQueueAndRefresh()
    }, 5000)

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      clearInterval(checkInterval)
    }
  }, [currentChapter, loadChunkMetadata])

  if (!chunkMetadata || chunkMetadata.length === 0 || chapterTextLength === 0) {
    return null
  }

  const sortedChunks = [...chunkMetadata].sort((a, b) => (a.index || 0) - (b.index || 0))
  
  // Calculate gaps
  const gaps: Gap[] = []
  let lastEnd = 0
  for (const chunk of sortedChunks) {
    const chunkStart = chunk.text_start || 0
    if (chunkStart > lastEnd) {
      gaps.push({ start: lastEnd, end: chunkStart, length: chunkStart - lastEnd })
    }
    lastEnd = Math.max(lastEnd, chunk.text_end || 0)
  }
  if (lastEnd < chapterTextLength) {
    gaps.push({ start: lastEnd, end: chapterTextLength, length: chapterTextLength - lastEnd })
  }

  // Calculate stats
  const completed = sortedChunks.filter((c) => c.status === 'completed').length
  const pending = sortedChunks.filter((c) => c.status === 'pending').length
  
  const totalChars = chapterTextLength > 0 ? chapterTextLength : Math.max(...sortedChunks.map((c) => c.text_end || 0), 0)
  const coveredChars = sortedChunks
    .filter((c) => c.status === 'completed')
    .reduce((sum, chunk) => sum + (chunk.text_length || 0), 0)
  
  const coveragePercent = totalChars > 0 ? Math.round((coveredChars / totalChars) * 100) : 0

  const getStatusColor = (status: ChunkMetadata['status']): string => {
    switch (status) {
      case 'completed': return '#4CAF50'
      case 'running': return '#6b7d8e'
      case 'pending': return '#ff9800'
      case 'failed': return '#f44336'
      default: return '#ccc'
    }
  }

  // Calculate position indicator
  const completedChunks = sortedChunks.filter((c) => c.status === 'completed')
  const currentChunkMeta = completedChunks[currentChunkIndex]
  let positionPercent = 0

  if (currentChunkMeta && totalDuration > 0) {
    const chunkStart = currentChunkMeta.text_start || 0
    const chunkEnd = currentChunkMeta.text_end || chunkStart
    const chunkLength = chunkEnd - chunkStart
    
    const chunkProgress = currentTime / totalDuration
    const estimatedTextPos = chunkStart + (chunkLength * chunkProgress)
    positionPercent = (estimatedTextPos / totalChars) * 100
  }

  const handleGenerateChunk = async (chunkIndex: number): Promise<void> => {
    if (!currentChapter) return
    
    setGeneratingChunks((prev) => new Set(prev).add(chunkIndex))
    try {
      await generateSingleChunk(currentChapter.chapter_number, chunkIndex)
      toast.success(`Chunk ${chunkIndex} generated successfully!`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate chunk')
    } finally {
      setGeneratingChunks((prev) => {
        const next = new Set(prev)
        next.delete(chunkIndex)
        return next
      })
    }
  }

  const handleGeneratePending = async (): Promise<void> => {
    if (!currentChapter) return
    
    const confirmed = await confirm(`Queue all pending chunks in "${currentChapter.title}" for processing?`)
    if (!confirmed) {
      return
    }
    
    try {
      const result = await generateChunks(currentChapter.chapter_number, null)
      const totalChunks = result.generated + result.skipped + result.failed
      if (totalChunks > 0) {
        toast.success(`Queued ${result.generated} chunks. Click "Start Processing" in the queue to begin.`)
        // Reload chunk metadata to refresh status
        await loadChunkMetadata(currentChapter.chapter_number)
      } else {
        toast.warning('No chunks to queue. All chunks may already be completed or queued.')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to queue chunks')
    }
  }

  const pendingChunks = sortedChunks.filter((c) => c.status === 'pending' || c.status === 'failed')

  return (
    <div className={styles.chunkTimelineContainer}>
      <div className={styles.chunkTimelineHeader}>
        <span className={styles.chunkTimelineLabel}>Text Coverage:</span>
        <span className={styles.chunkTimelineStats}>
          {completed} completed, {pending} pending • {coveragePercent}% coverage
        </span>
        {pendingChunks.length > 0 && (
          <button
            className={styles.btnGeneratePending}
            onClick={() => { void handleGeneratePending() }}
            title="Generate all pending chunks"
          >
            <Music size={14} />
            Generate Pending ({pendingChunks.length})
          </button>
        )}
      </div>
      <div className={styles.chunkTimelineBar}>
        {sortedChunks.map((chunk) => {
          const startPercent = ((chunk.text_start || 0) / totalChars) * 100
          const widthPercent = ((chunk.text_length || 0) / totalChars) * 100
          const statusColor = getStatusColor(chunk.status)
          const isCurrent = completedChunks[currentChunkIndex]?.index === chunk.index
          
          return (
            <div
              key={chunk.index}
              className={`${styles.chunkTimelineSegment} ${isCurrent ? styles.currentChunk : ''}`}
              data-chunk-index={chunk.index}
              style={{
                position: 'absolute',
                left: `${startPercent}%`,
                width: `${widthPercent}%`,
                height: '100%',
                background: statusColor,
                opacity: chunk.status === 'completed' ? 0.8 : 0.6,
                borderRight: '1px solid rgba(0,0,0,0.1)',
              }}
              title={`Chunk ${chunk.index}: ${chunk.text_length || 0} chars (${chunk.status})`}
            />
          )
        })}
        {gaps.map((gap, idx) => {
          const startPercent = (gap.start / totalChars) * 100
          const widthPercent = (gap.length / totalChars) * 100
          return (
            <div
              key={`gap-${idx}`}
              className={styles.chunkTimelineGap}
              style={{
                position: 'absolute',
                left: `${startPercent}%`,
                width: `${widthPercent}%`,
                height: '100%',
                background: 'repeating-linear-gradient(45deg, #ff9800, #ff9800 5px, #ffb74d 5px, #ffb74d 10px)',
                opacity: 0.7,
                border: '1px dashed #ff6b00',
              }}
              title={`Gap: ${gap.length.toLocaleString()} chars`}
            />
          )
        })}
        {positionPercent > 0 && (
          <div
            className={styles.chunkTimelinePositionIndicator}
            style={{ left: `${positionPercent}%` }}
          />
        )}
      </div>

      {/* Chunk Details Table */}
      <div className={styles.chunkTableContainer}>
        <table className={styles.chunkTable}>
          <thead>
            <tr>
              <th>Chunk</th>
              <th>Text Start</th>
              <th>Text End</th>
              <th>Text Length</th>
              <th>Audio Duration</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedChunks.map((chunk) => {
              const duration = chunkDurations[chunk.index] || 0
              const statusColor = getStatusColor(chunk.status)
              const isGenerating = generatingChunks.has(chunk.index)
              const canGenerate = chunk.status !== 'completed'
              
              return (
                <ChunkRow
                  key={chunk.index}
                  chunk={chunk}
                  duration={duration}
                  statusColor={statusColor}
                  isGenerating={isGenerating}
                  canGenerate={canGenerate}
                  onGenerate={handleGenerateChunk}
                  onSeekToChunk={onSeekToChunk}
                  bookId={currentBook?.id}
                  chapterNumber={currentChapter?.chapter_number}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ChunkTimeline

