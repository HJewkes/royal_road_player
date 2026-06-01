import { StepProgress, Step } from '@titan-design/react-ui'

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
  if (needsDownload) {
    return (
      <StepProgress compact={compact}>
        <Step
          label={isDownloading ? '...' : '\u2193'}
          value={0}
          tooltip="Download chapters"
          isActive
          onClick={isDownloading ? undefined : onDownload}
          isLocked={isDownloading}
        />
        <Step label="N" value={0} tooltip="Download first" isLocked />
        <Step label="C" value={0} tooltip="Download first" isLocked />
        <Step label="G" value={0} tooltip="Download first" isLocked />
        <Step label="E" value={0} tooltip="Download first" isLocked />
      </StepProgress>
    )
  }

  const pct = (n: number) => (totalChapters > 0 ? (n / totalChapters) * 100 : 0)
  const done = (n: number) => totalChapters > 0 && n === totalChapters

  const normComplete = done(normalized)
  const chunkComplete = done(chunked)
  const audioCompleteFlag = done(audioComplete)
  const exportComplete = done(exported)

  return (
    <StepProgress compact={compact}>
      <Step
        label="N"
        value={pct(normalized)}
        tooltip={`Normalize: ${normalized}/${totalChapters}`}
        isComplete={normComplete}
        isActive={!normComplete && normalized < totalChapters}
        onClick={onNormalize}
        isLocked={disabled || normComplete}
      />
      <Step
        label="C"
        value={pct(chunked)}
        tooltip={`Chunk: ${chunked}/${totalChapters}`}
        isComplete={chunkComplete}
        isActive={normComplete && !chunkComplete}
        onClick={onChunk}
        isLocked={disabled || chunkComplete || !normComplete}
      />
      <Step
        label="G"
        value={pct(audioComplete)}
        tooltip={`Generate: ${audioComplete}/${totalChapters}`}
        isComplete={audioCompleteFlag}
        isActive={chunkComplete && !audioCompleteFlag}
        onClick={onGenerate}
        isLocked={disabled || audioCompleteFlag || !chunkComplete}
      />
      <Step
        label="E"
        value={pct(exported)}
        tooltip={`Export: ${exported}/${totalChapters}`}
        isComplete={exportComplete}
        isActive={audioCompleteFlag && !exportComplete}
        onClick={onExport}
        isLocked={disabled || exportComplete || !audioCompleteFlag}
      />
    </StepProgress>
  )
}
