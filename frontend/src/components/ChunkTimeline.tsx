import { useState, useEffect } from 'react'
import { Music, Loader } from 'lucide-react'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import type { ChunkMetadata } from '../types'
import styles from './ChunkTimeline.module.css'

interface ChunkTimelineProps {
  currentTime: number
  totalDuration: number
  currentChunkIndex: number
}

interface Gap {
  start: number
  end: number
  length: number
}

function ChunkTimeline({ currentTime, totalDuration, currentChunkIndex }: ChunkTimelineProps) {
  const { chunkMetadata, chapterTextLength, generateSingleChunk, generateChunks, currentChapter } = useAudiobookStore()
  const toast = useToastStore()
  const [chunkDurations, setChunkDurations] = useState<Record<number, number>>({})
  const [generatingChunks, setGeneratingChunks] = useState<Set<number>>(new Set())

  // Load audio durations for completed chunks
  useEffect(() => {
    if (!chunkMetadata || chunkMetadata.length === 0) {
      return
    }

    const loadDurations = async (): Promise<void> => {
      const durations: Record<number, number> = {}
      const promises = chunkMetadata
        .filter((c) => c.status === 'completed' && c.path)
        .map(async (chunk) => {
          try {
            let audioUrl = chunk.url || chunk.path || ''
            if (!audioUrl.startsWith('/audio/')) {
              if (audioUrl.includes('/books/')) {
                const match = audioUrl.match(/\/books\/(.+)$/)
                if (match) {
                  audioUrl = `/audio/${match[1]}`
                }
              } else {
                audioUrl = `/audio/${audioUrl}`
              }
            }
            
            const audio = new Audio(audioUrl)
            await new Promise<void>((resolve) => {
              audio.addEventListener('loadedmetadata', () => {
                durations[chunk.index] = audio.duration
                resolve()
              })
              audio.addEventListener('error', () => {
                durations[chunk.index] = 0
                resolve()
              })
              setTimeout(() => {
                durations[chunk.index] = 0
                resolve()
              }, 5000)
            })
          } catch (error) {
            console.warn(`Failed to load duration for chunk ${chunk.index}:`, error)
            durations[chunk.index] = 0
          }
        })
      
      await Promise.all(promises)
      setChunkDurations(durations)
    }

    void loadDurations()
  }, [chunkMetadata])

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

  const formatDuration = (seconds: number): string => {
    if (isNaN(seconds) || seconds < 0) return '0:00'
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  const handleGenerateChunk = async (chunkIndex: number): Promise<void> => {
    if (!currentChapter) return
    
    setGeneratingChunks((prev) => new Set(prev).add(chunkIndex))
    try {
      await generateSingleChunk(currentChapter.title, chunkIndex)
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
    
    if (!window.confirm(`Generate audio for all pending chunks in "${currentChapter.title}"?`)) {
      return
    }
    
    try {
      await generateChunks(currentChapter.title, null)
      toast.success('Started generating pending chunks!')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate chunks')
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
                <tr 
                  key={chunk.index}
                  className={chunk.status === 'completed' ? styles.completedRow : ''}
                >
                  <td className={styles.chunkIndexCell}>{chunk.index}</td>
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
                    {canGenerate && (
                      <button
                        className={styles.btnGenerateChunk}
                        onClick={() => { void handleGenerateChunk(chunk.index) }}
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
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ChunkTimeline

