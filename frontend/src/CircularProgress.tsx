import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { CircularProgress as TitanCircularProgress, cn } from '@titan-design/react-ui'
import type { ProgressColor } from '@titan-design/react-ui'

interface AppCircularProgressProps {
  value: number
  size?: number
  strokeWidth?: number
  label?: string
  tooltip?: string
  isActive?: boolean
  isComplete?: boolean
  onClick?: () => void
  disabled?: boolean
}

function AppCircularProgress({
  value,
  size = 36,
  strokeWidth = 3,
  label,
  tooltip,
  isActive = false,
  isComplete = false,
  onClick,
  disabled = false,
}: AppCircularProgressProps) {
  const [showTooltip, setShowTooltip] = useState(false)
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 })
  const wrapperRef = useRef<HTMLDivElement>(null)

  const color: ProgressColor = isComplete ? 'success' : isActive ? 'primary' : 'secondary'
  const pct = Math.min(100, Math.max(0, value))
  const isClickable = onClick && !disabled

  useEffect(() => {
    if (showTooltip && wrapperRef.current) {
      const rect = wrapperRef.current.getBoundingClientRect()
      setTooltipPos({
        top: rect.top - 8,
        left: rect.left + rect.width / 2,
      })
    }
  }, [showTooltip])

  return (
    <div
      ref={wrapperRef}
      className={cn('relative inline-flex', isClickable && 'cursor-pointer')}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onClick={!disabled ? onClick : undefined}
    >
      <TitanCircularProgress
        value={pct}
        size={size}
        strokeWidth={strokeWidth}
        color={color}
        showValue={false}
        className={cn(
          'transition-transform',
          isClickable && 'hover:scale-110',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      />
      {label && (
        <span
          className={cn(
            'absolute inset-0 flex items-center justify-center font-mono text-xs font-semibold transition-colors',
            isComplete
              ? 'text-status-success text-sm'
              : isActive
                ? 'text-brand-primary'
                : 'text-text-tertiary',
          )}
        >
          {isComplete ? '\u2713' : label}
        </span>
      )}

      {/* Tooltip - rendered via portal to escape overflow containers */}
      {showTooltip && tooltip && createPortal(
        <div
          className="rounded bg-surface-elevated border border-border-subtle px-3 py-1 font-mono text-xs text-text-secondary whitespace-nowrap pointer-events-none animate-in fade-in z-[10000]"
          style={{
            position: 'fixed',
            top: tooltipPos.top,
            left: tooltipPos.left,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip}
        </div>,
        document.body,
      )}
    </div>
  )
}

interface PipelineStagesProps {
  normalized: number
  chunked: number
  audioComplete: number
  exported: number
  totalChapters: number
  compact?: boolean
  onNormalize?: () => void
  onChunk?: () => void
  onGenerate?: () => void
  onExport?: () => void
  disabled?: boolean
  needsDownload?: boolean
  onDownload?: () => void
  isDownloading?: boolean
}

export function PipelineStages({
  normalized,
  chunked,
  audioComplete,
  exported,
  totalChapters,
  compact = false,
  onNormalize,
  onChunk,
  onGenerate,
  onExport,
  disabled = false,
  needsDownload = false,
  onDownload,
  isDownloading = false,
}: PipelineStagesProps) {
  const size = compact ? 28 : 40
  const strokeWidth = compact ? 2.5 : 3
  const connectorClass = cn('h-[2px] rounded-[1px] bg-border-default', compact ? 'w-2' : 'w-3')

  if (needsDownload) {
    const lockedConnectorClass = cn(connectorClass, 'opacity-20')

    return (
      <div className={cn('flex items-center', compact ? 'gap-[2px]' : 'gap-1')}>
        <AppCircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label={isDownloading ? '...' : '\u2193'}
          tooltip="Download chapters"
          isComplete={false}
          isActive={true}
          onClick={onDownload}
          disabled={isDownloading}
        />

        <div className={lockedConnectorClass} />

        <AppCircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="N"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />

        <div className={lockedConnectorClass} />

        <AppCircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="C"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />

        <div className={lockedConnectorClass} />

        <AppCircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="G"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />

        <div className={lockedConnectorClass} />

        <AppCircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="E"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />
      </div>
    )
  }

  const normPercent = totalChapters > 0 ? (normalized / totalChapters) * 100 : 0
  const chunkPercent = totalChapters > 0 ? (chunked / totalChapters) * 100 : 0
  const audioPercent = totalChapters > 0 ? (audioComplete / totalChapters) * 100 : 0
  const exportPercent = totalChapters > 0 ? (exported / totalChapters) * 100 : 0

  const normComplete = totalChapters > 0 && normalized === totalChapters
  const chunkComplete = totalChapters > 0 && chunked === totalChapters
  const audioCompleteFlag = totalChapters > 0 && audioComplete === totalChapters
  const exportComplete = totalChapters > 0 && exported === totalChapters

  const normActive = !normComplete && normalized < totalChapters
  const chunkActive = normComplete && !chunkComplete
  const audioActiveFlag = chunkComplete && !audioCompleteFlag
  const exportActive = audioCompleteFlag && !exportComplete

  return (
    <div className={cn('flex items-center', compact ? 'gap-[2px]' : 'gap-1')}>
      <AppCircularProgress
        value={normPercent}
        size={size}
        strokeWidth={strokeWidth}
        label="N"
        tooltip={`Normalize: ${normalized}/${totalChapters}`}
        isComplete={normComplete}
        isActive={normActive}
        onClick={onNormalize}
        disabled={disabled || normComplete}
      />

      <div className={connectorClass} />

      <AppCircularProgress
        value={chunkPercent}
        size={size}
        strokeWidth={strokeWidth}
        label="C"
        tooltip={`Chunk: ${chunked}/${totalChapters}`}
        isComplete={chunkComplete}
        isActive={chunkActive}
        onClick={onChunk}
        disabled={disabled || chunkComplete || !normComplete}
      />

      <div className={connectorClass} />

      <AppCircularProgress
        value={audioPercent}
        size={size}
        strokeWidth={strokeWidth}
        label="G"
        tooltip={`Generate: ${audioComplete}/${totalChapters}`}
        isComplete={audioCompleteFlag}
        isActive={audioActiveFlag}
        onClick={onGenerate}
        disabled={disabled || audioCompleteFlag || !chunkComplete}
      />

      <div className={connectorClass} />

      <AppCircularProgress
        value={exportPercent}
        size={size}
        strokeWidth={strokeWidth}
        label="E"
        tooltip={`Export: ${exported}/${totalChapters}`}
        isComplete={exportComplete}
        isActive={exportActive}
        onClick={onExport}
        disabled={disabled || exportComplete || !audioCompleteFlag}
      />
    </div>
  )
}
