import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'

interface CircularProgressProps {
  value: number  // 0-100
  size?: number
  strokeWidth?: number
  label?: string
  tooltip?: string
  isActive?: boolean
  isComplete?: boolean
  onClick?: () => void
  disabled?: boolean
}

export function CircularProgress({
  value,
  size = 36,
  strokeWidth = 3,
  label,
  tooltip,
  isActive = false,
  isComplete = false,
  onClick,
  disabled = false,
}: CircularProgressProps) {
  const [showTooltip, setShowTooltip] = useState(false)
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 })
  const wrapperRef = useRef<HTMLDivElement>(null)
  
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (value / 100) * circumference
  
  const isClickable = onClick && !disabled
  
  // Calculate tooltip position when showing
  useEffect(() => {
    if (showTooltip && wrapperRef.current) {
      const rect = wrapperRef.current.getBoundingClientRect()
      setTooltipPos({
        top: rect.top - 8, // 8px above the element
        left: rect.left + rect.width / 2,
      })
    }
  }, [showTooltip])
  
  return (
    <div 
      ref={wrapperRef}
      className={`circular-progress-wrapper ${isClickable ? 'clickable' : ''}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <button
        className={`circular-progress ${isActive ? 'active' : ''} ${isComplete ? 'complete' : ''}`}
        style={{ width: size, height: size }}
        onClick={onClick}
        disabled={disabled || !onClick}
        type="button"
      >
        <svg width={size} height={size}>
          {/* Background circle */}
          <circle
            className="circular-progress-bg"
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={strokeWidth}
          />
          {/* Progress circle */}
          <circle
            className="circular-progress-fill"
            cx={size / 2}
            cy={size / 2}
            r={radius}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </svg>
        {/* Center content */}
        <span className="circular-progress-label">
          {isComplete ? '✓' : label}
        </span>
      </button>
      
      {/* Tooltip - rendered via portal to escape overflow containers */}
      {showTooltip && tooltip && createPortal(
        <div 
          className="circular-progress-tooltip-fixed"
          style={{
            position: 'fixed',
            top: tooltipPos.top,
            left: tooltipPos.left,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip}
        </div>,
        document.body
      )}
    </div>
  )
}

// Compact version for dashboard rows
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
  // For non-downloaded books
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
  
  // If needs download, show download-required state
  if (needsDownload) {
    return (
      <div className={`pipeline-stages ${compact ? 'compact' : ''} needs-download`}>
        <CircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label={isDownloading ? '...' : '↓'}
          tooltip="Download chapters"
          isComplete={false}
          isActive={true}
          onClick={onDownload}
          disabled={isDownloading}
        />
        
        <div className="pipeline-connector-mini locked" />
        
        <CircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="N"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />
        
        <div className="pipeline-connector-mini locked" />
        
        <CircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="C"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />
        
        <div className="pipeline-connector-mini locked" />
        
        <CircularProgress
          value={0}
          size={size}
          strokeWidth={strokeWidth}
          label="G"
          tooltip="Download first"
          isComplete={false}
          isActive={false}
          disabled={true}
        />
        
        <div className="pipeline-connector-mini locked" />
        
        <CircularProgress
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
  
  // Determine which stage is complete (must have chapters to be complete)
  const normComplete = totalChapters > 0 && normalized === totalChapters
  const chunkComplete = totalChapters > 0 && chunked === totalChapters
  const audioCompleteFlag = totalChapters > 0 && audioComplete === totalChapters
  const exportComplete = totalChapters > 0 && exported === totalChapters
  
  const normActive = !normComplete && normalized < totalChapters
  const chunkActive = normComplete && !chunkComplete
  const audioActiveFlag = chunkComplete && !audioCompleteFlag
  const exportActive = audioCompleteFlag && !exportComplete

  return (
    <div className={`pipeline-stages ${compact ? 'compact' : ''}`}>
      <CircularProgress
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
      
      <div className="pipeline-connector-mini" />
      
      <CircularProgress
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
      
      <div className="pipeline-connector-mini" />
      
      <CircularProgress
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
      
      <div className="pipeline-connector-mini" />
      
      <CircularProgress
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

