import { create } from 'zustand'
import type { Book, Chapter, ChunkMetadata, GenerateChunksResult, ChunkChapterResult } from '../types'

interface AudiobookStore {
  // Current book state
  currentBook: Book | null
  books: Book[]
  
  // Current chapter state (for viewing/UI)
  currentChapter: Chapter | null
  chapters: Chapter[]
  
  // Playing chapter state (separate from viewing chapter)
  playingChapter: Chapter | null
  
  // Chunk metadata for current chapter (viewing/UI)
  chunkMetadata: ChunkMetadata[] | null
  chapterTextLength: number
  
  // Chunk metadata for playing chapter (audio playback)
  playingChunkMetadata: ChunkMetadata[] | null
  playingChapterTextLength: number
  
  // Actions
  setBooks: (books: Book[]) => void
  
  setCurrentBook: (book: Book) => Promise<void>
  
  setCurrentChapter: (chapterNumber: number, startTime?: number) => Promise<void>
  
  setPlayingChapter: (chapterNumber: number, startTime?: number) => Promise<void>
  
  loadChunkMetadata: (chapterNumber: number) => Promise<void>
  
  loadPlayingChunkMetadata: (chapterNumber: number) => Promise<void>
  
  refreshBook: () => Promise<void>
  
  chunkChapter: (chapterNumber: number, chunkDurationMinutes?: number) => Promise<ChunkChapterResult>
  
  generateChunks: (chapterNumber: number, chunkIndices?: number[] | null) => Promise<GenerateChunksResult>
  
  generateSingleChunk: (chapterNumber: number, chunkIndex: number) => Promise<GenerateChunksResult>
}

