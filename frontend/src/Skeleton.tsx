// Skeleton loading components for perceived performance
import { Skeleton as TitanSkeleton } from '@titan-design/react-ui'

interface SkeletonProps {
  className?: string
  width?: string | number
  height?: string | number
  style?: React.CSSProperties
}

export function Skeleton({ className = '', width, height, style }: SkeletonProps) {
  return (
    <TitanSkeleton
      className={className}
      variant="rounded"
      width={width}
      height={height}
      style={style as any}
    />
  )
}

export function SkeletonText({ lines = 1, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          width={i === lines - 1 && lines > 1 ? '70%' : '100%'}
          height={14}
        />
      ))}
    </div>
  )
}

// Dashboard skeleton
export function DashboardSkeleton() {
  return (
    <div className="animate-[fadeIn_var(--duration-slow)_var(--ease-out)]">
      {/* Header skeleton */}
      <div className="flex justify-between items-center mb-6">
        <Skeleton width={120} height={28} />
        <Skeleton width={120} height={40} />
      </div>

      {/* Series skeleton */}
      {[1, 2].map(i => (
        <section key={i} className="mb-8 animate-[fadeIn_var(--duration-slow)_var(--ease-out)]" style={{ animationDelay: `${i * 100}ms` }}>
          <div className="flex justify-between items-start mb-4 gap-6">
            <Skeleton width={280} height={32} />
            <div className="flex items-center gap-4 flex-shrink-0" style={{ gap: '2rem' }}>
              <Skeleton width={80} height={40} />
              <Skeleton width={80} height={40} />
              <Skeleton width={100} height={40} />
            </div>
          </div>

          <div className="bg-surface-base border border-border-subtle rounded-lg overflow-hidden">
            <div className="grid grid-cols-[60px_80px_60px_60px_140px_100px] items-center gap-3 px-5 py-3 bg-black/20 text-xs text-text-tertiary uppercase tracking-[0.1em] font-semibold border-b border-border-subtle">
              <Skeleton width={60} height={14} />
              <Skeleton width={60} height={14} />
              <Skeleton width={40} height={14} />
              <Skeleton width={40} height={14} />
              <Skeleton width={60} height={14} />
              <Skeleton width={60} height={14} />
            </div>
            {[1, 2, 3].map(j => (
              <div key={j} className="grid grid-cols-[60px_80px_60px_60px_140px_100px] items-center gap-3 px-5 py-3 border-b border-border-subtle last:border-b-0" style={{ animationDelay: `${(i * 3 + j) * 50}ms` }}>
                <div className="flex items-center gap-4 min-w-0" style={{ gap: '1rem' }}>
                  <Skeleton width={24} height={24} />
                  <Skeleton width={150} height={16} />
                </div>
                <Skeleton width={30} height={16} />
                <Skeleton width={30} height={16} />
                <Skeleton width={30} height={16} />
                <Skeleton width={100} height={8} />
                <Skeleton width={90} height={28} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

// Book view skeleton
export function BookViewSkeleton() {
  return (
    <div className="max-w-[1100px] mx-auto animate-[fadeIn_var(--duration-slow)_var(--ease-out)]">
      <Skeleton width={160} height={20} />

      <div className="grid grid-cols-[60px_80px_60px_60px_140px_100px] items-center gap-3 px-5 py-3 bg-black/20 text-xs text-text-tertiary uppercase tracking-[0.1em] font-semibold border-b border-border-subtle" style={{ marginTop: '1rem' }}>
        <Skeleton width={200} height={48} />
        <Skeleton width={180} height={16} style={{ marginTop: '0.5rem' }} />
      </div>

      {/* Pipeline summary skeleton */}
      <div className="grid grid-cols-4 gap-5 mb-8 p-6 bg-gradient-to-br from-surface-elevated to-surface-base border border-border rounded-xl shadow-lg">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="flex flex-col gap-2 p-5 bg-black/[0.18] rounded-lg text-center border border-border-subtle" style={{ animationDelay: `${i * 50}ms` }}>
            <Skeleton width={80} height={12} />
            <Skeleton width={60} height={32} style={{ marginTop: '0.5rem' }} />
          </div>
        ))}
      </div>

      {/* Bulk actions skeleton */}
      <div className="flex flex-wrap gap-3 mb-6">
        {[1, 2, 3, 4].map(i => (
          <Skeleton key={i} width={100} height={36} style={{ animationDelay: `${i * 30}ms` }} />
        ))}
      </div>

      {/* Chapter table skeleton */}
      <div className="bg-surface-base border border-border-subtle rounded-lg overflow-hidden">
        <div className="grid grid-cols-[1fr_140px_180px] items-center gap-4 px-5 py-2 bg-black/20 text-xs text-text-tertiary uppercase tracking-[0.08em] font-medium border-b border-border-subtle">
          <Skeleton width={80} height={14} />
          <Skeleton width={40} height={14} />
          <Skeleton width={40} height={14} />
          <Skeleton width={120} height={14} />
          <Skeleton width={40} height={14} />
          <Skeleton width={40} height={14} />
        </div>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="grid grid-cols-[1fr_140px_180px] items-center gap-4 px-5 py-3 border-b border-border-subtle last:border-b-0 transition-all animate-[rowFadeIn_var(--duration-normal)_var(--ease-out)_backwards]" style={{ animationDelay: `${i * 40}ms` }}>
            <div className="flex items-center gap-3 min-w-0" style={{ gap: '1rem' }}>
              <Skeleton width={28} height={20} />
              <Skeleton width={200} height={16} />
            </div>
            <Skeleton width={24} height={24} />
            <Skeleton width={24} height={24} />
            <Skeleton width={120} height={8} />
            <Skeleton width={32} height={24} />
            <Skeleton width={24} height={24} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default Skeleton
