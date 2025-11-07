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
  scraping?: {
    total_chapters: number
    scraped_chapters: number
    last_scraped: string | null
  }
  tts?: {
    total_chapters: number
    generated_chapters: number
    last_generated: string | null
  }
  chunks?: {
    total_chunks: number
    chunks_by_chapter: Record<string, number>
  }
}

export interface Chapter {
  id?: number
  chapter_number: number
  title: string
  text_path?: string
  audio_paths?: string[]
  is_chunked: boolean
  chunk_count: number
  has_audio: boolean
  scraped: boolean
  word_count?: number
  duration_seconds?: number | null
  book_id?: string
  startTime?: number
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
  generation_time_seconds?: number
  flagged?: boolean
}

export interface ChunksData {
  chunks: ChunkMetadata[]
  chapter_title: string
  text_length: number
}

export interface Job {
  id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  book_id?: string
  chapter_title?: string
  message?: string
  created_at?: string
  updated_at?: string
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

