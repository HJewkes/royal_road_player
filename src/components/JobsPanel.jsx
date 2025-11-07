import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import styles from './JobsPanel.module.css'

function JobsPanel({ book, onClose }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadJobs()
    const interval = setInterval(loadJobs, 2000) // Poll every 2 seconds
    return () => clearInterval(interval)
  }, [book])

  const loadJobs = async () => {
    try {
      const bookId = book?.id
      const url = bookId ? `/api/jobs?book_id=${bookId}` : '/api/jobs'
      const response = await fetch(url)
      const data = await response.json()
      setJobs(data.jobs || [])
    } catch (error) {
      console.error('Failed to load jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const cancelJob = async (jobId) => {
    try {
      await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' })
      await loadJobs()
    } catch (error) {
      console.error('Failed to cancel job:', error)
      alert('Failed to cancel job')
    }
  }

  const getJobTypeLabel = (type) => {
    const labels = {
      'scrape_book': 'Scraping Book',
      'generate_audio': 'Generating Audio',
      'generate_chapter_audio': 'Generating Chapter Audio',
    }
    return labels[type] || type
  }

  const escapeHtml = (text) => {
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
          jobs.map(job => {
            const statusClass = job.status.toLowerCase()
            const progress = job.progress || 0
            
            return (
              <div key={job.id} className={`${styles.jobItem} ${styles[statusClass]}`}>
                <div className={styles.jobHeader}>
                  <div>
                    <div className={styles.jobTitle}>{getJobTypeLabel(job.type)}</div>
                    <div className={styles.jobMessage} dangerouslySetInnerHTML={{ __html: escapeHtml(job.message || '') }} />
                  </div>
                  {job.status === 'running' && (
                    <button className={styles.btnCancel} onClick={() => cancelJob(job.id)}>
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
                  {new Date(job.created_at).toLocaleString()}
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

