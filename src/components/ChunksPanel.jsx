import { useState, useEffect } from 'react'
import { X, Music, Check, AlertTriangle } from 'lucide-react'
import styles from './ChunksPanel.module.css'

function ChunksPanel({ book, chapterTitle, onClose }) {
  const [chunksData, setChunksData] = useState(null)
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadChunksAndJobs()
    const interval = setInterval(loadChunksAndJobs, 3000) // Poll every 3 seconds
    return () => clearInterval(interval)
  }, [book, chapterTitle])

  const loadChunksAndJobs = async () => {
    if (!book || !chapterTitle) return

    try {
      const [chunksResponse, jobsResponse] = await Promise.all([
        fetch(`/api/books/${book.id}/chapters/${encodeURIComponent(chapterTitle)}/chunks`),
        fetch(`/api/jobs?book_id=${book.id}`)
      ])
      
      const chunksData = await chunksResponse.json()
      const jobsData = await jobsResponse.json()
      
      setChunksData(chunksData)
      
      // Filter jobs relevant to this chapter
      const chapterJobs = (jobsData.jobs || []).filter(job => {
        return (job.type === 'generate_chapter_audio' || job.type === 'generate_chunk_audio') &&
               job.chapter_title === chapterTitle
      })
      setJobs(chapterJobs)
    } catch (error) {
      console.error('Failed to load chunks/jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleChunkFlag = async (chunkIndex) => {
    try {
      await fetch(`/api/books/${book.id}/chapters/${encodeURIComponent(chapterTitle)}/chunks/${chunkIndex}/flag`, {
        method: 'POST',
      })
      await loadChunksAndJobs()
    } catch (error) {
      console.error('Failed to flag chunk:', error)
      alert('Failed to flag chunk')
    }
  }

  const generateChunk = async (chunkIndex) => {
    try {
      const response = await fetch('/api/jobs/generate-chunk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_id: book.id,
          chapter_title: chapterTitle,
          chunk_index: chunkIndex,
        }),
      })
      const data = await response.json()
      
      alert(`Chunk ${chunkIndex} generation queued! Job ID: ${data.job_id}`)
      await loadChunksAndJobs()
    } catch (error) {
      console.error('Failed to generate chunk:', error)
      alert('Failed to generate chunk')
    }
  }

  const generateRemainingChunks = async () => {
    try {
      const response = await fetch('/api/jobs/generate-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_id: book.id,
          chapter_title: chapterTitle,
        }),
      })
      const data = await response.json()
      
      alert(`Remaining chunks generation queued! Job ID: ${data.job_id}`)
      await loadChunksAndJobs()
    } catch (error) {
      console.error('Failed to generate remaining chunks:', error)
      alert('Failed to generate remaining chunks')
    }
  }

  const escapeHtml = (text) => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  if (loading || !chunksData) {
    return (
      <div className={styles.panel}>
        <div className={styles.panelHeader}>
          <h3>Chapter Chunks</h3>
          <button className={styles.btnClose} onClick={onClose}>
          <X size={20} />
        </button>
        </div>
        <div className={styles.chunksList}>
          <p className="loading">Loading chunks...</p>
        </div>
      </div>
    )
  }

  const chunks = chunksData.chunks || []
  const textLength = chunksData.text_length || 1
  const totalChars = Math.max(...chunks.map(c => c.text_end || 0), textLength)

  // Calculate gaps
  const sortedChunks = [...chunks].sort((a, b) => (a.text_start || 0) - (b.text_start || 0))
  const gaps = []
  let lastEnd = 0
  for (const chunk of sortedChunks) {
    const chunkStart = chunk.text_start || 0
    if (chunkStart > lastEnd) {
      gaps.push({ start: lastEnd, end: chunkStart, length: chunkStart - lastEnd })
    }
    lastEnd = Math.max(lastEnd, chunk.text_end || 0)
  }
  if (lastEnd < totalChars) {
    gaps.push({ start: lastEnd, end: totalChars, length: totalChars - lastEnd })
  }

  const runningJobs = jobs.filter(j => j.status === 'running')
  const pendingJobs = jobs.filter(j => j.status === 'pending')
  const failedJobs = jobs.filter(j => j.status === 'failed')

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

  const remainingChunks = chunks.filter(c => c.status !== 'completed' || c.flagged).length + gaps.length

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h3>Chapter Chunks</h3>
        <button className={styles.btnClose} onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      <div className={styles.chunksList}>
        <div style={{ marginBottom: '20px' }}>
          <p style={{ marginBottom: '10px', color: '#666' }}>
            Chapter: <strong>{escapeHtml(chunksData.chapter_title)}</strong>
            <span style={{ marginLeft: '15px', fontSize: '0.9em' }}>
              Total text: {totalChars.toLocaleString()} characters
            </span>
          </p>

          {/* Status Summary */}
          <div style={{ display: 'flex', gap: '15px', marginBottom: '15px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <div style={{ width: '12px', height: '12px', background: '#4CAF50', borderRadius: '2px' }}></div>
              <span style={{ fontSize: '0.9em' }}>
                Completed: {chunks.filter(c => c.status === 'completed' && !c.flagged).length}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <div style={{ width: '12px', height: '12px', background: '#6b7d8e', borderRadius: '2px' }}></div>
              <span style={{ fontSize: '0.9em' }}>
                Running: {chunks.filter(c => c.status === 'running').length}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <div style={{ width: '12px', height: '12px', background: '#ff9800', borderRadius: '2px' }}></div>
              <span style={{ fontSize: '0.9em' }}>
                Pending: {chunks.filter(c => c.status === 'pending' || !c.status).length}
              </span>
            </div>
            {gaps.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', background: 'repeating-linear-gradient(45deg, #ff9800, #ff9800 5px, #ffb74d 5px, #ffb74d 10px)', borderRadius: '2px' }}></div>
                <span style={{ fontSize: '0.9em' }}>Gaps: {gaps.length}</span>
              </div>
            )}
            {chunks.filter(c => c.flagged).length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', background: '#ff6b6b', borderRadius: '2px' }}></div>
                <span style={{ fontSize: '0.9em' }}>Flagged: {chunks.filter(c => c.flagged).length}</span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          {remainingChunks > 0 && (
            <div style={{ marginBottom: '15px' }}>
              <button
                className={styles.btnGenerate}
                onClick={generateRemainingChunks}
              >
                <Music size={16} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
                Generate Remaining Chunks ({remainingChunks})
              </button>
            </div>
          )}
        </div>

        {/* Chunk List */}
        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          {chunks.length === 0 ? (
            <p>No chunks found for this chapter. Click "Generate Remaining Chunks" to start.</p>
          ) : (
            chunks.map(chunk => {
              const isFlagged = chunk.flagged || false
              const statusColor = getStatusColor(chunk.status, isFlagged)
              const percentCoverage = totalChars > 0 ? ((chunk.text_length || 0) / totalChars * 100).toFixed(1) : 0
              const canGenerate = chunk.status !== 'completed' || isFlagged

              return (
                <div key={chunk.index} className={`${styles.chunkItem} ${isFlagged ? styles.flagged : ''}`} style={{ marginBottom: '10px' }}>
                  <div className={styles.chunkInfo} style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '5px' }}>
                      <div className={styles.chunkName}>Chunk {chunk.index}</div>
                      <div style={{
                        width: '8px',
                        height: '8px',
                        background: statusColor,
                        borderRadius: '50%',
                      }}></div>
                      <span style={{ fontSize: '0.85em', color: 'var(--color-text-tertiary)', textTransform: 'capitalize' }}>
                        {chunk.status || 'pending'}
                      </span>
                      {isFlagged && (
                        <span style={{ fontSize: '0.85em', color: '#ff6b6b', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <AlertTriangle size={12} />
                          Flagged
                        </span>
                      )}
                    </div>
                    <div className={styles.chunkMeta}>
                      {chunk.filename ? escapeHtml(chunk.filename) : `Chunk ${chunk.index} (not generated)`}
                      <span style={{ marginLeft: '10px', color: 'var(--color-text-tertiary)' }}>
                        {chunk.text_length || 0} chars ({percentCoverage}% of text)
                      </span>
                      {chunk.generation_time_seconds && (
                        <span style={{ marginLeft: '10px', color: 'var(--color-text-tertiary)' }}>
                          Generated in {chunk.generation_time_seconds.toFixed(1)}s
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    {canGenerate && (
                      <button
                        className={styles.btnGenerateChunk}
                        onClick={() => generateChunk(chunk.index)}
                      >
                        <Music size={14} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
                        Generate
                      </button>
                    )}
                    <button
                      className={`${styles.btnFlag} ${isFlagged ? styles.flagged : ''}`}
                      onClick={() => toggleChunkFlag(chunk.index)}
                    >
                      {isFlagged ? (
                        <>
                          <Check size={14} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }} />
                          Flagged
                        </>
                      ) : (
                        'Flag'
                      )}
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

export default ChunksPanel

