import { useState, useRef, useCallback } from 'react'
import { CircularProgress, cn } from '@titan-design/react-ui'
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

  // Only show as active if actually running jobs exist (not just is_processing flag)
  const hasWork = status.pending > 0 || status.running > 0
  const isActive = hasWork && (status.is_processing || status.running > 0)
  const isComplete = total > 0 && done === total && status.pending === 0 && status.running === 0

  // Determine what to display
  const getStatusText = () => {
    if (isActive && status.current_job_info) {
      return `Book ${status.current_job_info.book_number} · Ch ${status.current_job_info.chapter_number}`
    }
    if (isActive && status.running > 0) {
      return `Processing ${status.running} chunk${status.running > 1 ? 's' : ''}`
    }
    if (isComplete) {
      return 'Complete'
    }
    if (status.pending > 0) {
      return `${status.pending} pending`
    }
    return 'Queue empty'
  }

  const statusText = getStatusText()

  return (
    <div
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className={cn(
        "flex items-center gap-3 px-4 py-2 bg-surface-base border rounded-full cursor-default transition-all duration-fast",
        isActive && "border-brand-primary/40 shadow-[0_0_20px_rgba(var(--color-brand-primary-rgb),0.15)]",
        isComplete && "border-status-success/30",
        !isActive && !isComplete && "border-border"
      )}>
        {/* Circular progress */}
        <div className="relative w-8 h-8 flex-shrink-0">
          <CircularProgress
            value={progressPercent}
            size={32}
            strokeWidth={3}
            color={isActive ? 'primary' : isComplete ? 'success' : 'secondary'}
            showValue={false}
          />
          {isActive && (
            <div className="absolute top-1/2 left-1/2 w-4 h-4 -mt-2 -ml-2 border-2 border-transparent border-t-brand-primary rounded-full animate-spin" />
          )}
        </div>

        {/* Summary text */}
        <div className="flex flex-col gap-[1px] min-w-[90px]">
          <span className={cn("font-mono text-xs font-medium",
            isActive && "text-brand-primary",
            isComplete && "text-status-success",
            !isActive && !isComplete && "text-text-tertiary"
          )}>
            {statusText}
          </span>
          {total > 0 && <span className="font-mono text-[10px] text-text-tertiary opacity-70">{done}/{total}</span>}
        </div>
      </div>

      {/* Details dropdown */}
      {showDetails && (hasWork || status.queued_chapters.length > 0) && (
        <div
          className="absolute top-[calc(100%+8px)] right-0 min-w-[220px] bg-surface-base border border-border rounded-lg shadow-lg z-[1000] overflow-hidden"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {/* Hover gap spacer (replaces ::before pseudo-element) */}
          <div className="absolute -top-3 left-0 right-0 h-3" />
          <div className="px-3 py-2 text-xs font-semibold text-text-tertiary uppercase tracking-[0.05em] bg-black/20 border-b border-border-subtle">
            {isActive ? 'Processing Queue' : 'Queue Summary'}
          </div>
          <div className="flex justify-around p-3 bg-black/10">
            <div className="flex flex-col items-center gap-[2px]">
              <span className="font-mono text-lg font-semibold text-text-primary">{status.pending}</span>
              <span className="text-[10px] text-text-tertiary uppercase tracking-[0.05em]">pending</span>
            </div>
            <div className="flex flex-col items-center gap-[2px]">
              <span className="font-mono text-lg font-semibold text-brand-primary">{status.running}</span>
              <span className="text-[10px] text-text-tertiary uppercase tracking-[0.05em]">running</span>
            </div>
            <div className="flex flex-col items-center gap-[2px]">
              <span className="font-mono text-lg font-semibold text-status-success">{status.completed}</span>
              <span className="text-[10px] text-text-tertiary uppercase tracking-[0.05em]">done</span>
            </div>
            {status.failed > 0 && (
              <div className="flex flex-col items-center gap-[2px]">
                <span className="font-mono text-lg font-semibold text-status-error">{status.failed}</span>
                <span className="text-[10px] text-text-tertiary uppercase tracking-[0.05em]">failed</span>
              </div>
            )}
          </div>
          {status.queued_chapters.length > 0 && (
            <>
              <div className="h-px bg-border-subtle" />
              <div className="max-h-[200px] overflow-y-auto">
                {status.queued_chapters.map((chapter, idx) => (
                  <div
                    key={`${chapter.fiction_id}_${chapter.book_number}_${chapter.chapter_number}`}
                    className={cn(
                      "flex justify-between items-center px-3 py-2 border-b border-border-subtle last:border-b-0 font-mono text-xs",
                      idx === 0 && isActive && "bg-brand-primary/10"
                    )}
                  >
                    <div className="flex gap-2">
                      <span className="text-brand-primary font-medium">Book {chapter.book_number}</span>
                      <span className="text-text-secondary">Ch {chapter.chapter_number}</span>
                    </div>
                    <div className="text-text-tertiary">
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
