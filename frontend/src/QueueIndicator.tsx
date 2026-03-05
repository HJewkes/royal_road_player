import { useState, useRef, useCallback } from 'react'
import { QueueStatus } from './types'

interface QueueIndicatorProps {
  status: QueueStatus
}

export function QueueIndicator({ status }: QueueIndicatorProps) {
  const [showDetails, setShowDetails] = useState(false)
  const hideTimeoutRef = useRef<number | null>(null)
  
  // Clear any pending hide timeout
  const cancelHide = useCallback(() => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current)
      hideTimeoutRef.current = null
    }
  }, [])
  
  // Show dropdown immediately
  const handleMouseEnter = useCallback(() => {
    cancelHide()
    setShowDetails(true)
  }, [cancelHide])
  
  // Hide dropdown with a small delay to allow mouse to reach dropdown
  const handleMouseLeave = useCallback(() => {
    hideTimeoutRef.current = window.setTimeout(() => {
      setShowDetails(false)
    }, 150) // 150ms delay gives time to reach the dropdown
  }, [])
  
  const total = status.pending + status.running + status.completed + status.failed
  const done = status.completed
  const progressPercent = total > 0 ? (done / total) * 100 : 0
  
  // Calculate SVG parameters
  const size = 32
  const strokeWidth = 3
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (progressPercent / 100) * circumference
  
  // Only show as active if actually running jobs exist (not just is_processing flag)
  const hasWork = status.pending > 0 || status.running > 0
  const isActive = hasWork && (status.is_processing || status.running > 0)
  const isComplete = total > 0 && done === total && status.pending === 0 && status.running === 0
  const isEmpty = total === 0 || (!hasWork && !isComplete)
  
  // Determine what to display
  const getStatusText = () => {
    if (isActive && status.current_job_info) {
      return {
        primary: `Book ${status.current_job_info.book_number} · Ch ${status.current_job_info.chapter_number}`,
        className: 'queue-current'
      }
    }
    if (isActive && status.running > 0) {
      return {
        primary: `Processing ${status.running} chunk${status.running > 1 ? 's' : ''}`,
        className: 'queue-current'
      }
    }
    if (isComplete) {
      return {
        primary: 'Complete',
        className: 'queue-complete-text'
      }
    }
    if (status.pending > 0) {
      return {
        primary: `${status.pending} pending`,
        className: 'queue-idle'
      }
    }
    return {
      primary: 'Queue empty',
      className: 'queue-empty'
    }
  }
  
  const statusText = getStatusText()
  
  return (
    <div 
      className="queue-indicator-container"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className={`queue-indicator-new ${isActive ? 'active' : ''} ${isComplete ? 'complete' : ''} ${isEmpty ? 'empty' : ''}`}>
        {/* Circular progress */}
        <div className="queue-progress-ring">
          <svg width={size} height={size}>
            <circle
              className="queue-progress-bg"
              cx={size / 2}
              cy={size / 2}
              r={radius}
              strokeWidth={strokeWidth}
            />
            <circle
              className="queue-progress-fill"
              cx={size / 2}
              cy={size / 2}
              r={radius}
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          </svg>
          {isActive && (
            <div className="queue-spinner" />
          )}
        </div>
        
        {/* Summary text */}
        <div className="queue-summary">
          <span className={statusText.className}>{statusText.primary}</span>
          {total > 0 && <span className="queue-counts">{done}/{total}</span>}
        </div>
      </div>
      
      {/* Details dropdown */}
      {showDetails && (hasWork || status.queued_chapters.length > 0) && (
        <div 
          className="queue-details-dropdown"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <div className="queue-details-header">
            {isActive ? 'Processing Queue' : 'Queue Summary'}
          </div>
          <div className="queue-details-stats">
            <div className="queue-stat">
              <span className="queue-stat-value">{status.pending}</span>
              <span className="queue-stat-label">pending</span>
            </div>
            <div className="queue-stat">
              <span className="queue-stat-value running">{status.running}</span>
              <span className="queue-stat-label">running</span>
            </div>
            <div className="queue-stat">
              <span className="queue-stat-value complete">{status.completed}</span>
              <span className="queue-stat-label">done</span>
            </div>
            {status.failed > 0 && (
              <div className="queue-stat">
                <span className="queue-stat-value failed">{status.failed}</span>
                <span className="queue-stat-label">failed</span>
              </div>
            )}
          </div>
          {status.queued_chapters.length > 0 && (
            <>
              <div className="queue-details-divider" />
              <div className="queue-details-list">
                {status.queued_chapters.map((chapter, idx) => (
                  <div 
                    key={`${chapter.fiction_id}_${chapter.book_number}_${chapter.chapter_number}`}
                    className={`queue-details-item ${idx === 0 && isActive ? 'current' : ''}`}
                  >
                    <div className="queue-item-info">
                      <span className="queue-item-book">Book {chapter.book_number}</span>
                      <span className="queue-item-chapter">Ch {chapter.chapter_number}</span>
                    </div>
                    <div className="queue-item-progress">
                      {chapter.pending_chunks} chunks
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

