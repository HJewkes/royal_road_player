import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import styles from './ChunkTimeline.module.css'

function ChunkTimeline({ chunkMetadata, chapterTextLength, currentTime, totalDuration, currentChunkIndex }) {
  const [chunkTransitionWarningShown, setChunkTransitionWarningShown] = useState(false)

  useEffect(() => {
    if (!chunkMetadata || chunkMetadata.length === 0 || chapterTextLength === 0) {
      return
    }

    // Find current chunk based on playback position
    const sortedChunks = [...chunkMetadata]
      .filter(c => c.status === 'completed')
      .sort((a, b) => (a.index || 0) - (b.index || 0))

    const currentChunkMeta = sortedChunks[currentChunkIndex]

    if (currentChunkMeta) {
      // Check if approaching chunk boundary (within 5 seconds)
      // This is a simplified check - in a real implementation, you'd calculate
      // the time remaining in the current chunk more accurately
      const warningEl = document.getElementById('chunk-transition-warning')
      if (warningEl && !chunkTransitionWarningShown) {
        // Show warning logic would go here
        // For now, we'll keep it simple
      }
    }
  }, [chunkMetadata, currentChunkIndex, currentTime, chunkTransitionWarningShown])

  if (!chunkMetadata || chunkMetadata.length === 0 || chapterTextLength === 0) {
    return null
  }

  const sortedChunks = [...chunkMetadata].sort((a, b) => (a.index || 0) - (b.index || 0))
  
  // Calculate gaps
  const gaps = []
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
  const completed = sortedChunks.filter(c => c.status === 'completed').length
  const pending = sortedChunks.filter(c => c.status === 'pending').length
  const totalChars = Math.max(...sortedChunks.map(c => c.text_end || 0), chapterTextLength)
  const coveredChars = Math.max(...sortedChunks.filter(c => c.status === 'completed').map(c => c.text_end || 0), 0)
  const coveragePercent = totalChars > 0 ? Math.round((coveredChars / totalChars) * 100) : 0

  const getStatusColor = (status, isFlagged) => {
    if (isFlagged) return '#ff6b6b'
    switch (status) {
      case 'completed': return '#4CAF50'
      case 'running': return '#6b7d8e'
      case 'pending': return '#ff9800'
      case 'failed': return '#f44336'
      default: return '#ccc'
    }
  }

  // Calculate position indicator
  const completedChunks = sortedChunks.filter(c => c.status === 'completed')
  const currentChunkMeta = completedChunks[currentChunkIndex]
  let positionPercent = 0

  if (currentChunkMeta && totalDuration > 0) {
    const chunkStart = currentChunkMeta.text_start || 0
    const chunkEnd = currentChunkMeta.text_end || chunkStart
    const chunkLength = chunkEnd - chunkStart
    
    // Estimate position within chunk based on audio progress
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
        {sortedChunks.map(chunk => {
          const startPercent = ((chunk.text_start || 0) / totalChars) * 100
          const widthPercent = ((chunk.text_length || 0) / totalChars) * 100
          const isFlagged = chunk.flagged || false
          const statusColor = getStatusColor(chunk.status, isFlagged)
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
                opacity: chunk.status === 'completed' && !isFlagged ? 0.8 : 0.6,
                borderRight: '1px solid rgba(0,0,0,0.1)',
                ...(isFlagged ? { border: '2px solid #ff0000' } : {}),
              }}
              title={`Chunk ${chunk.index}: ${chunk.text_length || 0} chars (${chunk.status}${isFlagged ? ', flagged' : ''})`}
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
      <div
        id="chunk-transition-warning"
        className={`${styles.chunkTransitionWarning} ${chunkTransitionWarningShown ? '' : styles.hidden}`}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <AlertTriangle size={14} />
          Approaching chunk boundary
        </span>
      </div>
    </div>
  )
}

export default ChunkTimeline

