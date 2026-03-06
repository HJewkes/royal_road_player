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
      style={style}
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
    <div className="dashboard">
      {/* Header skeleton */}
      <div className="dashboard-header">
        <Skeleton width={120} height={28} />
        <Skeleton width={120} height={40} />
      </div>

      {/* Series skeleton */}
      {[1, 2].map(i => (
        <section key={i} className="fiction-section" style={{ animationDelay: `${i * 100}ms` }}>
          <div className="fiction-header">
            <Skeleton width={280} height={32} />
            <div className="fiction-summary" style={{ gap: '2rem' }}>
              <Skeleton width={80} height={40} />
              <Skeleton width={80} height={40} />
              <Skeleton width={100} height={40} />
            </div>
          </div>

          <div className="book-table">
            <div className="book-header">
              <Skeleton width={60} height={14} />
              <Skeleton width={60} height={14} />
              <Skeleton width={40} height={14} />
              <Skeleton width={40} height={14} />
              <Skeleton width={60} height={14} />
              <Skeleton width={60} height={14} />
            </div>
            {[1, 2, 3].map(j => (
              <div key={j} className="book-row" style={{ animationDelay: `${(i * 3 + j) * 50}ms` }}>
                <div className="col-book" style={{ gap: '1rem' }}>
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
    <div className="book-view">
      <Skeleton width={160} height={20} />

      <div className="book-header" style={{ marginTop: '1rem' }}>
        <Skeleton width={200} height={48} />
        <Skeleton width={180} height={16} style={{ marginTop: '0.5rem' }} />
      </div>

      {/* Pipeline summary skeleton */}
      <div className="pipeline-summary">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="stat" style={{ animationDelay: `${i * 50}ms` }}>
            <Skeleton width={80} height={12} />
            <Skeleton width={60} height={32} style={{ marginTop: '0.5rem' }} />
          </div>
        ))}
      </div>

      {/* Bulk actions skeleton */}
      <div className="bulk-actions">
        {[1, 2, 3, 4].map(i => (
          <Skeleton key={i} width={100} height={36} style={{ animationDelay: `${i * 30}ms` }} />
        ))}
      </div>

      {/* Chapter table skeleton */}
      <div className="chapter-table">
        <div className="chapter-header">
          <Skeleton width={80} height={14} />
          <Skeleton width={40} height={14} />
          <Skeleton width={40} height={14} />
          <Skeleton width={120} height={14} />
          <Skeleton width={40} height={14} />
          <Skeleton width={40} height={14} />
        </div>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="chapter-row" style={{ animationDelay: `${i * 40}ms` }}>
            <div className="col-chapter" style={{ gap: '1rem' }}>
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
