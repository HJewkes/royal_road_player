import { create } from 'zustand'
import type { Book, Chapter, ChunkMetadata, GenerateChunksResult, ChunkChapterResult } from '../types'

interface AudiobookStore {
  // Current book state
  currentBook: Book | null
  books: Book[]
  
  // Current chapter state
  currentChapter: Chapter | null
  chapters: Chapter[]
  
  // Chunk metadata for current chapter
  chunkMetadata: ChunkMetadata[] | null
  chapterTextLength: number
  
  // Actions
  setBooks: (books: Book[]) => void
  
  setCurrentBook: (book: Book) => Promise<void>
  
  setCurrentChapter: (chapterNumber: number, startTime?: number) => Promise<void>
  
  loadChunkMetadata: (chapterNumber: number) => Promise<void>
  
  refreshBook: () => Promise<void>
  
  chunkChapter: (chapterNumber: number, chunkDurationMinutes?: number) => Promise<ChunkChapterResult>
  
  generateChunks: (chapterNumber: number, chunkIndices?: number[] | null) => Promise<GenerateChunksResult>
  
  generateSingleChunk: (chapterNumber: number, chunkIndex: number) => Promise<GenerateChunksResult>
}

const useAudiobookStore = create<AudiobookStore>((set, get) => ({
  // Current book state
  currentBook: null,
  books: [],
  
  // Current chapter state
  currentChapter: null,
  chapters: [],
  
  // Chunk metadata for current chapter
  chunkMetadata: null,
  chapterTextLength: 0,
  
  // Actions
  setBooks: (books: Book[]) => {
    set({ books })
  },
  
  setCurrentBook: async (book: Book) => {
    set({ currentBook: book })
    
    // Fetch full chapter data
    try {
      const chaptersResponse = await fetch(`/api/books/${book.id}/chapters`)
      if (chaptersResponse.ok) {
        const chaptersData = await chaptersResponse.json() as { chapters?: Chapter[] }
        const chapters = chaptersData.chapters || []
        set({ chapters })
        
        // If book has chapters, load the first one by default
        if (chapters.length > 0 && !get().currentChapter) {
          const firstChapter = chapters[0]
          if (firstChapter) {
            await get().setCurrentChapter(firstChapter.chapter_number, 0)
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
    if (chapter) {
      set({ currentChapter: { ...chapter, startTime } })
      
      // Load chunk metadata if chapter is chunked
      if (chapter.is_chunked && chapter.chunk_count > 0) {
        await get().loadChunkMetadata(chapter.chapter_number)
      } else {
        set({ chunkMetadata: null, chapterTextLength: 0 })
      }
    }
  },
  
  loadChunkMetadata: async (chapterNumber: number) => {
    const { currentBook } = get()
    if (!currentBook || !chapterNumber) return
    
    try {
      const response = await fetch(
        `/api/books/${currentBook.id}/chapters/${chapterNumber}/chunks`
      )
      if (!response.ok) {
        throw new Error(`Failed to load chunk metadata: ${response.statusText}`)
      }
      const data = await response.json() as { chunks?: ChunkMetadata[]; text_length?: number }
      set({
        chunkMetadata: data.chunks || [],
        chapterTextLength: data.text_length || 0,
      })
    } catch (error) {
      console.error('Failed to load chunk metadata:', error)
      set({ chunkMetadata: null, chapterTextLength: 0 })
    }
  },
  
  refreshBook: async () => {
    const { currentBook } = get()
    if (!currentBook) return
    
    try {
      // Fetch book info
      const bookResponse = await fetch(`/api/books/${currentBook.id}`)
      if (!bookResponse.ok) {
        throw new Error(`Failed to fetch book: ${bookResponse.statusText}`)
      }
      const bookData = await bookResponse.json() as Book
      
      // Fetch full chapter data
      const chaptersResponse = await fetch(`/api/books/${currentBook.id}/chapters`)
      if (!chaptersResponse.ok) {
        throw new Error(`Failed to fetch chapters: ${chaptersResponse.statusText}`)
      }
      const chaptersData = await chaptersResponse.json() as { chapters?: Chapter[] }
      const chapters = chaptersData.chapters || []
      
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
          
          // Reload chunk metadata if needed
          if (updatedChapter.is_chunked && updatedChapter.chunk_count > 0) {
            await get().loadChunkMetadata(updatedChapter.chapter_number)
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
    
    const response = await fetch('/api/chapters/chunk', {
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
    
    const response = await fetch('/api/chunks/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: currentBook.id,
        chapter_number: chapterNumber,
        chunk_indices: chunkIndices,
      }),
    })
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string; error?: string }
      throw new Error(error.detail || error.error || 'Failed to generate chunks')
    }
    
    const data = await response.json() as { status: string; result?: GenerateChunksResult; error?: string }
    if (data.status === 'error') {
      throw new Error(data.error || 'Failed to generate chunks')
    }
    
    await get().refreshBook()
    return data.result as GenerateChunksResult
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

