import { useState, useRef, useEffect, ReactNode } from 'react'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
  className?: string
}

export function Tooltip({
  content,
  children,
  position = 'top',
  delay = 300,
  className = ''
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [coords, setCoords] = useState({ top: 0, left: 0 })
  const triggerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

  const showTooltip = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true)
    }, delay)
  }

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setIsVisible(false)
  }

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const trigger = triggerRef.current.getBoundingClientRect()
      const tooltip = tooltipRef.current.getBoundingClientRect()

      let top = 0
      let left = 0
      const gap = 8

      switch (position) {
        case 'top':
          top = trigger.top - tooltip.height - gap
          left = trigger.left + (trigger.width - tooltip.width) / 2
          break
        case 'bottom':
          top = trigger.bottom + gap
          left = trigger.left + (trigger.width - tooltip.width) / 2
          break
        case 'left':
          top = trigger.top + (trigger.height - tooltip.height) / 2
          left = trigger.left - tooltip.width - gap
          break
        case 'right':
          top = trigger.top + (trigger.height - tooltip.height) / 2
          left = trigger.right + gap
          break
      }

      // Keep within viewport
      left = Math.max(8, Math.min(left, window.innerWidth - tooltip.width - 8))
      top = Math.max(8, Math.min(top, window.innerHeight - tooltip.height - 8))

      setCoords({ top, left })
    }
  }, [isVisible, position])

  return (
    <div
      className={`inline-flex relative ${className}`}
      ref={triggerRef}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
    >
      {children}
      {isVisible && (
        <div
          ref={tooltipRef}
          className="bg-surface-elevated border border-border-default rounded-md px-3 py-2 text-xs text-text-primary shadow-lg z-[300] max-w-[280px] pointer-events-none animate-[tooltipFadeIn_0.15s_ease-out]"
          style={{
            position: 'fixed',
            top: coords.top,
            left: coords.left,
          }}
        >
          {content}
        </div>
      )}
    </div>
  )
}

// Help tooltip with info icon
interface HelpTooltipProps {
  content: ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
}

export function HelpTooltip({ content, position = 'top' }: HelpTooltipProps) {
  return (
    <Tooltip content={content} position={position} className="inline-flex flex-shrink-0">
      <span className="inline-flex items-center justify-center w-3 h-3 rounded-full border border-border-default text-[8px] font-semibold text-text-tertiary cursor-help opacity-60 transition-all duration-150 hover:border-brand-primary hover:text-brand-primary hover:opacity-100">?</span>
    </Tooltip>
  )
}

// Pipeline stage explanations
export const PipelineHelp = {
  normalize: (
    <div className="leading-relaxed">
      <strong className="block mb-1 text-brand-primary text-xs uppercase tracking-wide">Normalize</strong>
      <p className="m-0 text-text-secondary">Cleans and formats the raw chapter text for TTS processing. Removes HTML, fixes encoding issues, and standardizes formatting.</p>
    </div>
  ),
  chunk: (
    <div className="leading-relaxed">
      <strong className="block mb-1 text-brand-primary text-xs uppercase tracking-wide">Chunk</strong>
      <p className="m-0 text-text-secondary">Splits chapters into smaller segments (≤250 chars) suitable for the TTS engine. Preserves sentence boundaries.</p>
    </div>
  ),
  audio: (
    <div className="leading-relaxed">
      <strong className="block mb-1 text-brand-primary text-xs uppercase tracking-wide">Audio Generation</strong>
      <p className="m-0 text-text-secondary">Converts text chunks to speech using the TTS model. This is the most time-consuming step.</p>
    </div>
  ),
  validate: (
    <div className="leading-relaxed">
      <strong className="block mb-1 text-brand-primary text-xs uppercase tracking-wide">Validate</strong>
      <p className="m-0 text-text-secondary">Checks generated audio for quality issues like truncation, silence, or artifacts.</p>
    </div>
  ),
  export: (
    <div className="leading-relaxed">
      <strong className="block mb-1 text-brand-primary text-xs uppercase tracking-wide">Export</strong>
      <p className="m-0 text-text-secondary">Combines all audio chunks into a single M4B audiobook file with chapter markers.</p>
    </div>
  )
}

export default Tooltip
