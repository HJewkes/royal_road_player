import { StatusPill, StatusPillContent, cn } from '@titan-design/react-ui'
import { QueueStatus } from './types'

interface QueueIndicatorProps {
  status: QueueStatus
}

export function QueueIndicator({ status }: QueueIndicatorProps) {
  const total = status.pending + status.running + status.completed + status.failed
  const done = status.completed
  const progressPercent = total > 0 ? (done / total) * 100 : 0

  const hasWork = status.pending > 0 || status.running > 0
  const isActive = hasWork && (status.is_processing || status.running > 0)
  const isComplete = total > 0 && done === total && status.pending === 0 && status.running === 0

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
  const pillStatus = isActive ? 'active' : isComplete ? 'success' : 'idle'
  const hasDropdown = hasWork || status.queued_chapters.length > 0

  return (
    <StatusPill
      progress={progressPercent}
      label={statusText}
      detail={total > 0 ? `${done}/${total}` : undefined}
      status={pillStatus}
    >
      {hasDropdown && (
        <StatusPillContent className="p-0 overflow-hidden">
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
        </StatusPillContent>
      )}
    </StatusPill>
  )
}
