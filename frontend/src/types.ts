// API response types

// Status enums (matches backend)
export type BookStatus = 
  | 'available'
  | 'not_downloaded'
  | 'downloaded'
  | 'processing'
  | 'ready'
  | 'exported'

export type ChapterStatus =
  | 'not_downloaded'
  | 'downloaded'
  | 'normalized'
  | 'chunked'
  | 'processing'
  | 'audio_complete'
  | 'validated'
  | 'validation_failed'
  | 'exported'

export type DownloadStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'

export interface BookSummary {
  fiction_id: string
  book_number: number
  title: string
  status: string
  progress_percent: number
  chapter_count: number
  chapters_complete: number  // Audio complete
  chapters_normalized: number
  chapters_chunked: number
}

export interface ChapterSummary {
  chapter_number: number
  title: string
  status: string
  progress_percent: number
  chunk_count: number
  chunks_completed: number
  is_normalized: boolean
  is_chunked: boolean
  is_audio_complete: boolean
  is_exported: boolean
}

export interface Chapter {
  chapter_number: number
  title: string
  source_url: string | null
  is_downloaded: boolean
  is_normalized: boolean
  is_chunked: boolean
  chunks_completed: number
  chunks_failed: number
  is_audio_complete: boolean
  is_validated: boolean
  validation_passed: boolean | null
  is_exported: boolean
  status: string
  progress_percent: number
  chunk_count: number
}

export interface CurrentJobInfo {
  fiction_id: string
  book_number: number
  chapter_number: number
  chunk_index: number
  chapter_title?: string
}

export interface QueuedChapterInfo {
  fiction_id: string
  fiction_name?: string
  book_number: number
  chapter_number: number
  chapter_title?: string
  pending_chunks: number
  total_chunks: number
}

export interface QueueStatus {
  pending: number
  running: number
  completed: number
  failed: number
  is_processing: boolean
  current_job: string | null
  current_job_info: CurrentJobInfo | null
  queued_chapters: QueuedChapterInfo[]
  total: number
}

export interface ChapterQueueStatus {
  chapter_number: number
  total: number
  pending: number
  running: number
  completed: number
  failed: number
  progress_percent: number
  is_complete: boolean
}

export interface ChunkValidationResult {
  chunk_index: number
  similarity: number
  passed: boolean
  issues: string[]
  expected_text?: string
  transcribed_text?: string
}

export interface ChapterValidationResult {
  chapter_number: number
  validated_at: string
  total_chunks: number
  passed_chunks: number
  failed_chunks: number
  chunks: Record<string, ChunkValidationResult>
  pass_rate: number
}

export interface OperationResult {
  success: boolean
  message: string
  data?: Record<string, unknown>
}

// Download queue types
export interface DownloadJob {
  job_id: string
  fiction_id: string
  book_number: number
  status: DownloadStatus
  message: string
  progress_chapters: number
  total_chapters: number
  progress_percent: number
}export interface DownloadQueueStatus {
  pending: number
  running: number
  completed: number
  failed: number
  is_processing: boolean
  jobs: DownloadJob[]
}