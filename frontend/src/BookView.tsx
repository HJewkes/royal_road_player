import { useState, useEffect, useMemo, useCallback } from 'react'
import { Button, ButtonText, Badge, BadgeText, Progress } from '@titan-design/react-ui'
import { useToastContext, useAudioContext } from './App'
import { BookViewSkeleton } from './Skeleton'
import { Tooltip } from './Tooltip'
import { ChapterSummary, ChapterValidationResult } from './types'

// Header info passed up to App for unified header
export interface BookHeaderInfo {
  fictionName: string
  fictionId: string
  bookNumber: number
  chapterCount: number
  normalizedCount: number
  chunkedCount: number
  audioCompleteCount: number
  exportedCount: number
  eta: string | null
  isProcessing: boolean
  sourceUrl: string | null
  onNormalize: () => void
  onChunk: () => void
  onGenerate: () => void
  onExport: () => void
}

interface BookViewProps {
  fictionId: string
  bookNumber: number
  onBack: () => void
  onHeaderUpdate?: (info: BookHeaderInfo) => void
}

// Clean chapter title by removing redundant prefixes since we show chapter number separately
function cleanChapterTitle(title: string): string {
  if (!title) return ''
  
  // Remove patterns like:
  // "Book 7 - Chapter 13: Title" -> "Title"
  // "7.1 - The First Cut" -> "The First Cut"
  // "Chapter 13: Title" -> "Title"
  // "13 - Title" -> "Title"
  
  let cleaned = title
  
  // Remove "Book X - " or "Book X, " prefix
  cleaned = cleaned.replace(/^Book\s+\d+\s*[-–,]\s*/i, '')
  
  // Remove "Chapter X: " or "Chapter X - " prefix
  cleaned = cleaned.replace(/^Chapter\s+\d+\s*[:.\-–]\s*/i, '')
  
  // Remove leading number prefix like "7.1 - " or "13 - " or "1: " (handles decimals)
  cleaned = cleaned.replace(/^\d+(\.\d+)?\s*[-–:\.]\s*/, '')
  
  // If nothing left after cleaning, return original
  return cleaned.trim() || title
}

// Calculate ETA based on processing rate
function useETA(chapters: ChapterSummary[]) {
  return useMemo(() => {
    const totalChunks = chapters.reduce((sum, c) => sum + (c.chunk_count || 0), 0)
    const completedChunks = chapters.reduce((sum, c) => sum + (c.chunks_completed || 0), 0)
    const remainingChunks = totalChunks - completedChunks

    if (remainingChunks === 0) return null

    // Estimate ~3 seconds per chunk (adjust based on your TTS speed)
    const secondsPerChunk = 3
    const remainingSeconds = remainingChunks * secondsPerChunk

    if (remainingSeconds < 60) {
      return `~${Math.ceil(remainingSeconds)}s`
    } else if (remainingSeconds < 3600) {
      return `~${Math.ceil(remainingSeconds / 60)}m`
    } else {
      const hours = Math.floor(remainingSeconds / 3600)
      const mins = Math.ceil((remainingSeconds % 3600) / 60)
      return `~${hours}h ${mins}m`
    }
  }, [chapters])
}

