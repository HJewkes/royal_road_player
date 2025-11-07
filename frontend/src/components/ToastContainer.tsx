import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import useToastStore from '../store/useToastStore'
import type { ToastType } from '../types'
import styles from './ToastContainer.module.css'

const iconMap: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const colorMap: Record<ToastType, string> = {
  success: 'var(--color-success)',
  error: 'var(--color-error)',
  warning: 'var(--color-warning)',
  info: 'var(--color-accent-blue)',
}

function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  if (toasts.length === 0) {
    return null
  }

  return (
    <div className={styles.toastContainer}>
      {toasts.map((toast) => {
        const Icon = iconMap[toast.type]
        const color = colorMap[toast.type]

        return (
          <div
            key={toast.id}
            className={`${styles.toast} ${styles[toast.type]}`}
            style={{ borderLeftColor: color }}
          >
            <Icon size={20} style={{ color }} />
            <span className={styles.toastMessage}>{toast.message}</span>
            <button
              className={styles.toastClose}
              onClick={() => removeToast(toast.id)}
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default ToastContainer

