import { useState } from 'react'
import { Scissors, Music, Loader } from 'lucide-react'
import useAudiobookStore from '../store/useAudiobookStore'
import useToastStore from '../store/useToastStore'
import type { Chapter } from '../types'
import styles from './ChapterActions.module.css'

interface ChapterActionsProps {
  chapter: Chapter
}

function ChapterActions({ chapter }: ChapterActionsProps) {
  const { chunkChapter, generateChunks } = useAudiobookStore()
  const toast = useToastStore()
  const [chunking, setChunking] = useState(false)
  const [generating, setGenerating] = useState(false)

  const handleChunkChapter = async (): Promise<void> => {
    if (!chapter.scraped) {
      toast.warning('Chapter must be scraped before chunking')
      return
    }

    if (!window.confirm(`Chunk chapter "${chapter.title}"?`)) {
      return
    }

    setChunking(true)
    try {
      const result = await chunkChapter(chapter.chapter_number, 1.0)
      toast.success(`Chapter chunked successfully! Created ${result.chunk_count} chunks.`)
    } catch (error) {
      console.error('Failed to chunk chapter:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to chunk chapter')
    } finally {
      setChunking(false)
    }
  }

  const handleGenerateChunks = async (): Promise<void> => {
    if (!chapter.is_chunked) {
      toast.warning('Chapter must be chunked before generating audio')
      return
    }

    if (!window.confirm(`Generate audio for all pending chunks in "${chapter.title}"?`)) {
      return
    }

    setGenerating(true)
    try {
      const result = await generateChunks(chapter.chapter_number, null)
      toast.success(`Started generation! Will process ${result.generated + result.skipped + result.failed} chunks.`)
    } catch (error) {
      console.error('Failed to generate chunks:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to generate chunks')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className={styles.chapterActions}>
      {chapter.scraped && !chapter.is_chunked && (
        <button
          className={styles.btnAction}
          onClick={() => { void handleChunkChapter() }}
          disabled={chunking}
          title="Chunk chapter text into segments"
        >
          {chunking ? (
            <>
              <Loader size={14} className={styles.spinner} />
              Chunking...
            </>
          ) : (
            <>
              <Scissors size={14} />
              Chunk Chapter
            </>
          )}
        </button>
      )}
      
      {chapter.is_chunked && (
        <button
          className={styles.btnAction}
          onClick={() => { void handleGenerateChunks() }}
          disabled={generating}
          title="Generate audio for pending chunks"
        >
          {generating ? (
            <>
              <Loader size={14} className={styles.spinner} />
              Generating...
            </>
          ) : (
            <>
              <Music size={14} />
              Generate Audio
            </>
          )}
        </button>
      )}
    </div>
  )
}

export default ChapterActions

