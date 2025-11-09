// Type definitions for the audiobook application

export interface Book {
  id: string
  title: string
  author: string | null
  url: string
  chapter_count: number
  path: string
  chapters?: Chapter[]
  stats?: BookStats
}

export interface BookStats {
  book_id: string
  title: string
  total_chapters: number
  chapters_with_text: number
  chapters_with_audio: number
  chapters_chunked: number
  total_chunks: number
  completed_chunks: number
  pending_chunks: number
}

export interface ChapterStats {
  book_id: string
  chapter_number: number
  title: string
  has_text: boolean
  word_count: number | null
  text_size: number | null
  is_chunked: boolean
  chunk_count: number
  has_audio: boolean
  total_chunks: number
  completed_chunks: number
  pending_chunks: number
  failed_chunks: number
}

export interface Chapter {
  id?: string | null
  chapter_number: number
  title: string
  number?: number | null  // Royal Road number
  url?: string | null
  text_path?: string | null
  audio_urls?: string[]  // Changed from audio_paths
  is_chunked: boolean
  chunk_count: number
  has_audio: boolean
  scraped: boolean  // Maps to has_text
  word_count?: number | null
  duration_seconds?: number | null
  book_id?: string
  startTime?: number
  stats?: ChapterStats  // New nested stats
}

export interface ChunkMetadata {
  index: number
  text_start: number
  text_end: number
  text_length: number
  status: 'completed' | 'pending' | 'running' | 'failed'
  path?: string
  url?: string
  filename?: string
  text?: string  // Actual text content of the chunk
  generation_time_seconds?: number
  audio_duration_seconds?: number  // Duration of the audio file in seconds
  audio_start_time?: number | null  // Start time in seconds (cumulative, from backend)
  audio_end_time?: number | null  // End time in seconds (cumulative, from backend)
}

export interface ChunksData {
  chunks: ChunkMetadata[]
  chapter_number: number
  chapter_title: string  // Keep for display purposes
  text_length: number
}

export interface GenerateChunksResult {
  generated: number
  skipped: number
  failed: number
  chunk_count?: number
}

export interface ChunkChapterResult {
  chunk_count: number
}

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  message: string
  type: ToastType
  duration?: number
}

