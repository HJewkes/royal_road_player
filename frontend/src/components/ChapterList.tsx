import { FileText, Music, Volume2 } from 'lucide-react'
import ChapterActions from './ChapterActions'
import useAudiobookStore from '../store/useAudiobookStore'
import styles from './ChapterList.module.css'

function ChapterList() {
  const { chapters, currentChapter, setCurrentChapter } = useAudiobookStore()
  
  const escapeHtml = (text: string): string => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  return (
    <aside className={styles.sidebar}>
      <h3>Chapters</h3>
      <ul className={styles.chapterList}>
        {chapters.map((chapter) => {
          return (
            <li
              key={chapter.chapter_number}
              className={`${styles.chapterItem} ${chapter.has_audio ? styles.hasAudio : ''} ${
                chapter.chapter_number === currentChapter?.chapter_number ? styles.active : ''
              }`}
            >
              <span
                className={styles.chapterTitleClickable}
                onClick={() => { void setCurrentChapter(chapter.chapter_number, 0) }}
              >
                <span dangerouslySetInnerHTML={{ __html: escapeHtml(chapter.title) }} />
                <span className={styles.statusIcons}>
                  {chapter.scraped && <FileText size={14} className={styles.statusIcon} />}
                  {chapter.has_audio && <Music size={14} className={styles.statusIcon} />}
                  {chapter.is_chunked && chapter.chunk_count > 0 && (
                    <span className={styles.chunkCount} title={`${chapter.chunk_count} chunks`}>
                      <Volume2 size={14} className={styles.statusIcon} />
                      {chapter.chunk_count}
                    </span>
                  )}
                </span>
              </span>
              {chapter.chapter_number === currentChapter?.chapter_number && (
                <div className={styles.chapterActions}>
                  <ChapterActions chapter={chapter} />
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

export default ChapterList

