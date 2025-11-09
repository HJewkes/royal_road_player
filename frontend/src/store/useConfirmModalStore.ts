import { create } from 'zustand'

interface ConfirmModalState {
  isOpen: boolean
  message: string
  onConfirm: (() => void) | null
  onCancel: (() => void) | null
  open: (message: string, onConfirm?: () => void, onCancel?: () => void) => void
  close: () => void
}

const useConfirmModalStore = create<ConfirmModalState>((set) => ({
  isOpen: false,
  message: '',
  onConfirm: null,
  onCancel: null,
  
  open: (message: string, onConfirm?: () => void, onCancel?: () => void) => {
    set({
      isOpen: true,
      message,
      onConfirm: onConfirm || null,
      onCancel: onCancel || null,
    })
  },
  
  close: () => {
    set({
      isOpen: false,
      message: '',
      onConfirm: null,
      onCancel: null,
    })
  },
}))

// Helper function that returns a Promise for easier migration from window.confirm()
export const confirm = (message: string): Promise<boolean> => {
  return new Promise((resolve) => {
    useConfirmModalStore.getState().open(
      message,
      () => resolve(true),
      () => resolve(false)
    )
  })
}

export default useConfirmModalStore