function BookView({ fictionId, bookNumber, onHeaderUpdate }: BookViewProps) {
  const toast = useToastContext()
  const { playAudio } = useAudioContext()
  const [chapters, setChapters] = useState<ChapterSummary[]>([])
  const [fictionName, setFictionName] = useState<string>('')
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState<string | null>(null)
  const [validationResults, setValidationResults] = useState<Record<number, ChapterValidationResult>>({})

  const eta = useETA(chapters)
  
  // Memoize bulk action handlers for header
  const normalizeAll = useCallback(async () => {
    setProcessing('normalize-all')
    try {
      const res = await fetch('/api/normalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber }),
      })
      if (res.ok) {
        toast.success('All chapters normalized')
      }
      await loadChapters()
    } finally {
      setProcessing(null)
    }
  }, [fictionId, bookNumber, toast])

  const chunkAll = useCallback(async () => {
    setProcessing('chunk-all')
    try {
      const res = await fetch('/api/chunk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber }),
      })
      if (res.ok) {
        toast.success('All chapters chunked')
      }
      await loadChapters()
    } finally {
      setProcessing(null)
    }
  }, [fictionId, bookNumber, toast])

  const generateAll = useCallback(async () => {
    setProcessing('generate-all')
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber }),
      })
      if (res.ok) {
        toast.info('Generation queued', 'All chapters queued for audio generation')
      }
    } finally {
      setProcessing(null)
    }
  }, [fictionId, bookNumber, toast])

  const exportAll = useCallback(async () => {
    setProcessing('export-all')
    try {
      for (const chapter of chapters.filter(c => c.is_audio_complete && !c.is_exported)) {
        await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber, chapter_number: chapter.chapter_number }),
        })
      }
      toast.success('All chapters exported')
      await loadChapters()
    } finally {
      setProcessing(null)
    }
  }, [fictionId, bookNumber, chapters, toast])

  // Load chapters function (needs to be defined before useEffect)
  const loadChapters = useCallback(async () => {
    try {
      const res = await fetch(`/api/books/${fictionId}/${bookNumber}/chapters`)
      if (res.ok) {
        const data = await res.json()
        setChapters(data)
      }
    } catch (e) {
      console.error('Failed to load chapters:', e)
    } finally {
      setLoading(false)
    }
  }, [fictionId, bookNumber])

  const loadFictionInfo = useCallback(async () => {
    try {
      const res = await fetch('/api/fictions')
      if (res.ok) {
        const fictions = await res.json()
        const fiction = fictions.find((f: { fiction_id: string; name: string }) => f.fiction_id === fictionId)
        if (fiction) {
          setFictionName(fiction.name)
        }
      }
    } catch (e) {
      console.error('Failed to load fiction info:', e)
    }
  }, [fictionId])

  const loadBookInfo = useCallback(async () => {
    try {
      const res = await fetch(`/api/books/${fictionId}/${bookNumber}`)
      if (res.ok) {
        const book = await res.json()
        // Use source_url from book, or construct from fiction_id
        if (book.source_url) {
          setSourceUrl(book.source_url)
        } else {
          // Fallback: construct Royal Road URL from fiction_id
          setSourceUrl(`https://www.royalroad.com/fiction/${fictionId}`)
        }
      }
    } catch (e) {
      console.error('Failed to load book info:', e)
      // Fallback: construct Royal Road URL from fiction_id
      setSourceUrl(`https://www.royalroad.com/fiction/${fictionId}`)
    }
  }, [fictionId, bookNumber])

  useEffect(() => {
    loadFictionInfo()
    loadBookInfo()
    loadChapters()
    const interval = setInterval(loadChapters, 3000)
    return () => clearInterval(interval)
  }, [fictionId, bookNumber, loadFictionInfo, loadBookInfo, loadChapters])
  
  // Update header info for parent App
  const normalizedCount = chapters.filter(c => c.is_normalized).length
  const chunkedCount = chapters.filter(c => c.is_chunked).length
  const audioCompleteCount = chapters.filter(c => c.is_audio_complete).length
  const exportedCount = chapters.filter(c => c.is_exported).length
  
  useEffect(() => {
    if (onHeaderUpdate && fictionName) {
      onHeaderUpdate({
        fictionName,
        fictionId,
        bookNumber,
        chapterCount: chapters.length,
        normalizedCount,
        chunkedCount,
        audioCompleteCount,
        exportedCount,
        eta,
        isProcessing: processing !== null,
        sourceUrl,
        onNormalize: normalizeAll,
        onChunk: chunkAll,
        onGenerate: generateAll,
        onExport: exportAll,
      })
    }
  }, [fictionName, fictionId, bookNumber, chapters.length, normalizedCount, chunkedCount, audioCompleteCount, exportedCount, eta, processing, sourceUrl, onHeaderUpdate, normalizeAll, chunkAll, generateAll, exportAll])

  const normalizeChapter = async (chapterNumber: number) => {
    setProcessing(`normalize-${chapterNumber}`)
    try {
      const res = await fetch('/api/normalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber, chapter_numbers: [chapterNumber] }),
      })
      if (res.ok) {
        toast.success('Normalized', `Chapter ${chapterNumber} has been normalized`)
      } else {
        toast.error('Normalization failed', 'Please try again')
      }
      await loadChapters()
    } finally {
      setProcessing(null)
    }
  }

  const chunkChapter = async (chapterNumber: number) => {
    setProcessing(`chunk-${chapterNumber}`)
    try {
      const res = await fetch('/api/chunk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber, chapter_numbers: [chapterNumber] }),
      })
      if (res.ok) {
        toast.success('Chunked', `Chapter ${chapterNumber} has been split into chunks`)
      } else {
        toast.error('Chunking failed', 'Please try again')
      }
      await loadChapters()
    } finally {
      setProcessing(null)
    }
  }

  const generateChapter = async (chapterNumber: number) => {
    setProcessing(`generate-${chapterNumber}`)
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber, chapter_numbers: [chapterNumber] }),
      })
      if (res.ok) {
        toast.info('Generation queued', `Chapter ${chapterNumber} audio generation started`)
      } else {
        toast.error('Generation failed', 'Please try again')
      }
    } finally {
      setProcessing(null)
    }
  }

  const validateChapter = async (chapterNumber: number) => {
    setProcessing(`validate-${chapterNumber}`)
    try {
      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber, chapter_number: chapterNumber }),
      })
      if (res.ok) {
        const result = await res.json()
        setValidationResults(prev => ({ ...prev, [chapterNumber]: result }))
        if (result.pass_rate >= 90) {
          toast.success('Validation passed', `${result.pass_rate.toFixed(0)}% quality score`)
        } else if (result.pass_rate >= 70) {
          toast.warning('Validation concerns', `${result.pass_rate.toFixed(0)}% quality score`)
        } else {
          toast.error('Validation issues', `Only ${result.pass_rate.toFixed(0)}% quality score`)
        }
      }
    } finally {
      setProcessing(null)
    }
  }

  const exportChapter = async (chapterNumber: number) => {
    setProcessing(`export-${chapterNumber}`)
    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber, chapter_number: chapterNumber }),
      })
      if (res.ok) {
        toast.success('Exported', `Chapter ${chapterNumber} M4B created`)
      } else {
        toast.error('Export failed', 'Please try again')
      }
      await loadChapters()
    } finally {
      setProcessing(null)
    }
  }

  const checkRoyalRoad = async () => {
    setProcessing('check-rr')
    try {
      const res = await fetch(`/api/series/${fictionId}?refresh=true`)
      if (!res.ok) throw new Error('Failed to fetch')
      const books: Array<{ book_number: number; chapter_count: number; chapters_on_royal_road?: number | null }> = await res.json()
      const thisBook = books.find(b => b.book_number === bookNumber)
      if (thisBook?.chapters_on_royal_road != null && thisBook.chapters_on_royal_road > chapters.length) {
        const newCount = thisBook.chapters_on_royal_road - chapters.length
        toast.info('New chapters available', `${newCount} new chapter${newCount !== 1 ? 's' : ''} on Royal Road. Download the book again to fetch them.`)
      } else {
        toast.success('Royal Road checked', 'All chapters are up to date')
      }
    } catch (err) {
      toast.error('Check failed', 'Could not fetch Royal Road data')
      console.error('Royal Road check failed:', err)
    } finally {
      setProcessing(null)
    }
  }

  const backfillTitles = async () => {
    setProcessing('backfill')
    try {
      const res = await fetch('/api/backfill/titles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fiction_id: fictionId, book_number: bookNumber }),
      })
      if (res.ok) {
        const result = await res.json()
        if (result.updated > 0) {
          toast.success('Titles updated', `Updated ${result.updated} chapter titles`)
        } else {
          toast.info('No updates', 'All titles are already up to date')
        }
        await loadChapters()
      } else {
        toast.error('Backfill failed', 'Could not update titles')
      }
    } catch (e) {
      toast.error('Backfill failed', 'Network error')
    } finally {
      setProcessing(null)
    }
  }

  // Check if any chapters have generic titles (need backfill)
  const hasGenericTitles = useMemo(() => {
    return chapters.some(c => /^Chapter\s+\d+$/i.test(c.title))
  }, [chapters])

  const handlePlayAudio = (chapterNumber: number, title: string) => {
    const src = `/api/audio/preview/${fictionId}/${bookNumber}/${chapterNumber}`
    playAudio(src, `Chapter ${chapterNumber}: ${title}`)
  }

  if (loading) {
    return <BookViewSkeleton />
  }

  return (
    <div className="max-w-[1100px] mx-auto animate-[fadeIn_var(--duration-slow)_var(--ease-out)]">
      {/* Action bar: backfill titles + check Royal Road */}
      <div className="flex items-center gap-4 flex-wrap mb-4">
        {hasGenericTitles && (
          <div className="flex items-center gap-3 py-3 px-4 bg-interactive-hover border border-border-subtle rounded-md text-sm text-text-secondary">
            <span>Some chapters have generic titles.</span>
            <Button
              variant="solid"
              color="secondary"
              size="sm"
              onPress={backfillTitles}
              isDisabled={processing === 'backfill'}
            >
              <ButtonText>{processing === 'backfill' ? 'Updating...' : '↻ Refresh Titles'}</ButtonText>
            </Button>
          </div>
        )}
        <Button
          variant="outline"
          color="secondary"
          size="sm"
          onPress={() => void checkRoyalRoad()}
          isDisabled={processing === 'check-rr'}
        >
          <ButtonText>{processing === 'check-rr' ? '...' : '↻ Check Royal Road'}</ButtonText>
        </Button>
      </div>

      {/* Chapter table */}
      <div className="chapter-table">
        <div className="chapter-header">
          <div className="col-chapter">Chapter</div>
          <div className="col-status">Status</div>
          <div className="col-actions">Actions</div>
        </div>

        {chapters.map((chapter, index) => {
          const validation = validationResults[chapter.chapter_number]
          const isProcessingThis = processing?.includes(`-${chapter.chapter_number}`)

          // Determine row state for styling
          const rowState = chapter.is_exported ? 'exported'
            : chapter.is_audio_complete ? 'audio-complete'
            : (chapter.is_chunked && chapter.chunks_completed > 0) ? 'generating'
            : chapter.is_chunked ? 'ready'
            : chapter.is_normalized ? 'chunked'
            : 'pending'

          return (
            <div
              key={chapter.chapter_number}
              className={`chapter-row state-${rowState} ${isProcessingThis ? 'processing' : ''}`}
              style={{ animationDelay: `${index * 30}ms` }}
            >
              {/* Chapter Info */}
              <div className="col-chapter">
                <span className="font-mono font-medium text-sm text-text-tertiary min-w-[2.5ch] text-right shrink-0">{chapter.chapter_number}</span>
                <Tooltip content={cleanChapterTitle(chapter.title)} position="right" delay={500}>
                  <span className="text-sm text-text-primary whitespace-nowrap overflow-hidden text-ellipsis">{cleanChapterTitle(chapter.title)}</span>
                </Tooltip>
              </div>

              {/* Status Column - Shows progress or completion state */}
              <div className="col-status">
                {chapter.is_exported ? (
                  <Badge color="success" variant="subtle"><BadgeText>✓ Exported</BadgeText></Badge>
                ) : chapter.is_audio_complete ? (
                  <Badge color="info" variant="subtle"><BadgeText>✓ {chapter.chunk_count} chunks</BadgeText></Badge>
                ) : chapter.is_chunked ? (
                  <div className="flex items-center gap-2 w-full">
                    <Progress value={chapter.progress_percent} size="sm" color="primary" className="max-w-[60px]" />
                    <span className="font-mono text-xs text-brand-primary-light min-w-[5ch]">
                      {chapter.chunks_completed}/{chapter.chunk_count}
                    </span>
                  </div>
                ) : chapter.is_normalized ? (
                  <Badge color="default" variant="subtle"><BadgeText>Ready to chunk</BadgeText></Badge>
                ) : (
                  <Badge color="default" variant="subtle"><BadgeText>Not processed</BadgeText></Badge>
                )}
              </div>

              {/* Actions Column - Contextual actions */}
              <div className="col-actions">
                {chapter.is_exported ? (
                  <button
                    className="action-btn play"
                    onClick={() => handlePlayAudio(chapter.chapter_number, cleanChapterTitle(chapter.title))}
                    title="Preview audio"
                  >
                    ▶
                  </button>
                ) : chapter.is_audio_complete ? (
                  <div className="flex items-center gap-2">
                    <button
                      className="action-btn play"
                      onClick={() => handlePlayAudio(chapter.chapter_number, cleanChapterTitle(chapter.title))}
                      title="Preview audio"
                    >
                      ▶
                    </button>
                    {!validation && (
                      <button
                        className="action-btn"
                        onClick={() => validateChapter(chapter.chapter_number)}
                        disabled={processing === `validate-${chapter.chapter_number}`}
                        title="Validate audio"
                      >
                        {processing === `validate-${chapter.chapter_number}` ? '...' : '?'}
                      </button>
                    )}
                    {validation && (
                      <Badge
                        color={validation.pass_rate >= 90 ? 'success' : validation.pass_rate >= 70 ? 'warning' : 'error'}
                        variant="subtle"
                        size="sm"
                      >
                        <BadgeText>{validation.pass_rate.toFixed(0)}%</BadgeText>
                      </Badge>
                    )}
                    <button
                      className="action-btn export"
                      onClick={() => exportChapter(chapter.chapter_number)}
                      disabled={processing === `export-${chapter.chapter_number}`}
                      title="Export M4B"
                    >
                      {processing === `export-${chapter.chapter_number}` ? '...' : '↓'}
                    </button>
                  </div>
                ) : chapter.is_chunked ? (
                  chapter.chunks_completed === 0 ? (
                    <button
                      className="action-btn generate"
                      onClick={() => generateChapter(chapter.chapter_number)}
                      disabled={processing === `generate-${chapter.chapter_number}`}
                      title="Generate audio"
                    >
                      {processing === `generate-${chapter.chapter_number}` ? '...' : 'Generate'}
                    </button>
                  ) : (
                    <span className="font-mono text-xs text-brand-primary-light animate-[statusPulse_1.5s_ease-in-out_infinite]">Generating...</span>
                  )
                ) : chapter.is_normalized ? (
                  <button
                    className="action-btn"
                    onClick={() => chunkChapter(chapter.chapter_number)}
                    disabled={processing === `chunk-${chapter.chapter_number}`}
                    title="Split into chunks"
                  >
                    {processing === `chunk-${chapter.chapter_number}` ? '...' : 'Chunk'}
                  </button>
                ) : (
                  <button
                    className="action-btn"
                    onClick={() => normalizeChapter(chapter.chapter_number)}
                    disabled={processing === `normalize-${chapter.chapter_number}`}
                    title="Normalize text"
                  >
                    {processing === `normalize-${chapter.chapter_number}` ? '...' : 'Normalize'}
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default BookView
