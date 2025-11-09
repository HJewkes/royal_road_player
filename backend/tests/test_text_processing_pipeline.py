"""Test text processing pipeline and save results for inspection."""

import json
from pathlib import Path

import attr
import pytest

from src.controllers.chunking_controller import ChunkingController
from src.text_processing.processor import validate_text_for_tts


def test_process_first_chapter_and_save_results():
    """
    Process the first chapter using the chunking controller
    and save results to a temp directory for inspection.
    """
    # Find the first chapter
    books_dir = Path(__file__).parent.parent.parent / "data" / "books"
    book_dirs = list(books_dir.glob("*"))
    
    if not book_dirs:
        pytest.skip("No books found in data/books")
    
    book_dir = book_dirs[0]
    book_id = book_dir.name.split("(")[-1].rstrip(")")
    
    chapters_dir = book_dir / "chapters"
    chapter_dirs = sorted(chapters_dir.glob("*"))
    
    if not chapter_dirs:
        pytest.skip(f"No chapters found in {book_dir}")
    
    first_chapter_dir = chapter_dirs[0]
    chapter_number = int(first_chapter_dir.name)
    text_file = first_chapter_dir / "text.txt"
    
    if not text_file.exists():
        pytest.skip(f"Text file not found: {text_file}")
    
    # Load original text
    original_text = text_file.read_text(encoding='utf-8')
    
    # Create output directory
    output_dir = Path(__file__).parent.parent.parent / "temp" / "text_processing_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Saving results to: {output_dir}")
    print(f"📖 Processing chapter: {chapter_number}")
    print(f"📝 Original text length: {len(original_text)} characters")
    
    # Use chunking controller to process the chapter (in-memory only)
    print("\n🔧 Processing with ChunkingController (in-memory)...")
    controller = ChunkingController()
    
    try:
        # Normalize text first
        from src.text_processing.processor import UnifiedTextProcessor, ProcessingConfig
        
        config = ProcessingConfig(
            extract_html=False,
            normalize_punctuation=True,
            normalize_acronyms=True,
            normalize_numbers=True,
            normalize_dates=True,
            segment_into_breath_groups=False,
            chunk_for_tts=False,
        )
        processor = UnifiedTextProcessor()
        normalized_text = processor.process_text(original_text, config)
        if isinstance(normalized_text, list):
            normalized_text = '\n\n'.join(normalized_text)
        
        # Create chunks in memory without saving (using normalized text)
        chunks = controller.create_chunks(
            normalized_text=normalized_text,
            book_id=book_id,
            chapter_id=f"{book_id}_{chapter_number}",
            chunk_duration_minutes=1.0,
        )
        
        print(f"   Created {len(chunks)} chunks")
        
        # Extract chunk text and convert to dicts
        chunk_data = []
        chunk_sizes = []
        for chunk in chunks:
            # Extract text from normalized text using positions (positions are relative to normalized text)
            chunk_text = normalized_text[chunk.text_start:chunk.text_end]
            chunk_sizes.append(len(chunk_text))
            
            # Convert chunk to dict (using attr.asdict)
            chunk_dict = attr.asdict(chunk)
            # Convert enum to string for JSON
            chunk_dict['status'] = chunk.status.value
            # Add text content
            chunk_dict['text'] = chunk_text
            chunk_data.append(chunk_dict)
        
        # Validation
        is_valid, warnings = validate_text_for_tts(original_text)
        
        # Summary with all data
        summary = {
            'book_id': book_id,
            'chapter_number': chapter_number,
            'original_length': len(original_text),
            'chunks_created': len(chunks),
            'validation': {
                'is_valid': is_valid,
                'warnings': warnings,
            },
            'chunk_stats': {
                'avg_size': sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0,
                'max_size': max(chunk_sizes) if chunk_sizes else 0,
                'min_size': min(chunk_sizes) if chunk_sizes else 0,
            },
            'chunks': chunk_data,
        }
        
        # Serialize chunks list directly to JSON
        (output_dir / "results.json").write_text(
            json.dumps(summary, indent=2), encoding='utf-8'
        )
        
        print(f"\n✅ Results saved to: {output_dir / 'results.json'}")
        print(f"📊 Summary:")
        print(f"   - Original: {summary['original_length']} chars")
        print(f"   - Chunks created: {summary['chunks_created']}")
        print(f"   - Avg chunk size: {summary['chunk_stats']['avg_size']:.1f} chars")
        print(f"   - Max chunk size: {summary['chunk_stats']['max_size']} chars")
        print(f"   - Min chunk size: {summary['chunk_stats']['min_size']} chars")
        
        # Basic assertions
        assert len(chunks) > 0, "Chunking produced no chunks"
        
    except Exception as e:
        # Save error as JSON
        error_data = {
            'error': str(e),
            'error_type': type(e).__name__,
        }
        (output_dir / "error.json").write_text(
            json.dumps(error_data, indent=2), encoding='utf-8'
        )
        raise
