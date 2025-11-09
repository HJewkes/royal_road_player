#!/usr/bin/env python3
"""Quick script to check ETA calculation values."""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from src.data.database import db_session
from src.data.db_repository import ChunkRepository
from src.services.job_queue import JobQueue

def main():
    """Check ETA calculation values."""
    with db_session() as session:
        # Get pending jobs
        queue = JobQueue()
        pending_jobs = queue.get_pending_jobs()
        
        print(f"Pending jobs: {len(pending_jobs)}")
        print()
        
        # Calculate ETA
        eta_result = ChunkRepository.calculate_eta(pending_jobs, session)
        
        print("ETA Calculation Results:")
        print(f"  avg_time_per_char: {eta_result['avg_time_per_char']:.6f} seconds/char")
        print(f"  avg_time_per_chunk: {eta_result['avg_time_per_chunk']:.2f} seconds/chunk")
        print(f"  estimated_seconds_remaining: {eta_result['estimated_seconds_remaining']:,} seconds")
        print(f"  estimated_hours_remaining: {eta_result['estimated_seconds_remaining'] / 3600:.2f} hours")
        print()
        
        # Check total chars
        from sqlalchemy import func
        from src.data.db_models import ChunkDB
        from src.models.enums import ChunkStatus
        
        total_chars_result = session.query(
            func.sum(ChunkDB.text_end - ChunkDB.text_start).label('total_chars'),
            func.count(ChunkDB.id).label('pending_count')
        ).filter(
            ChunkDB.status == ChunkStatus.PENDING.value,
            ChunkDB.text_end.isnot(None),
            ChunkDB.text_start.isnot(None)
        ).first()
        
        total_chars = float(total_chars_result.total_chars) if total_chars_result and total_chars_result.total_chars else 0
        pending_count = total_chars_result.pending_count if total_chars_result else 0
        
        print("Pending Chunks Info:")
        print(f"  pending_chunks_in_db: {pending_count}")
        print(f"  total_chars: {total_chars:,.0f}")
        if total_chars > 0:
            avg_chunk_size = total_chars / pending_count if pending_count > 0 else 0
            print(f"  avg_chars_per_chunk: {avg_chunk_size:.1f}")
        print()
        
        # Check recent completed chunks stats
        from sqlalchemy import desc
        
        # Get last 50 chunk IDs first, then aggregate
        recent_chunk_ids = session.query(ChunkDB.id).filter(
            ChunkDB.status == ChunkStatus.COMPLETED.value,
            ChunkDB.generation_time_seconds.isnot(None),
            ChunkDB.generation_time_seconds > 0,
            ChunkDB.text_end.isnot(None),
            ChunkDB.text_start.isnot(None),
            (ChunkDB.text_end - ChunkDB.text_start) > 0
        ).order_by(desc(ChunkDB.updated_at)).limit(50).subquery()
        
        recent_stats = session.query(
            func.avg(ChunkDB.generation_time_seconds / (ChunkDB.text_end - ChunkDB.text_start)).label('avg_time_per_char'),
            func.avg(ChunkDB.generation_time_seconds).label('avg_time_per_chunk'),
            func.avg(ChunkDB.text_end - ChunkDB.text_start).label('avg_text_length'),
            func.count(ChunkDB.id).label('count')
        ).filter(
            ChunkDB.id.in_(session.query(recent_chunk_ids.c.id))
        ).first()
        
        print("Recent Completed Chunks (last 50):")
        if recent_stats and recent_stats.count:
            print(f"  count: {recent_stats.count}")
            print(f"  avg_time_per_char: {float(recent_stats.avg_time_per_char):.6f} seconds/char")
            print(f"  avg_time_per_chunk: {float(recent_stats.avg_time_per_chunk):.2f} seconds/chunk")
            print(f"  avg_text_length: {float(recent_stats.avg_text_length):.1f} chars")
        else:
            print("  No completed chunks found")
        print()
        
        # Manual calculation check
        if total_chars > 0 and eta_result['avg_time_per_char'] > 0:
            manual_eta = total_chars * eta_result['avg_time_per_char']
            print("Manual Calculation Check:")
            print(f"  total_chars * avg_time_per_char = {total_chars:,.0f} * {eta_result['avg_time_per_char']:.6f}")
            print(f"  = {manual_eta:,.0f} seconds ({manual_eta/3600:.2f} hours)")
            print(f"  Matches result: {abs(manual_eta - eta_result['estimated_seconds_remaining']) < 1}")

if __name__ == "__main__":
    main()

