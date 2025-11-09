import { useState } from 'react'
import { ChevronDown, FileText, Music, Volume2 } from 'lucide-react'
import useAudiobookStore from '../store/useAudiobookStore'
import styles from './ChapterList.module.css'

function ChapterList() {
  const { chapters, currentChapter, setCurrentChapter } = useAudiobookStore()
  const [isOpen, setIsOpen] = useState(false)
  
  const escapeHtml = (text: string): string => {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }

  const selectedChapter = currentChapter || chapters[0]

  return (
    <div className={styles.dropdownContainer}>
      <button
        className={styles.dropdownButton}
        onClick={() => { setIsOpen(!isOpen) }}
        aria-expanded={isOpen}
      >
        <span className={styles.dropdownLabel}>
          {selectedChapter ? (
            <>
              <span className={styles.chapterNumber}>Chapter {selectedChapter.chapter_number}</span>
              <span className={styles.chapterTitle} dangerouslySetInnerHTML={{ __html: escapeHtml(selectedChapter.title) }} />
              <span className={styles.statusIcons}>
                {selectedChapter.scraped && <FileText size={14} className={styles.statusIcon} />}
                {selectedChapter.has_audio && <Music size={14} className={styles.statusIcon} />}
                {selectedChapter.is_chunked && selectedChapter.chunk_count > 0 && (
                  <span className={styles.chunkCount} title={`${selectedChapter.chunk_count} chunks`}>
                    <Volume2 size={14} className={styles.statusIcon} />
                    {selectedChapter.chunk_count}
                  </span>
                )}
              </span>
            </>
          ) : (
            'Select Chapter'
          )}
        </span>
        <ChevronDown size={16} className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`} />
      </button>

      {isOpen && (
        <>
          <div className={styles.dropdownOverlay} onClick={() => { setIsOpen(false) }} />
          <div className={styles.dropdownMenu}>
            <div className={styles.dropdownHeader}>
              <h3>Chapters ({chapters.length})</h3>
            </div>
            <ul className={styles.chapterList}>
              {chapters.map((chapter) => {
                return (
                  <li
                    key={chapter.chapter_number}
                    className={`${styles.chapterItem} ${chapter.has_audio ? styles.hasAudio : ''} ${
                      chapter.chapter_number === currentChapter?.chapter_number ? styles.active : ''
                    }`}
                    onClick={() => {
                      void setCurrentChapter(chapter.chapter_number, 0)
                      setIsOpen(false)
                    }}
                  >
                    <span className={styles.chapterTitleClickable}>
                      <span className={styles.chapterNumber}>Chapter {chapter.chapter_number}</span>
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
                  </li>
                )
              })}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}

export default ChapterList

