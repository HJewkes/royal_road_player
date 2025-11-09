import { useState, useEffect, useRef } from 'react'
import { Play, Loader, CheckCircle, Clock, XCircle } from 'lucide-react'
import useToastStore from '../store/useToastStore'
import useAudiobookStore from '../store/useAudiobookStore'
import { useQueueEvents } from '../hooks/useQueueEvents'
import styles from './QueueStatus.module.css'

interface QueueStatus {
  pending: number
  running: number
  failed: number
  is_processing: boolean
}

interface QueueStatusProps {
  bookId?: string
  chapterNumber?: number
}

function QueueStatus({ bookId, chapterNumber }: QueueStatusProps = {}) {
  const toast = useToastStore()
  const { chunkMetadata, loadChunkMetadata } = useAudiobookStore()
  const [status, setStatus] = useState<QueueStatus | null>(null)
  const [processing, setProcessing] = useState(false)
  const fallbackFetchedRef = useRef(false)

  // Load chunk metadata if we have a chapter but no metadata yet
  useEffect(() => {
    if (chapterNumber !== undefined && (!chunkMetadata || chunkMetadata.length === 0)) {
      void loadChunkMetadata(chapterNumber)
    }
  }, [chapterNumber, chunkMetadata, loadChunkMetadata])

  // Use SSE for real-time queue status updates (replaces polling)
  const { status: sseStatus, connected: sseConnected } = useQueueEvents({
    enabled: true, // Always enabled when component is mounted
    onStatusUpdate: (newStatus) => {
      // Convert SSE status format to component format
      setStatus({
        pending: newStatus.pending ?? 0,
        running: newStatus.running ?? 0,
        failed: newStatus.failed ?? 0,
        is_processing: newStatus.is_processing ?? false,
      })
      // Reset fallback flag when SSE provides status
      fallbackFetchedRef.current = false
    },
  })

  // Fallback: fetch status once on mount if SSE not connected (for initial load)
  useEffect(() => {
    if (!sseConnected && !status && !fallbackFetchedRef.current) {
      fallbackFetchedRef.current = true
      const fetchStatus = async (): Promise<void> => {
        try {
          // Build URL with optional filters
          const params = new URLSearchParams()
          if (bookId) params.append('book_id', bookId)
          if (chapterNumber !== undefined) params.append('chapter_number', chapterNumber.toString())
          
          const url = `/api/queue/status${params.toString() ? `?${params.toString()}` : ''}`
          const response = await fetch(url)
          if (!response.ok) {
            throw new Error('Failed to fetch queue status')
          }
          const data = await response.json() as QueueStatus & { total: number; completed: number }
          setStatus({
            pending: data.pending,
            running: data.running,
            failed: data.failed,
            is_processing: data.is_processing,
          })
        } catch (error) {
          console.error('Failed to fetch queue status:', error)
          fallbackFetchedRef.current = false // Allow retry on error
        }
      }
      void fetchStatus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sseConnected]) // Only run when SSE connection state changes

  const startProcessing = async (): Promise<void> => {
    setProcessing(true)
    try {
      const response = await fetch('/api/queue/process', {
        method: 'POST',
      })
      if (!response.ok) {
        throw new Error('Failed to start processing')
      }
      toast.success('Started processing queue')
      // Status will update automatically via SSE
    } catch (error) {
      console.error('Failed to start processing:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to start processing')
    } finally {
      setProcessing(false)
    }
  }

  // Get chunks that need processing (pending or failed)
  const chunksNeedingProcessing = chunkMetadata
    ? chunkMetadata.filter((chunk) => chunk.status === 'pending' || chunk.status === 'failed')
    : []

  // Determine if processing is active
  const isProcessing = status?.is_processing || (status?.running ?? 0) > 0
  const needsProcessing = (status?.pending ?? 0) > 0 || chunksNeedingProcessing.length > 0

  // Hide if no chapter selected or nothing needs processing
  if (chapterNumber === undefined || (!needsProcessing && !isProcessing)) {
    return null
  }

  if (!status) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading...</div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Processing Queue</h3>
        {isProcessing ? (
          <div className={styles.statusBadge}>
            <Loader size={14} className={styles.spinner} />
            Processing
          </div>
        ) : needsProcessing ? (
          <div className={styles.statusBadge}>
            <Clock size={14} />
            Ready
          </div>
        ) : (
          <div className={styles.statusBadge}>
            <CheckCircle size={14} />
            Complete
          </div>
        )}
      </div>

      {needsProcessing && (
        <>
          <div className={styles.summary}>
            {status.pending > 0 && (
              <span className={styles.summaryItem}>
                <Clock size={12} className={styles.summaryIconPending} />
                {status.pending} pending
              </span>
            )}
            {chunksNeedingProcessing.length > status.pending && (
              <span className={styles.summaryItem}>
                <XCircle size={12} className={styles.summaryIconFailed} />
                {chunksNeedingProcessing.length - status.pending} failed
              </span>
            )}
            {status.running > 0 && (
              <span className={styles.summaryItem}>
                <Loader size={12} className={styles.summaryIconRunning} />
                {status.running} running
              </span>
            )}
          </div>

          {chunksNeedingProcessing.length > 0 && (
            <div className={styles.chunkList}>
              <div className={styles.chunkListLabel}>
                Chunks needing processing ({chunksNeedingProcessing.length}):
              </div>
              <div className={styles.chunkIndices}>
                {chunksNeedingProcessing
                  .sort((a, b) => (a.index || 0) - (b.index || 0))
                  .slice(0, 20)
                  .map((chunk) => (
                    <span
                      key={chunk.index}
                      className={`${styles.chunkIndex} ${
                        chunk.status === 'failed' ? styles.chunkIndexFailed : ''
                      }`}
                      title={`Chunk ${chunk.index} (${chunk.status})`}
                    >
                      {chunk.index}
                    </span>
                  ))}
                {chunksNeedingProcessing.length > 20 && (
                  <span className={styles.chunkIndexMore}>
                    +{chunksNeedingProcessing.length - 20} more
                  </span>
                )}
              </div>
            </div>
          )}

          {!isProcessing && (
            <button
              className={styles.startButton}
              onClick={() => { void startProcessing() }}
              disabled={processing}
            >
              {processing ? (
                <>
                  <Loader size={14} className={styles.spinner} />
                  Starting...
                </>
              ) : (
                <>
                  <Play size={14} />
                  Start Processing
                </>
              )}
            </button>
          )}
        </>
      )}

      {isProcessing && status.running > 0 && (
        <div className={styles.processingMessage}>
          Processing {status.running} chunk{status.running !== 1 ? 's' : ''}...
        </div>
      )}
    </div>
  )
}

export default QueueStatus

