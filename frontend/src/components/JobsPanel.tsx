import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import useToastStore from '../store/useToastStore'
import type { Book, Job } from '../types'
import styles from './JobsPanel.module.css'

interface JobsPanelProps {
  book: Book | null
  onClose: () => void
}

function JobsPanel({ book, onClose }: JobsPanelProps) {
  const toast = useToastStore()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void loadJobs()
    const interval = setInterval(() => { void loadJobs() }, 2000) // Poll every 2 seconds
    return () => { clearInterval(interval) }
  }, [book])

  const loadJobs = async (): Promise<void> => {
    try {
      const bookId = book?.id
      const url = bookId ? `/api/jobs?book_id=${bookId}` : '/api/jobs'
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to fetch jobs: ${response.statusText}`)
      }
      const data = await response.json() as { jobs?: Job[] }
      setJobs(data.jobs || [])
    } catch (error) {
      console.error('Failed to load jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const cancelJob = async (jobId: string): Promise<void> => {
    try {
      const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' })
      if (!response.ok) {
        throw new Error(`Failed to cancel job: ${response.statusText}`)
      }
      await loadJobs()
      toast.success('Job cancelled')
    } catch (error) {
      console.error('Failed to cancel job:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to cancel job')
    }
  }

  const getJobTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      'scrape_book': 'Scraping Book',
      'generate_audio': 'Generating Audio',
      'generate_chapter_audio': 'Generating Chapter Audio',
    }
    return labels[type] || type
  }

  const escapeHtml = (text: string): string => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h3>Background Jobs</h3>
        <button className={styles.btnClose} onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      <div className={styles.jobsList}>
        {loading ? (
          <p className="loading">Loading jobs...</p>
        ) : jobs.length === 0 ? (
          <p>No jobs found.</p>
        ) : (
          jobs.map((job) => {
            const statusClass = job.status.toLowerCase()
            const progress = (job as unknown as { progress?: number }).progress || 0
            
            return (
              <div key={job.id} className={`${styles.jobItem} ${styles[statusClass]}`}>
                <div className={styles.jobHeader}>
                  <div>
                    <div className={styles.jobTitle}>{getJobTypeLabel(job.type)}</div>
                    <div className={styles.jobMessage} dangerouslySetInnerHTML={{ __html: escapeHtml(job.message || '') }} />
                  </div>
                  {job.status === 'running' && (
                    <button className={styles.btnCancel} onClick={() => { void cancelJob(job.id) }}>
                      Cancel
                    </button>
                  )}
                </div>
                {job.status === 'running' && (
                  <div className={styles.jobProgress}>
                    <div className={styles.jobProgressBar}>
                      <div className={styles.jobProgressFill} style={{ width: `${progress}%` }}></div>
                    </div>
                    <div style={{ fontSize: '0.85em', color: 'var(--color-text-tertiary)', marginTop: '5px' }}>
                      {progress}%
                    </div>
                  </div>
                )}
                <div style={{ fontSize: '0.8em', color: 'var(--color-text-tertiary)', marginTop: '5px' }}>
                  {job.created_at ? new Date(job.created_at).toLocaleString() : ''}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default JobsPanel

