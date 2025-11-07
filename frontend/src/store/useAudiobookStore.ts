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
  
  loadChunkMetadata: (chapterTitle: string) => Promise<void>
  
  refreshBook: () => Promise<void>
  
  chunkChapter: (chapterTitle: string, chunkDurationMinutes?: number) => Promise<ChunkChapterResult>
  
  generateChunks: (chapterTitle: string, chunkIndices?: number[] | null) => Promise<GenerateChunksResult>
  
  generateSingleChunk: (chapterTitle: string, chunkIndex: number) => Promise<GenerateChunksResult>
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
    set({ currentBook: book, chapters: book?.chapters || [] })
    
    // If book has chapters, load the first one by default
    if (book?.chapters && book.chapters.length > 0 && !get().currentChapter) {
      const firstChapter = book.chapters[0]
      if (firstChapter) {
        await get().setCurrentChapter(firstChapter.chapter_number, 0)
      }
    }
  },
  
  setCurrentChapter: async (chapterNumber: number, startTime = 0) => {
    const { chapters } = get()
    const chapter = chapters.find((c) => c.chapter_number === chapterNumber)
    if (chapter) {
      set({ currentChapter: { ...chapter, startTime } })
      
      // Load chunk metadata if chapter is chunked
      if (chapter.is_chunked && chapter.chunk_count > 0) {
        await get().loadChunkMetadata(chapter.title)
      } else {
        set({ chunkMetadata: null, chapterTextLength: 0 })
      }
    }
  },
  
  loadChunkMetadata: async (chapterTitle: string) => {
    const { currentBook } = get()
    if (!currentBook || !chapterTitle) return
    
    try {
      const response = await fetch(
        `/api/books/${currentBook.id}/chapters/${encodeURIComponent(chapterTitle)}/chunks`
      )
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
      const response = await fetch(`/api/books/${currentBook.id}`)
      const bookData = await response.json() as Book
      set({ 
        currentBook: bookData,
        chapters: bookData.chapters || [],
      })
      
      // Update current chapter if it exists
      const { currentChapter } = get()
      if (currentChapter) {
        const updatedChapter = bookData.chapters?.find(
          (c) => c.chapter_number === currentChapter.chapter_number
        )
        if (updatedChapter) {
          // Preserve startTime if it exists
          const startTime = currentChapter.startTime || 0
          set({ currentChapter: { ...updatedChapter, startTime } })
          
          // Reload chunk metadata if needed
          if (updatedChapter.is_chunked && updatedChapter.chunk_count > 0) {
            await get().loadChunkMetadata(updatedChapter.title)
          }
        }
      }
    } catch (error) {
      console.error('Failed to refresh book:', error)
    }
  },
  
  chunkChapter: async (chapterTitle: string, chunkDurationMinutes = 1.0): Promise<ChunkChapterResult> => {
    const { currentBook } = get()
    if (!currentBook) throw new Error('No book selected')
    
    const response = await fetch('/api/chapters/chunk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: currentBook.id,
        chapter_title: chapterTitle,
        chunk_duration_minutes: chunkDurationMinutes,
      }),
    })
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string }
      throw new Error(error.detail || 'Failed to chunk chapter')
    }
    
    const data = await response.json() as { result: ChunkChapterResult }
    await get().refreshBook()
    return data.result
  },
  
  generateChunks: async (chapterTitle: string, chunkIndices: number[] | null = null): Promise<GenerateChunksResult> => {
    const { currentBook } = get()
    if (!currentBook) throw new Error('No book selected')
    
    const response = await fetch('/api/chunks/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: currentBook.id,
        chapter_title: chapterTitle,
        chunk_indices: chunkIndices,
      }),
    })
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string }
      throw new Error(error.detail || 'Failed to generate chunks')
    }
    
    const data = await response.json() as { result: GenerateChunksResult }
    await get().refreshBook()
    return data.result
  },
  
  generateSingleChunk: async (chapterTitle: string, chunkIndex: number): Promise<GenerateChunksResult> => {
    const { currentBook } = get()
    if (!currentBook) throw new Error('No book selected')
    
    const response = await fetch(
      `/api/chunks/${chunkIndex}/generate?book_id=${encodeURIComponent(currentBook.id)}&chapter_title=${encodeURIComponent(chapterTitle)}`,
      { method: 'POST' }
    )
    
    if (!response.ok) {
      const error = await response.json() as { detail?: string }
      throw new Error(error.detail || 'Failed to generate chunk')
    }
    
    const data = await response.json() as { result: GenerateChunksResult }
    await get().refreshBook()
    return data.result
  },
}))

export default useAudiobookStore

