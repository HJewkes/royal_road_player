import { useState, useEffect, useRef } from 'react'
import { Loader, CheckCircle, Clock, XCircle, ListTodo } from 'lucide-react'
import styles from './QueueStatusFlyout.module.css'
import { useQueueEvents } from '../hooks/useQueueEvents'

interface QueueStatus {
  pending: number
  running: number
  failed: number
  completed: number
  total: number
  is_processing: boolean
  estimated_seconds_remaining?: number
  avg_time_per_chunk?: number
  avg_time_per_char?: number
}

interface QueueJob {
  book_id: string
  chapter_number: number
  chunk_index: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  error?: string
  created_at?: string
}

interface BookInfo {
  book_id: string
  book_title: string
}

interface ChapterInfo {
  chapter_number: number
  title: string
}

function QueueStatusFlyout() {
  const [isOpen, setIsOpen] = useState(false)
  const [status, setStatus] = useState<QueueStatus | null>(null)
  const [runningJobs, setRunningJobs] = useState<QueueJob[]>([])
  const [pendingJobs, setPendingJobs] = useState<QueueJob[]>([])
  const [failedJobs, setFailedJobs] = useState<QueueJob[]>([])
  const [bookInfo, setBookInfo] = useState<Record<string, BookInfo>>({})
  const [chapterInfo, setChapterInfo] = useState<Record<string, ChapterInfo>>({})
  const [pendingOffset, setPendingOffset] = useState(0)
  const [failedOffset, setFailedOffset] = useState(0)
  const [loadingJobs, setLoadingJobs] = useState(false)
  const [hasMorePending, setHasMorePending] = useState(false)
  const [hasMoreFailed, setHasMoreFailed] = useState(false)
  const flyoutRef = useRef<HTMLDivElement>(null)
  const jobsContainerRef = useRef<HTMLDivElement>(null)
  const fallbackFetchedRef = useRef(false)

  const fetchStatus = async (includeEta = false): Promise<void> => {
    try {
      const url = `/api/queue/status${includeEta ? '?include_eta=true' : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Failed to fetch queue status:', response.status, errorText)
        throw new Error(`Failed to fetch queue status: ${response.status}`)
      }
      const data = await response.json() as QueueStatus
      setStatus(data)
    } catch (error) {
      console.error('Failed to fetch queue status:', error)
    }
  }

  const fetchJobs = async (pendingOffset = 0, failedOffset = 0, limit = 50): Promise<{ 
    running: QueueJob[]
    pending: QueueJob[]
    failed: QueueJob[]
    totals: { running: number; pending: number; failed: number }
  }> => {
    try {
      // Fetch running, pending, and failed jobs separately
      const [runningRes, pendingRes, failedRes] = await Promise.all([
        fetch(`/api/queue/jobs?status=running&limit=10&offset=0&use_db=true`),
        fetch(`/api/queue/jobs?status=pending&limit=${limit}&offset=${pendingOffset}&use_db=true`),
        fetch(`/api/queue/jobs?status=failed&limit=${limit}&offset=${failedOffset}&use_db=true`),
      ])
      
      if (!runningRes.ok || !pendingRes.ok || !failedRes.ok) {
        const runningText = await runningRes.text().catch(() => '')
        const pendingText = await pendingRes.text().catch(() => '')
        const failedText = await failedRes.text().catch(() => '')
        console.error('Failed to fetch queue jobs:', {
          running: { status: runningRes.status, text: runningText },
          pending: { status: pendingRes.status, text: pendingText },
          failed: { status: failedRes.status, text: failedText }
        })
        throw new Error('Failed to fetch queue jobs')
      }
      
      const runningData = await runningRes.json() as { jobs: QueueJob[]; total: number }
      const pendingData = await pendingRes.json() as { jobs: QueueJob[]; total: number }
      const failedData = await failedRes.json() as { jobs: QueueJob[]; total: number }
      
      // Deduplicate jobs by ID (in case a job appears in multiple statuses)
      const seenIds = new Set<string>()
      const dedupeJobs = (jobs: QueueJob[]): QueueJob[] => {
        return jobs.filter(job => {
          const id = `${job.book_id}_${job.chapter_number}_${job.chunk_index}`
          if (seenIds.has(id)) return false
          seenIds.add(id)
          return true
        })
      }
      
      // Process in order: running first (highest priority), then pending, then failed
      const running = dedupeJobs(runningData.jobs)
      const pending = dedupeJobs(pendingData.jobs)
      const failed = dedupeJobs(failedData.jobs)
      
      return {
        running,
        pending,
        failed,
        totals: {
          running: runningData.total,
          pending: pendingData.total,
          failed: failedData.total,
        }
      }
    } catch (error) {
      console.error('Failed to fetch queue jobs:', error)
      return { running: [], pending: [], failed: [], totals: { running: 0, pending: 0, failed: 0 } }
    }
  }

  // Load jobs quickly (without metadata) - for infinite scroll
  const loadJobs = async (pendingOffset = 0, failedOffset = 0, limit = 50): Promise<void> => {
    const result = await fetchJobs(pendingOffset, failedOffset, limit)
    
    // Always update running jobs (replace, don't append)
    setRunningJobs(result.running)
    
    // For infinite scroll, append new jobs to existing ones (avoid duplicates)
    setPendingJobs(prev => {
      const existingIds = new Set(prev.map(j => `${j.book_id}_${j.chapter_number}_${j.chunk_index}`))
      const newJobs = result.pending.filter(j => !existingIds.has(`${j.book_id}_${j.chapter_number}_${j.chunk_index}`))
      return [...prev, ...newJobs]
    })
    
    setFailedJobs(prev => {
      const existingIds = new Set(prev.map(j => `${j.book_id}_${j.chapter_number}_${j.chunk_index}`))
      const newJobs = result.failed.filter(j => !existingIds.has(`${j.book_id}_${j.chapter_number}_${j.chunk_index}`))
      return [...prev, ...newJobs]
    })
    
    // Update pagination state
    setHasMorePending(result.pending.length === limit && pendingOffset + result.pending.length < result.totals.pending)
    setHasMoreFailed(result.failed.length === limit && failedOffset + result.failed.length < result.totals.failed)
  }
  
  // Load metadata in background (non-blocking)
  const loadMetadata = async (
    jobsToLoad: QueueJob[],
    currentBookInfo: Record<string, BookInfo>,
    currentChapterInfo: Record<string, ChapterInfo>
  ): Promise<void> => {
    // Fetch book and chapter info for unique book/chapter combinations
    const uniqueBooks = new Set<string>()
    const uniqueChapters = new Set<string>()
    
    jobsToLoad.forEach(job => {
      // Only fetch if we don't already have this info
      if (!currentBookInfo[job.book_id]) {
        uniqueBooks.add(job.book_id)
      }
      const chapterKey = `${job.book_id}_${job.chapter_number}`
      if (!currentChapterInfo[chapterKey]) {
        uniqueChapters.add(chapterKey)
      }
    })
    
    // Batch fetch book info (limit to 5 at a time, smaller batches for faster initial render)
    if (uniqueBooks.size > 0) {
      const bookArray = Array.from(uniqueBooks).slice(0, 5)
      // Don't await - load in background
      Promise.all(bookArray.map(async (bookId) => {
        try {
          const bookResponse = await fetch(`/api/books/${bookId}?lightweight=true`)
          if (bookResponse.ok) {
            const bookData = await bookResponse.json() as { book_title?: string; title?: string }
            // API returns book_title, but check both for compatibility
            const title = bookData.book_title || bookData.title || bookId
            return { bookId, bookData: { book_id: bookId, book_title: title } }
          }
        } catch (error) {
          console.error(`Failed to fetch book ${bookId}:`, error)
        }
        return null
      })).then(bookResults => {
        const newBookInfo: Record<string, BookInfo> = {}
        bookResults.forEach(result => {
          if (result) {
            newBookInfo[result.bookId] = result.bookData
          }
        })
        setBookInfo(prev => ({ ...prev, ...newBookInfo }))
        
        // Load remaining books in next batch
        if (uniqueBooks.size > 5) {
          const remainingBooks = Array.from(uniqueBooks).slice(5)
          setTimeout(() => {
            void Promise.all(remainingBooks.map(async (bookId) => {
              try {
                const bookResponse = await fetch(`/api/books/${bookId}?lightweight=true`)
                if (bookResponse.ok) {
                  const bookData = await bookResponse.json() as { book_title?: string; title?: string }
                  // API returns book_title, but check both for compatibility
                  const title = bookData.book_title || bookData.title || bookId
                  return { bookId, bookData: { book_id: bookId, book_title: title } }
                }
              } catch (error) {
                console.error(`Failed to fetch book ${bookId}:`, error)
              }
              return null
            })).then(bookResults => {
              const newBookInfo: Record<string, BookInfo> = {}
              bookResults.forEach(result => {
                if (result) {
                  newBookInfo[result.bookId] = result.bookData
                }
              })
              setBookInfo(prev => ({ ...prev, ...newBookInfo }))
            })
          }, 100)
        }
      })
    }
    
    // Batch fetch chapter info (limit to 10 at a time, smaller batches)
    if (uniqueChapters.size > 0) {
      const chapterArray = Array.from(uniqueChapters).slice(0, 10)
      // Don't await - load in background
      Promise.all(chapterArray.map(async (key) => {
        // Key format: "book_58187_4" -> bookId="book_58187", chapterNum="4"
        const lastUnderscore = key.lastIndexOf('_')
        if (lastUnderscore === -1) return null
        const bookId = key.substring(0, lastUnderscore)
        const chapterNum = key.substring(lastUnderscore + 1)
        if (!bookId || !chapterNum) return null
        
        try {
          const chapterResponse = await fetch(`/api/books/${bookId}/chapters/${chapterNum}`)
          if (chapterResponse.ok) {
            const chapterData = await chapterResponse.json() as { title?: string }
            return { key, chapterData: { chapter_number: parseInt(chapterNum, 10), title: chapterData.title || `Chapter ${chapterNum}` } }
          }
        } catch (error) {
          console.error(`Failed to fetch chapter ${bookId}/${chapterNum}:`, error)
        }
        return null
      })).then(chapterResults => {
        const newChapterInfo: Record<string, ChapterInfo> = {}
        chapterResults.forEach(result => {
          if (result) {
            newChapterInfo[result.key] = result.chapterData
          }
        })
        setChapterInfo(prev => ({ ...prev, ...newChapterInfo }))
        
        // Load remaining chapters in next batch
        if (uniqueChapters.size > 10) {
          const remainingChapters = Array.from(uniqueChapters).slice(10)
          setTimeout(() => {
            void Promise.all(remainingChapters.map(async (key) => {
              // Key format: "book_58187_4" -> bookId="book_58187", chapterNum="4"
              const lastUnderscore = key.lastIndexOf('_')
              if (lastUnderscore === -1) return null
              const bookId = key.substring(0, lastUnderscore)
              const chapterNum = key.substring(lastUnderscore + 1)
              if (!bookId || !chapterNum) return null
              
              try {
                const chapterResponse = await fetch(`/api/books/${bookId}/chapters/${chapterNum}`)
                if (chapterResponse.ok) {
                  const chapterData = await chapterResponse.json() as { title?: string }
                  return { key, chapterData: { chapter_number: parseInt(chapterNum, 10), title: chapterData.title || `Chapter ${chapterNum}` } }
                }
              } catch (error) {
                console.error(`Failed to fetch chapter ${bookId}/${chapterNum}:`, error)
              }
              return null
            })).then(chapterResults => {
              const newChapterInfo: Record<string, ChapterInfo> = {}
              chapterResults.forEach(result => {
                if (result) {
                  newChapterInfo[result.key] = result.chapterData
                }
              })
              setChapterInfo(prev => ({ ...prev, ...newChapterInfo }))
            })
          }, 100)
        }
      })
    }
  }


  // Use SSE for real-time queue status updates (replaces polling)
  const { connected: sseConnected } = useQueueEvents({
    enabled: true, // Always enabled when component is mounted
    onStatusUpdate: (newStatus) => {
      // Convert SSE status format to component format
      setStatus({
        pending: newStatus.pending,
        running: newStatus.running,
        failed: newStatus.failed ?? 0,
        completed: newStatus.completed,
        total: (newStatus.pending ?? 0) + (newStatus.running ?? 0) + (newStatus.completed ?? 0) + (newStatus.failed ?? 0),
        is_processing: newStatus.is_processing,
        estimated_seconds_remaining: newStatus.estimated_seconds_remaining,
      })
      // Reset fallback flag when SSE provides status
      fallbackFetchedRef.current = false
    },
    onJobCompleted: () => {
      // Refresh jobs list when a job completes (if flyout is open)
      // Reload from beginning to ensure we have the latest state
      if (isOpen) {
        // Clear existing jobs first
        setRunningJobs([])
        setPendingJobs([])
        setFailedJobs([])
        setPendingOffset(0)
        setFailedOffset(0)
        void fetchJobs(0, 0, 100).then((result) => {
          // Update state
          setRunningJobs(result.running)
          setPendingJobs(result.pending)
          setFailedJobs(result.failed)
          setPendingOffset(100)
          setFailedOffset(100)
          setHasMorePending(result.pending.length === 100 && result.pending.length < result.totals.pending)
          setHasMoreFailed(result.failed.length === 100 && result.failed.length < result.totals.failed)
          
          // Load metadata for refreshed jobs
          const allJobs = [...result.running, ...result.pending, ...result.failed]
          setBookInfo(prevBookInfo => {
            setChapterInfo(prevChapterInfo => {
              void loadMetadata(allJobs, prevBookInfo, prevChapterInfo)
              return prevChapterInfo
            })
            return prevBookInfo
          })
        })
      }
    },
  })

  // Fallback: fetch status once on mount if SSE not connected (for initial load)
  useEffect(() => {
    if (!sseConnected && !status && !fallbackFetchedRef.current) {
      fallbackFetchedRef.current = true
      void fetchStatus(true).catch(() => {
        // Allow retry on error
        fallbackFetchedRef.current = false
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sseConnected]) // Only run when SSE connection state changes

  // Lazy load jobs only when flyout opens
  useEffect(() => {
    if (isOpen && pendingJobs.length === 0 && failedJobs.length === 0) {
      setLoadingJobs(true)
      // Load more initial jobs to ensure scrollability with dense grid
      void fetchJobs(0, 0, 100).then((result) => {
        // Update state
        setRunningJobs(result.running)
        setPendingJobs(result.pending)
        setFailedJobs(result.failed)
        setPendingOffset(100)
        setFailedOffset(100)
        setHasMorePending(result.pending.length === 100 && result.pending.length < result.totals.pending)
        setHasMoreFailed(result.failed.length === 100 && result.failed.length < result.totals.failed)
        setLoadingJobs(false)
        
        // Load metadata in background (non-blocking)
        const allJobs = [...result.running, ...result.pending, ...result.failed]
        setBookInfo(prevBookInfo => {
          setChapterInfo(prevChapterInfo => {
            void loadMetadata(allJobs, prevBookInfo, prevChapterInfo)
            return prevChapterInfo
          })
          return prevBookInfo
        })
      })
    } else if (!isOpen) {
      // Clear jobs when closed to free memory
      setRunningJobs([])
      setPendingJobs([])
      setFailedJobs([])
      setPendingOffset(0)
      setFailedOffset(0)
      setHasMorePending(false)
      setHasMoreFailed(false)
    }
  }, [isOpen])

  // Infinite scroll: load more jobs when scrolling near bottom
  const handleScroll = (): void => {
    if (!jobsContainerRef.current || loadingJobs) return
    
    const container = jobsContainerRef.current
    const scrollBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    
    // Load more when within 200px of bottom (smaller threshold for dense grid)
    if (scrollBottom < 200) {
      const nextPendingOffset = hasMorePending ? pendingJobs.length : pendingOffset
      const nextFailedOffset = hasMoreFailed ? failedJobs.length : failedOffset
      
      if (hasMorePending || hasMoreFailed) {
        setLoadingJobs(true)
        void loadJobs(nextPendingOffset, nextFailedOffset, 100).then(() => {
          setPendingOffset(nextPendingOffset)
          setFailedOffset(nextFailedOffset)
          setLoadingJobs(false)
          // Load metadata in background for new jobs
          const newJobs = [...pendingJobs, ...failedJobs]
          setBookInfo(prevBookInfo => {
            setChapterInfo(prevChapterInfo => {
              void loadMetadata(newJobs, prevBookInfo, prevChapterInfo)
              return prevChapterInfo
            })
            return prevBookInfo
          })
        })
      }
    }
  }

  // Close flyout when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (flyoutRef.current && !flyoutRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const formatDuration = (seconds: number): string => {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0:00'
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    
    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const isProcessing = status?.is_processing || (status?.running ?? 0) > 0
  const hasJobs = (status?.pending ?? 0) > 0 || (status?.failed ?? 0) > 0 || (status?.running ?? 0) > 0

  // Get badge count (pending + failed)
  const badgeCount = (status?.pending ?? 0) + (status?.failed ?? 0)

  return (
    <div className={styles.container} ref={flyoutRef}>
      <button
        className={styles.iconButton}
        onClick={() => { 
          setIsOpen(!isOpen)
        }}
        title="Job Queue Status"
      >
        <ListTodo size={20} />
        {badgeCount > 0 && (
          <span className={styles.badge}>{badgeCount}</span>
        )}
      </button>

      {isOpen && (
        <div className={styles.flyout}>
          <div className={styles.header}>
            <h3 className={styles.title}>Job Queue</h3>
            <div className={styles.headerRight}>
              {isProcessing && status && status.estimated_seconds_remaining !== undefined && status.estimated_seconds_remaining > 0 && (
                <div className={styles.etaInline}>
                  <Clock size={12} className={styles.etaIcon} />
                  <span className={styles.etaValue}>{formatDuration(status.estimated_seconds_remaining)}</span>
                </div>
              )}
              {isProcessing ? (
                <div className={styles.statusBadge}>
                  <Loader size={14} className={styles.spinner} />
                  Processing
                </div>
              ) : hasJobs ? (
                <div className={styles.statusBadge}>
                  <Clock size={14} />
                  Ready
                </div>
              ) : (
                <div className={styles.statusBadge}>
                  <CheckCircle size={14} />
                  Empty
                </div>
              )}
            </div>
          </div>

          {status && (
            <>
              <div className={styles.summary}>
                {status.pending > 0 && (
                  <span className={styles.summaryItem}>
                    <Clock size={12} className={styles.summaryIconPending} />
                    {status.pending} pending
                  </span>
                )}
                {status.failed > 0 && (
                  <span className={styles.summaryItem}>
                    <XCircle size={12} className={styles.summaryIconFailed} />
                    {status.failed} failed
                  </span>
                )}
                {status.running > 0 && (
                  <span className={styles.summaryItem}>
                    <Loader size={12} className={styles.summaryIconRunning} />
                    {status.running} running
                  </span>
                )}
                {status.completed > 0 && (
                  <span className={styles.summaryItem}>
                    <CheckCircle size={12} className={styles.summaryIconCompleted} />
                    {status.completed} completed
                  </span>
                )}
              </div>
            </>
          )}

          {(runningJobs.length > 0 || pendingJobs.length > 0 || failedJobs.length > 0 || loadingJobs) && (
            <div className={styles.jobsList}>
              <div 
                className={styles.jobsGrid}
                ref={jobsContainerRef}
                onScroll={handleScroll}
              >
                {/* Running Jobs Section */}
                {runningJobs.length > 0 && (
                  <>
                    <div className={styles.sectionLabelRunning} key="section-running">
                      Currently Running
                    </div>
                    {runningJobs.map((job) => {
                      const book = bookInfo[job.book_id]
                      const chapterKey = `${job.book_id}_${job.chapter_number}`
                      const chapter = chapterInfo[chapterKey]
                      const bookTitle = book?.book_title || (job.book_id.startsWith('book_') ? job.book_id.replace('book_', '').replace(/_/g, ' ') : job.book_id)
                      const chapterTitle = chapter?.title || `Chapter ${job.chapter_number}`
                      const jobKey = `running-${job.book_id}_${job.chapter_number}_${job.chunk_index}`
                      
                      return (
                        <div
                          key={jobKey}
                          className={`${styles.jobCard} ${styles.jobCardRunning}`}
                          title={`${bookTitle} - ${chapterTitle} - Chunk ${job.chunk_index} (running)${job.error ? `: ${job.error}` : ''}`}
                        >
                          <div className={styles.jobCardChunk}>
                            <Loader size={10} className={styles.jobCardRunningIcon} />
                            {job.chunk_index}
                          </div>
                          <div className={styles.jobCardInfo}>
                            {bookTitle} - {chapterTitle}
                          </div>
                        </div>
                      )
                    })}
                  </>
                )}

                {/* Pending Jobs Section */}
                {pendingJobs.length > 0 && (
                  <>
                    <div className={styles.sectionLabelPending} key="section-pending">
                      Pending ({status?.pending ?? pendingJobs.length})
                    </div>
                    {pendingJobs.flatMap((job, index) => {
                      // Only show book/chapter info when it changes from previous job
                      const prevJob = index > 0 ? pendingJobs[index - 1] : null
                      const showBook = !prevJob || prevJob.book_id !== job.book_id
                      const showChapter = !prevJob || prevJob.book_id !== job.book_id || prevJob.chapter_number !== job.chapter_number
                      
                      const book = bookInfo[job.book_id]
                      const chapterKey = `${job.book_id}_${job.chapter_number}`
                      const chapter = chapterInfo[chapterKey]
                      
                      const bookTitle = book?.book_title || (job.book_id.startsWith('book_') ? job.book_id.replace('book_', '').replace(/_/g, ' ') : job.book_id)
                      const chapterTitle = chapter?.title || `Chapter ${job.chapter_number}`
                      const jobKey = `pending-${job.book_id}_${job.chapter_number}_${job.chunk_index}`
                      
                      const elements = []
                      
                      if (showBook) {
                        elements.push(
                          <div className={styles.sectionLabelBook} key={`section-book-${job.book_id}`}>
                            {bookTitle}
                          </div>
                        )
                      }
                      
                      if (showChapter) {
                        elements.push(
                          <div className={styles.sectionLabelChapter} key={`section-chapter-${job.book_id}-${job.chapter_number}`}>
                            {chapterTitle}
                          </div>
                        )
                      }
                      
                      elements.push(
                        <div
                          key={jobKey}
                          className={styles.jobCard}
                          title={`${bookTitle} - ${chapterTitle} - Chunk ${job.chunk_index} (pending)`}
                        >
                          <div className={styles.jobCardChunk}>
                            {job.chunk_index}
                          </div>
                        </div>
                      )
                      
                      return elements
                    })}
                  </>
                )}

                {/* Failed Jobs Section */}
                {failedJobs.length > 0 && (
                  <>
                    <div className={styles.sectionLabelFailed} key="section-failed">
                      Failed ({status?.failed ?? failedJobs.length})
                    </div>
                    {failedJobs.flatMap((job, index) => {
                      // Only show book/chapter info when it changes from previous job
                      const prevJob = index > 0 ? failedJobs[index - 1] : null
                      const showBook = !prevJob || prevJob.book_id !== job.book_id
                      const showChapter = !prevJob || prevJob.book_id !== job.book_id || prevJob.chapter_number !== job.chapter_number
                      
                      const book = bookInfo[job.book_id]
                      const chapterKey = `${job.book_id}_${job.chapter_number}`
                      const chapter = chapterInfo[chapterKey]
                      
                      const bookTitle = book?.book_title || (job.book_id.startsWith('book_') ? job.book_id.replace('book_', '').replace(/_/g, ' ') : job.book_id)
                      const chapterTitle = chapter?.title || `Chapter ${job.chapter_number}`
                      const jobKey = `failed-${job.book_id}_${job.chapter_number}_${job.chunk_index}`
                      
                      const elements = []
                      
                      if (showBook) {
                        elements.push(
                          <div className={styles.sectionLabelBook} key={`section-book-failed-${job.book_id}`}>
                            {bookTitle}
                          </div>
                        )
                      }
                      
                      if (showChapter) {
                        elements.push(
                          <div className={styles.sectionLabelChapter} key={`section-chapter-failed-${job.book_id}-${job.chapter_number}`}>
                            {chapterTitle}
                          </div>
                        )
                      }
                      
                      elements.push(
                        <div
                          key={jobKey}
                          className={`${styles.jobCard} ${styles.jobCardFailed}`}
                          title={`${bookTitle} - ${chapterTitle} - Chunk ${job.chunk_index} (failed)${job.error ? `: ${job.error}` : ''}`}
                        >
                          <div className={styles.jobCardChunk}>
                            <XCircle size={10} className={styles.jobCardFailedIcon} />
                            {job.chunk_index}
                          </div>
                          {job.error && (
                            <div className={styles.jobCardError} title={job.error}>
                              {job.error.length > 50 ? `${job.error.substring(0, 50)}...` : job.error}
                            </div>
                          )}
                        </div>
                      )
                      
                      return elements
                    })}
                  </>
                )}

                {loadingJobs && (
                  <div className={styles.loadingMore}>Loading more jobs...</div>
                )}
                {!hasMorePending && !hasMoreFailed && (pendingJobs.length > 0 || failedJobs.length > 0) && (
                  <div className={styles.loadedAll}>All jobs loaded</div>
                )}
              </div>
            </div>
          )}

          {!hasJobs && status && (
            <div className={styles.emptyMessage}>
              No jobs in queue. All processing complete.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default QueueStatusFlyout

