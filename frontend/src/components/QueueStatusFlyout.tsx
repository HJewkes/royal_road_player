import { useState, useEffect, useRef } from 'react'
import { Loader, CheckCircle, Clock, XCircle, ListTodo } from 'lucide-react'
import styles from './QueueStatusFlyout.module.css'

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
  const [jobs, setJobs] = useState<QueueJob[]>([])
  const [bookInfo, setBookInfo] = useState<Record<string, BookInfo>>({})
  const [chapterInfo, setChapterInfo] = useState<Record<string, ChapterInfo>>({})
  const [jobsTotal, setJobsTotal] = useState(0)
  const [jobsOffset, setJobsOffset] = useState(0)
  const [loadingJobs, setLoadingJobs] = useState(false)
  const [hasMoreJobs, setHasMoreJobs] = useState(false)
  const flyoutRef = useRef<HTMLDivElement>(null)
  const jobsContainerRef = useRef<HTMLDivElement>(null)

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

  const fetchJobs = async (offset = 0, limit = 50): Promise<{ jobs: QueueJob[]; total: number }> => {
    try {
      // Use DB-based endpoint with proper pagination - same query as queue processor uses
      // Fetch pending jobs (in same order processor will process them) and failed jobs separately
      const [pendingRes, failedRes] = await Promise.all([
        fetch(`/api/queue/jobs?status=pending&limit=${limit}&offset=${offset}&use_db=true`),
        fetch(`/api/queue/jobs?status=failed&limit=${limit}&offset=${offset}&use_db=true`),
      ])
      
      if (!pendingRes.ok || !failedRes.ok) {
        const pendingText = await pendingRes.text().catch(() => '')
        const failedText = await failedRes.text().catch(() => '')
        console.error('Failed to fetch queue jobs:', {
          pending: { status: pendingRes.status, text: pendingText },
          failed: { status: failedRes.status, text: failedText }
        })
        throw new Error('Failed to fetch queue jobs')
      }
      
      const pendingData = await pendingRes.json() as { jobs: QueueJob[]; total: number }
      const failedData = await failedRes.json() as { jobs: QueueJob[]; total: number }
      
      // Combine jobs (pending first, then failed), already sorted by DB query
      const combinedJobs = [
        ...pendingData.jobs.map(j => ({ ...j, _sort: 0 })), // pending gets sort priority
        ...failedData.jobs.map(j => ({ ...j, _sort: 1 }))   // failed comes after
      ].sort((a, b) => {
        // Sort by status priority (pending first), then by book/chapter/index
        if (a._sort !== b._sort) return a._sort - b._sort
        if (a.book_id !== b.book_id) return a.book_id.localeCompare(b.book_id)
        if (a.chapter_number !== b.chapter_number) return a.chapter_number - b.chapter_number
        return a.chunk_index - b.chunk_index
      }).map(({ _sort, ...job }) => job) as QueueJob[] // Remove temporary sort field
      
      return { jobs: combinedJobs, total: pendingData.total + failedData.total }
    } catch (error) {
      console.error('Failed to fetch queue jobs:', error)
      return { jobs: [], total: 0 }
    }
  }

  // Load jobs quickly (without metadata) - for infinite scroll
  const loadJobs = async (offset = 0, limit = 50): Promise<{ jobs: QueueJob[]; total: number }> => {
    const result = await fetchJobs(offset, limit)
    setJobsTotal(result.total)
    
    // For infinite scroll, append new jobs to existing ones (avoid duplicates)
    setJobs(prev => {
      const existingIds = new Set(prev.map(j => `${j.book_id}_${j.chapter_number}_${j.chunk_index}`))
      const newJobs = result.jobs.filter(j => !existingIds.has(`${j.book_id}_${j.chapter_number}_${j.chunk_index}`))
      return [...prev, ...newJobs]
    })
    
    return result
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


  // Initial status fetch and polling (with ETA now that it's fast)
  useEffect(() => {
    // Fetch immediately on mount
    void fetchStatus(true) // Include ETA (now fast with SQL)
    
    // Poll less frequently to reduce backend load:
    // - Every 5 seconds if processing
    // - Every 15 seconds if idle (was 5 seconds)
    const isActive = status?.is_processing || (status?.running ?? 0) > 0
    const interval = setInterval(() => {
      void fetchStatus(true) // Include ETA (now fast with SQL)
    }, isActive ? 5000 : 15000)

    return () => {
      clearInterval(interval)
    }
  }, []) // Run once on mount, then use status for interval timing
  
  // Update polling interval when status changes
  useEffect(() => {
    const isActive = status?.is_processing || (status?.running ?? 0) > 0
    // This effect just ensures we're using the right interval timing
    // The actual polling is handled by the main effect above
  }, [status?.is_processing, status?.running])

  // Lazy load jobs only when flyout opens
  useEffect(() => {
    if (isOpen && jobs.length === 0) {
      setLoadingJobs(true)
      // Load more initial jobs to ensure scrollability with dense grid
      void loadJobs(0, 100).then(({ jobs: jobsData, total }) => {
        setJobsOffset(100)
        setHasMoreJobs(jobsData.length === 100 && 100 < total)
        setLoadingJobs(false)
        // Load metadata in background (non-blocking) - use current state
        setBookInfo(prevBookInfo => {
          setChapterInfo(prevChapterInfo => {
            void loadMetadata(jobsData, prevBookInfo, prevChapterInfo)
            return prevChapterInfo
          })
          return prevBookInfo
        })
      })
    } else if (!isOpen) {
      // Clear jobs when closed to free memory
      setJobs([])
      setJobsOffset(0)
      setJobsTotal(0)
      setHasMoreJobs(false)
    }
  }, [isOpen])

  // Infinite scroll: load more jobs when scrolling near bottom
  const handleScroll = (): void => {
    if (!jobsContainerRef.current || loadingJobs || !hasMoreJobs) return
    
    const container = jobsContainerRef.current
    const scrollBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    
    // Load more when within 200px of bottom (smaller threshold for dense grid)
    if (scrollBottom < 200) {
      const nextOffset = jobs.length // Use current jobs length as offset
      setLoadingJobs(true)
      void loadJobs(nextOffset, 100).then(({ jobs: jobsData, total }) => {
        setJobsOffset(nextOffset)
        setJobsTotal(total)
        // Check if we have more jobs to load
        setHasMoreJobs(jobsData.length > 0 && jobs.length + jobsData.length < total)
        setLoadingJobs(false)
        // Load metadata in background for new jobs
        setBookInfo(prevBookInfo => {
          setChapterInfo(prevChapterInfo => {
            void loadMetadata(jobsData, prevBookInfo, prevChapterInfo)
            return prevChapterInfo
          })
          return prevBookInfo
        })
      })
    }
  }

  // Update hasMoreJobs when jobs change - check if we've loaded all available jobs
  useEffect(() => {
    if (jobsTotal > 0) {
      setHasMoreJobs(jobs.length < jobsTotal)
    }
  }, [jobs.length, jobsTotal])

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

  const pendingJobs = jobs.filter(j => j.status === 'pending' || j.status === 'failed')
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

          {(pendingJobs.length > 0 || loadingJobs) && (
            <div className={styles.jobsList}>
              <div 
                className={styles.jobsGrid}
                ref={jobsContainerRef}
                onScroll={handleScroll}
              >
                {pendingJobs.flatMap((job, index) => {
                  // Only show book/chapter info when it changes from previous job
                  const prevJob = index > 0 ? pendingJobs[index - 1] : null
                  const showBook = !prevJob || prevJob.book_id !== job.book_id
                  const showChapter = !prevJob || prevJob.book_id !== job.book_id || prevJob.chapter_number !== job.chapter_number
                  
                  const book = bookInfo[job.book_id]
                  const chapterKey = `${job.book_id}_${job.chapter_number}`
                  const chapter = chapterInfo[chapterKey]
                  
                  // Use book title from metadata, fallback to a more readable format
                  const bookTitle = book?.book_title || (job.book_id.startsWith('book_') ? job.book_id.replace('book_', '').replace(/_/g, ' ') : job.book_id)
                  const chapterTitle = chapter?.title || `Chapter ${job.chapter_number}`
                  
                  const elements = []
                  
                  if (showBook) {
                    elements.push(
                      <div className={styles.sectionLabelBook} key={`section-book-${job.book_id}-${index}`}>
                        {bookTitle}
                      </div>
                    )
                  }
                  
                  if (showChapter) {
                    elements.push(
                      <div className={styles.sectionLabelChapter} key={`section-chapter-${job.book_id}-${job.chapter_number}-${index}`}>
                        {chapterTitle}
                      </div>
                    )
                  }
                  
                  elements.push(
                    <div
                      key={`${job.book_id}_${job.chapter_number}_${job.chunk_index}`}
                      className={`${styles.jobCard} ${
                        job.status === 'failed' ? styles.jobCardFailed : ''
                      } ${job.status === 'running' ? styles.jobCardRunning : ''}`}
                      title={`${bookTitle} - ${chapterTitle} - Chunk ${job.chunk_index} (${job.status})${job.error ? `: ${job.error}` : ''}`}
                    >
                      <div className={styles.jobCardChunk}>
                        {job.status === 'failed' && <XCircle size={10} className={styles.jobCardFailedIcon} />}
                        {job.status === 'running' && <Loader size={10} className={styles.jobCardRunningIcon} />}
                        {job.chunk_index}
                      </div>
                    </div>
                  )
                  
                  return elements
                })}
                {loadingJobs && (
                  <div className={styles.loadingMore}>Loading more jobs...</div>
                )}
                {!hasMoreJobs && jobs.length > 0 && (
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