const useAudiobookStore = create<AudiobookStore>((set, get) => ({
  // Current book state
  currentBook: null,
  books: [],
  
  // Current chapter state (for viewing/UI)
  currentChapter: null,
  chapters: [],
  
  // Playing chapter state (separate from viewing chapter)
  playingChapter: null,
  
  // Chunk metadata for current chapter (viewing/UI)
  chunkMetadata: null,
  chapterTextLength: 0,
  
  // Chunk metadata for playing chapter (audio playback)
  playingChunkMetadata: null,
  playingChapterTextLength: 0,
  
  // Actions
  setBooks: (books: Book[]) => {
    set({ books })
  },
  
  setCurrentBook: async (book: Book) => {
    set({ currentBook: book })
    
    // Fetch full chapter data (use lightweight mode for performance)
    try {
      const chaptersResponse = await fetch(`/api/books/${book.id}/chapters?lightweight=true`)
      if (chaptersResponse.ok) {
        const chaptersData = await chaptersResponse.json() as { chapters?: Chapter[] }
        const chapters = chaptersData.chapters || []
        set({ chapters })
        
        // If book has chapters, load the first one by default
        if (chapters.length > 0 && !get().currentChapter) {
          const firstChapter = chapters[0]
          if (firstChapter) {
            await get().setCurrentChapter(firstChapter.chapter_number, 0)
            // Also set as playing chapter initially
            await get().setPlayingChapter(firstChapter.chapter_number, 0)
          }
        }
      }
    } catch (error) {
      console.error('Failed to load chapters:', error)
      set({ chapters: [] })
    }
  },
  
  setCurrentChapter: async (chapterNumber: number, startTime = 0) => {
    const { chapters } = get()
    const chapter = chapters.find((c) => c.chapter_number === chapterNumber)
    if (!chapter) {
      console.warn(`Chapter ${chapterNumber} not found in chapters list`)
      return
    }
    
    set({ currentChapter: { ...chapter, startTime } })
    
    // Load chunk metadata if chapter is chunked (regardless of chunk_count)
    // chunk_count might be 0 temporarily or not yet updated
    if (chapter.is_chunked) {
      try {
        await get().loadChunkMetadata(chapter.chapter_number)
      } catch (error) {
        console.error(`Failed to load chunk metadata for chapter ${chapterNumber}:`, error)
        // Don't clear metadata on error - keep existing if any
      }
    } else {
      set({ chunkMetadata: null, chapterTextLength: 0 })
    }
  },
  
  setPlayingChapter: async (chapterNumber: number, startTime = 0) => {
    const { chapters } = get()
    const chapter = chapters.find((c) => c.chapter_number === chapterNumber)
    if (chapter) {
      set({ playingChapter: { ...chapter, startTime } })
      
      // Load chunk metadata for playing chapter if it's chunked
      if (chapter.is_chunked) {
        await get().loadPlayingChunkMetadata(chapter.chapter_number)
      } else {
        set({ playingChunkMetadata: null, playingChapterTextLength: 0 })
      }
    }
  },
  
  loadChunkMetadata: async (chapterNumber: number) => {
    const { currentBook } = get()
    if (!currentBook || !chapterNumber) {
      console.warn(`loadChunkMetadata: Missing currentBook or chapterNumber (book: ${currentBook?.id}, chapter: ${chapterNumber})`)
      return
    }
    
    try {
      // Don't include text by default - it's huge (308KB+) and not needed for most UI
      const response = await fetch(
        `/api/books/${currentBook.id}/chapters/${chapterNumber}/chunks?include_text=false`
      )
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to load chunk metadata: ${response.status} ${response.statusText} - ${errorText}`)
      }
      const data = await response.json() as { chunks?: ChunkMetadata[]; text_length?: number }
      const chunks = data.chunks || []
      const textLength = data.text_length || 0
      
      console.log(`Loaded chunk metadata for chapter ${chapterNumber}: ${chunks.length} chunks, text_length: ${textLength}`)
      
      set({
        chunkMetadata: chunks,
        chapterTextLength: textLength,
      })
    } catch (error) {
      console.error(`Failed to load chunk metadata for chapter ${chapterNumber}:`, error)
      // Only clear metadata if we're sure this chapter shouldn't have chunks
      // Otherwise, keep existing metadata to avoid flickering
      const { currentChapter } = get()
      if (currentChapter?.chapter_number === chapterNumber && !currentChapter.is_chunked) {
        set({ chunkMetadata: null, chapterTextLength: 0 })
      }
    }
  },
  
  loadPlayingChunkMetadata: async (chapterNumber: number) => {
    const { currentBook } = get()
    if (!currentBook || !chapterNumber) return
    
    try {
      // Don't include text by default - it's huge (308KB+) and not needed for audio playback
      const response = await fetch(
        `/api/books/${currentBook.id}/chapters/${chapterNumber}/chunks?include_text=false`
      )
      if (!response.ok) {
        throw new Error(`Failed to load playing chunk metadata: ${response.statusText}`)
      }
      const data = await response.json() as { chunks?: ChunkMetadata[]; text_length?: number }
      set({
        playingChunkMetadata: data.chunks || [],
        playingChapterTextLength: data.text_length || 0,
      })
    } catch (error) {
      console.error('Failed to load playing chunk metadata:', error)
      set({ playingChunkMetadata: null, playingChapterTextLength: 0 })
    }
  },
  
  refreshBook: async () => {
    const { currentBook } = get()
    if (!currentBook || !currentBook.id) {
      console.warn('refreshBook: No currentBook or currentBook.id is missing')
      return
    }
    
    try {
      // Fetch book info with chapters in a single call (optimized)
      // Use lightweight=true (default) for fast stats computation
      const bookResponse = await fetch(`/api/books/${currentBook.id}?include_chapters=true&lightweight=true`)
      if (!bookResponse.ok) {
        throw new Error(`Failed to fetch book: ${bookResponse.statusText}`)
      }
      const bookResponseData = await bookResponse.json() as { book_id?: string; book_title?: string; chapters?: Chapter[]; [key: string]: any }
      
      // Map API response (book_id) to Book interface (id)
      const bookData: Book = {
        id: bookResponseData.book_id || currentBook.id,
        title: bookResponseData.book_title || currentBook.title,
        author: bookResponseData.author || null,
        url: bookResponseData.book_url || currentBook.url,
        chapter_count: bookResponseData.stats?.total_chapters || currentBook.chapter_count,
        path: currentBook.path, // Keep existing path
        stats: bookResponseData.stats,
      }
      
      // Ensure bookData has an id before proceeding
      if (!bookData.id) {
        console.error('refreshBook: Fetched book data missing id field', bookResponseData)
        return
      }
      
      // Chapters are already included in the response (from include_chapters=true)
      const chapters = bookResponseData.chapters || []
      
      set({ 
        currentBook: bookData,
        chapters: chapters,
      })
      
      // Update current chapter if it exists
      const { currentChapter } = get()
      if (currentChapter) {
        const updatedChapter = chapters.find(
          (c) => c.chapter_number === currentChapter.chapter_number
        )
        if (updatedChapter) {
          // Preserve startTime if it exists
          const startTime = currentChapter.startTime || 0
          set({ currentChapter: { ...updatedChapter, startTime } })
          
          // Reload chunk metadata if chapter is chunked (regardless of chunk_count)
          // chunk_count might be 0 temporarily or not yet updated
          if (updatedChapter.is_chunked) {
            try {
              // Ensure currentBook is still set before loading metadata
              const { currentBook: bookCheck } = get()
              if (bookCheck && bookCheck.id) {
                await get().loadChunkMetadata(updatedChapter.chapter_number)
              } else {
                console.warn(`refreshBook: Skipping chunk metadata load - currentBook.id is missing`)
              }
            } catch (error) {
              console.error(`Failed to load chunk metadata in refreshBook for chapter ${updatedChapter.chapter_number}:`, error)
              // Don't clear existing metadata on error - keep it if available
            }
          } else {
            // Clear chunk metadata if chapter is no longer chunked
            set({ chunkMetadata: null, chapterTextLength: 0 })
          }
        }
      }
    } catch (error) {
      console.error('Failed to refresh book:', error)
    }
  },
  
  chunkChapter: async (chapterNumber: number, chunkDurationMinutes = 1.0): Promise<ChunkChapterResult> => {
    const { currentBook } = get()
    if (!currentBook) throw new Error('No book selected')
    
    // Use rechunk endpoint to properly clear old chunks before creating new ones
    const response = await fetch('/api/chapters/rechunk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: currentBook.id,
        chapter_number: chapterNumber,
        chunk_duration_minutes: chunkDurationMinutes,
      }),
    })
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string; error?: string }
      throw new Error(error.detail || error.error || 'Failed to chunk chapter')
    }
    
    const data = await response.json() as { status: string; result?: ChunkChapterResult; error?: string }
    if (data.status === 'error') {
      throw new Error(data.error || 'Failed to chunk chapter')
    }
    
    await get().refreshBook()
    return data.result as ChunkChapterResult
  },
  
  generateChunks: async (chapterNumber: number, chunkIndices: number[] | null = null): Promise<GenerateChunksResult> => {
    const { currentBook } = get()
    if (!currentBook) throw new Error('No book selected')
    
    // Queue chunks instead of generating immediately
    const response = await fetch('/api/queue/chunks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: currentBook.id,
        chapter_number: chapterNumber,
        chunk_indices: chunkIndices || undefined, // Convert null to undefined
      }),
    })
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string; error?: string }
      throw new Error(error.detail || error.error || 'Failed to queue chunks')
    }
    
    const data = await response.json() as { status: string; result?: { jobs_added?: number; queue_status?: any }; error?: string }
    if (data.status === 'error') {
      throw new Error(data.error || 'Failed to queue chunks')
    }
    
    const jobsAdded = data.result?.jobs_added || 0
    
    // Reload chunk metadata after a short delay to allow backend to save status updates
    // The backend resets failed chunks to PENDING, so we need to wait for that to complete
    setTimeout(async () => {
      await get().loadChunkMetadata(chapterNumber)
    }, 1000)
    
    // Return a result compatible with GenerateChunksResult
    return {
      generated: jobsAdded,
      skipped: 0,
      failed: 0,
    } as GenerateChunksResult
  },
  
  generateSingleChunk: async (chapterNumber: number, chunkIndex: number): Promise<GenerateChunksResult> => {
    const { currentBook } = get()
    if (!currentBook) throw new Error('No book selected')
    
    const response = await fetch(
      `/api/chunks/${chunkIndex}/generate?book_id=${encodeURIComponent(currentBook.id)}&chapter_number=${chapterNumber}`,
      { method: 'POST' }
    )
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string; error?: string }
      throw new Error(error.detail || error.error || 'Failed to generate chunk')
    }
    
    const data = await response.json() as { status: string; result?: GenerateChunksResult; error?: string }
    if (data.status === 'error') {
      throw new Error(data.error || 'Failed to generate chunk')
    }
    
    await get().refreshBook()
    return data.result as GenerateChunksResult
  },
}))

export default useAudiobookStore

