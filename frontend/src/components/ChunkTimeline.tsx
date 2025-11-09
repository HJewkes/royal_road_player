import { useState, useEffect, useRef } from 'react'
import useAudiobookStore from '../store/useAudiobookStore'
import { useQueueEvents } from '../hooks/useQueueEvents'
import type { ChunkMetadata } from '../types'
import styles from './ChunkTimeline.module.css'

// Component to handle chunk row with text display
function ChunkRow({ chunk, duration, statusColor, onSeekToChunk, bookId, chapterNumber }: {
  chunk: ChunkMetadata
  duration: number
  statusColor: string
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
  const { chunkMetadata, chapterTextLength, currentChapter, loadChunkMetadata, currentBook } = useAudiobookStore()
  const [chunkDurations, setChunkDurations] = useState<Record<number, number>>({})

  // Don't load durations here - it creates too many Audio objects and hits Chrome's WebMediaPlayer limit
  // Durations will be shown from the AudioPlayer component as chunks are played
  // This component will just show "-" for durations to avoid creating hundreds of Audio objects
  useEffect(() => {
    // Clear any existing durations to avoid stale data
    setChunkDurations({})
  }, [chunkMetadata])

  // Use SSE to detect when jobs complete for current chapter and refresh metadata
  useQueueEvents({
    enabled: !!currentChapter, // Only enabled when chapter is loaded
    onJobCompleted: (job) => {
      // Refresh chunk metadata when a job completes for the current chapter
      if (currentChapter && job.chapter_number === currentChapter.chapter_number) {
        void loadChunkMetadata(currentChapter.chapter_number)
      }
    },
    onStatusUpdate: (status) => {
      // Refresh metadata when processing starts for current chapter
      if (currentChapter && status.is_processing && status.current_job?.chapter_number === currentChapter.chapter_number) {
        void loadChunkMetadata(currentChapter.chapter_number)
      }
    },
  })

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


  return (
    <div className={styles.chunkTimelineContainer}>
      <div className={styles.chunkTimelineHeader}>
        <span className={styles.chunkTimelineLabel}>Text Coverage:</span>
        <span className={styles.chunkTimelineStats}>
          {completed} completed, {pending} pending • {coveragePercent}% coverage
        </span>
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
              
              return (
                <ChunkRow
                  key={chunk.index}
                  chunk={chunk}
                  duration={duration}
                  statusColor={statusColor}
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

