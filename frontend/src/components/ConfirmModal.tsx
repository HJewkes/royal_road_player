import { useEffect, useRef, useCallback } from 'react'
import { AlertTriangle, X } from 'lucide-react'
import useConfirmModalStore from '../store/useConfirmModalStore'
import styles from './ConfirmModal.module.css'

function ConfirmModal() {
  const { isOpen, message, onConfirm, onCancel, close } = useConfirmModalStore()
  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)

  const handleConfirm = useCallback((): void => {
    close()
    // Call onConfirm after closing to ensure modal is dismissed first
    if (onConfirm) {
      // Use setTimeout to ensure state update completes first
      setTimeout(() => {
        onConfirm()
      }, 0)
    }
  }, [close, onConfirm])

  const handleCancel = useCallback((): void => {
    close()
    // Call onCancel after closing to ensure modal is dismissed first
    if (onCancel) {
      // Use setTimeout to ensure state update completes first
      setTimeout(() => {
        onCancel()
      }, 0)
    }
  }, [close, onCancel])

  // Focus management and keyboard handling
  useEffect(() => {
    if (isOpen) {
      // Focus the confirm button by default
      confirmButtonRef.current?.focus()
      
      const handleEscape = (e: KeyboardEvent): void => {
        if (e.key === 'Escape') {
          handleCancel()
        }
      }
      
      document.addEventListener('keydown', handleEscape)
      return () => {
        document.removeEventListener('keydown', handleEscape)
      }
    }
    return undefined
  }, [isOpen, handleCancel])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  if (!isOpen) {
    return null
  }

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>): void => {
    // Only close if clicking the overlay itself, not the modal content
    if (e.target === e.currentTarget) {
      handleCancel()
    }
  }

  return (
    <>
      <div className={styles.overlay} onClick={handleOverlayClick} />
      <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
        <div className={styles.header}>
          <div className={styles.iconContainer}>
            <AlertTriangle size={24} className={styles.icon} />
          </div>
          <h2 id="confirm-modal-title" className={styles.title}>Confirm Action</h2>
          <button
            className={styles.closeButton}
            onClick={handleCancel}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>
        <div className={styles.content}>
          <p className={styles.message}>{message}</p>
        </div>
        <div className={styles.actions}>
          <button
            ref={cancelButtonRef}
            className={styles.buttonCancel}
            onClick={handleCancel}
          >
            Cancel
          </button>
          <button
            ref={confirmButtonRef}
            className={styles.buttonConfirm}
            onClick={handleConfirm}
            autoFocus
          >
            Confirm
          </button>
        </div>
      </div>
    </>
  )
}

export default ConfirmModal

