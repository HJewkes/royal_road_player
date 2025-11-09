/**
 * React hook for subscribing to queue status updates via Server-Sent Events (SSE).
 * 
 * Replaces polling with real-time push updates from the server.
 * Automatically reconnects on disconnect and handles errors gracefully.
 */

import { useEffect, useRef, useState, useCallback } from 'react'

export interface QueueStatus {
  is_processing: boolean
  pending: number
  running: number
  completed: number
  failed: number
  estimated_seconds_remaining?: number
  current_job?: {
    book_id: string
    chapter_number: number
    chunk_index: number
  }
}

export interface QueueJob {
  book_id: string
  chapter_number: number
  chunk_index: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  speaker?: string
  speed?: number
  error?: string
  created_at?: string
}

interface UseQueueEventsOptions {
  /** Whether to enable the SSE connection (default: true) */
  enabled?: boolean
  /** Callback when status updates */
  onStatusUpdate?: (status: QueueStatus) => void
  /** Callback when a job starts */
  onJobStarted?: (job: QueueJob) => void
  /** Callback when a job completes */
  onJobCompleted?: (job: QueueJob) => void
  /** Callback when a job fails */
  onJobFailed?: (job: QueueJob) => void
}

export function useQueueEvents(options: UseQueueEventsOptions = {}) {
  const {
    enabled = true,
    onStatusUpdate,
    onJobStarted,
    onJobCompleted,
    onJobFailed,
  } = options

  const [status, setStatus] = useState<QueueStatus | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef(0)
  
  // Store callbacks in refs to avoid recreating connect function
  const callbacksRef = useRef({ onStatusUpdate, onJobStarted, onJobCompleted, onJobFailed })
  
  // Update refs when callbacks change (without triggering reconnect)
  useEffect(() => {
    callbacksRef.current = { onStatusUpdate, onJobStarted, onJobCompleted, onJobFailed }
  }, [onStatusUpdate, onJobStarted, onJobCompleted, onJobFailed])

  const connect = useCallback(() => {
    if (!enabled) return

    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    try {
      const eventSource = new EventSource('/api/queue/events')
      eventSourceRef.current = eventSource
      setError(null)

      // Handle status updates
      eventSource.addEventListener('status', (event) => {
        try {
          const data = JSON.parse(event.data) as QueueStatus
          setStatus(data)
          callbacksRef.current.onStatusUpdate?.(data)
          reconnectAttemptsRef.current = 0 // Reset on successful message
        } catch (e) {
          console.error('Failed to parse status event:', e)
        }
      })

      // Handle job started
      eventSource.addEventListener('job_started', (event) => {
        try {
          const data = JSON.parse(event.data) as QueueJob
          callbacksRef.current.onJobStarted?.(data)
        } catch (e) {
          console.error('Failed to parse job_started event:', e)
        }
      })

      // Handle job completed
      eventSource.addEventListener('job_completed', (event) => {
        try {
          const data = JSON.parse(event.data) as QueueJob
          callbacksRef.current.onJobCompleted?.(data)
        } catch (e) {
          console.error('Failed to parse job_completed event:', e)
        }
      })

      // Handle job failed
      eventSource.addEventListener('job_failed', (event) => {
        try {
          const data = JSON.parse(event.data) as QueueJob
          callbacksRef.current.onJobFailed?.(data)
        } catch (e) {
          console.error('Failed to parse job_failed event:', e)
        }
      })

      // Handle connection open
      eventSource.onopen = () => {
        setConnected(true)
        reconnectAttemptsRef.current = 0
        console.log('SSE connection opened')
      }

      // Handle connection errors
      eventSource.onerror = (e) => {
        console.error('SSE connection error:', e)
        setConnected(false)
        
        // Close and attempt reconnect with exponential backoff
        if (eventSource.readyState === EventSource.CLOSED) {
          eventSource.close()
          eventSourceRef.current = null
          
          // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000)
          reconnectAttemptsRef.current++
          
          reconnectTimeoutRef.current = window.setTimeout(() => {
            console.log(`Reconnecting SSE (attempt ${reconnectAttemptsRef.current})...`)
            connect()
          }, delay)
        }
      }
    } catch (e) {
      console.error('Failed to create SSE connection:', e)
      setError(e instanceof Error ? e : new Error('Failed to create SSE connection'))
      setConnected(false)
    }
  }, [enabled]) // Only depend on enabled, not callbacks

  // Connect/disconnect based on enabled state
  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      setConnected(false)
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [enabled, connect])

  return {
    status,
    connected,
    error,
    reconnect: connect,
  }
}

