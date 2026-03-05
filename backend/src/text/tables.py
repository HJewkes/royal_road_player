"""Convert markdown tables to natural-sounding text for TTS."""

import re
from typing import List, Optional, Tuple


class TableConverter:
    """Converts markdown tables to natural text for TTS generation."""

    SPORTS_ABBREVIATIONS = {
        'P': 'played', 'W': 'won', 'D': 'drawn', 'L': 'lost',
        'F': 'for', 'A': 'against', 'GD': 'goal difference', 'Pts': 'points',
        'MP': 'matches played', 'GF': 'goals for', 'GA': 'goals against',
    }

    def convert(self, text: str) -> str:
        """Find all markdown tables and convert them to prose."""
        lines = text.split('\n')
        result_lines = []
        i = 0

        while i < len(lines):
            table_result = self._extract_table(lines, i)

            if table_result:
                table_lines, lines_consumed = table_result
                converted = self._convert_table(table_lines)
                result_lines.append(converted)
                i += lines_consumed
            else:
                result_lines.append(lines[i])
                i += 1

        return '\n'.join(result_lines)

    def _extract_table(self, lines: List[str], start_idx: int) -> Optional[Tuple[List[str], int]]:
        """Extract a complete markdown table starting at start_idx."""
        if start_idx >= len(lines):
            return None

        first_line = lines[start_idx].strip()
        if not first_line.startswith('|') or first_line == '|':
            return None

        table_lines = []
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()
            if not line or not line.startswith('|'):
                break

            # Skip separator lines (all dashes/colons)
            if not re.match(r'^\|[\s\-\|:]+\|$', line):
                table_lines.append(line)

            i += 1

        # Need at least header + 1 data row
        if len(table_lines) < 2:
            return None

        return (table_lines, i - start_idx)

    def _convert_table(self, table_lines: List[str]) -> str:
        """Convert a markdown table to natural-sounding text."""
        rows = []
        for line in table_lines:
            cells = [cell.strip() for cell in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty cells from split
            if cells:
                rows.append(cells)

        if len(rows) < 2:
            return '\n'.join(table_lines)

        header = rows[0]
        data_rows = rows[1:]

        if self._is_sports_standings(header):
            return self._convert_sports_standings(header, data_rows)
        else:
            return self._convert_generic_table(header, data_rows)

    def _is_sports_standings(self, header: List[str]) -> bool:
        """Check if this looks like a sports league standings table."""
        header_text = ' '.join(header).lower()
        sports_keywords = ['team', 'pts', 'points', 'played', 'won', 'drawn', 'lost', 'goal']
        return any(keyword in header_text for keyword in sports_keywords)

    def _convert_sports_standings(self, header: List[str], data_rows: List[List[str]]) -> str:
        """Convert sports standings table to natural text."""
        header_lower = [h.lower() for h in header]

        # Find column indices
        pos_idx = self._find_column(header_lower, ['pos', 'position'])
        team_idx = self._find_column(header_lower, ['team', 'club', 'name'])
        pts_idx = self._find_column(header_lower, ['pts', 'points'])
        played_idx = self._find_column(header_lower, ['played', 'mp', 'p'])
        won_idx = self._find_column(header_lower, ['won', 'w'])
        drawn_idx = self._find_column(header_lower, ['drawn', 'd'])
        lost_idx = self._find_column(header_lower, ['lost', 'l'])

        descriptions = []
        for row_idx, row in enumerate(data_rows):
            if not row:
                continue

            position = self._get_cell(row, pos_idx) or str(row_idx + 1)
            team = self._get_cell(row, team_idx) or "Unknown"

            parts = [f"{self._ordinal(int(position) if position.isdigit() else row_idx + 1)}: {team}"]

            if pts_idx is not None:
                points = self._get_cell(row, pts_idx)
                if points:
                    parts.append(f"{points} points")

            if played_idx is not None:
                played = self._get_cell(row, played_idx)
                if played:
                    parts.append(f"{played} games")

            record = []
            if won_idx is not None:
                won = self._get_cell(row, won_idx)
                if won:
                    record.append(f"{won} wins")
            if drawn_idx is not None:
                drawn = self._get_cell(row, drawn_idx)
                if drawn and drawn != '0':
                    record.append(f"{drawn} draws")
            if lost_idx is not None:
                lost = self._get_cell(row, lost_idx)
                if lost:
                    record.append(f"{lost} losses")

            if record:
                parts.append(', '.join(record))

            descriptions.append(', '.join(parts) + '.')

        return '\n\n'.join(descriptions) if descriptions else ''

    def _convert_generic_table(self, header: List[str], data_rows: List[List[str]]) -> str:
        """Convert a generic table to natural text."""
        descriptions = []

        for row in data_rows:
            if len(row) != len(header):
                continue

            pairs = []
            for col, val in zip(header, row):
                if val and col:
                    pairs.append(f"{col}: {val}")

            if pairs:
                descriptions.append(', '.join(pairs) + '.')

        return '\n\n'.join(descriptions) if descriptions else ''

    def _find_column(self, header: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index matching any of the keywords."""
        for i, col in enumerate(header):
            col_lower = col.lower().strip()
            if col_lower in [k.lower() for k in keywords]:
                return i
        return None

    def _get_cell(self, row: List[str], idx: Optional[int]) -> Optional[str]:
        """Safely get cell value."""
        if idx is None or idx >= len(row):
            return None
        val = row[idx].strip()
        return val if val else None

    def _ordinal(self, n: int) -> str:
        """Convert number to ordinal (1st, 2nd, 3rd, etc.)."""
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"


