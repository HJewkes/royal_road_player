"""Convert squad-roster stat blocks to natural-sounding text for TTS.

Runs on RAW text, before ``TextNormalizer`` (which later expands digits into
number words). Everything this converter emits therefore keeps DIGITS, so the
downstream normalizer can voice ``152`` as "one hundred fifty-two" and ``30000``
as "thirty thousand". Anything not recognised as a roster block or a
league-record line is left byte-identical, so the converter is a no-op on
ordinary prose and on non-roster chapters.
"""

import re
from typing import List, Optional, Tuple


class StatBlockConverter:
    """Rephrases football-manager squad tables into speakable prose."""

    ROLE_MAP = {
        'GK': 'goalkeeper', 'SW': 'sweeper', 'WB': 'wing back',
        'DM': 'defensive midfielder', 'AM': 'attacking midfielder',
        'D': 'defender', 'M': 'midfielder', 'F': 'forward',
        'S': 'striker', 'W': 'winger',
    }

    SIDE_WORDS = {'L': 'left', 'R': 'right', 'C': 'centre'}

    NATIONALITY_MAP = {
        'SVK': 'Slovakia', 'NOR': 'Norway', 'IRE': 'Ireland',
        'NIR': 'Northern Ireland', 'ENG': 'England', 'ROM': 'Romania',
        'WAL': 'Wales', 'GHA': 'Ghana', 'SCO': 'Scotland', 'ALG': 'Algeria',
        'JAM': 'Jamaica', 'SWE': 'Sweden', 'COL': 'Colombia', 'ESP': 'Spain',
        'KOR': 'South Korea', 'GER': 'Germany', 'GIB': 'Gibraltar',
        'FRA': 'France', 'NED': 'Netherlands', 'POR': 'Portugal',
        'BRA': 'Brazil', 'ARG': 'Argentina', 'ITA': 'Italy', 'USA': 'United States',
    }

    # A [CA PA] ability/potential bracket: two (optionally negative) integers.
    _BRACKET = re.compile(r'\[\s*(-?\d+)\s+(-?\d+)\s*\]')
    # Role code = optional leading sides + role stem + optional trailing sides.
    _POSITION = re.compile(r'^([LRC]*)(GK|SW|WB|DM|AM|D|M|F|S|W)([LRC]*)$')
    _SIDES_ONLY = re.compile(r'^[LRC]+$')
    _LEADING_NUMBER = re.compile(r'^(\d+)\.\s+')
    _INT = re.compile(r'^-?\d+$')
    _YOUTH = re.compile(r'^u\d+$', re.IGNORECASE)
    _NAT_CODE = re.compile(r'^[A-Z]{2,3}$')

    _HEADER_STD = re.compile(r'No\.\s+Name\s+Pos\s+Age\b.*\[CA PA\]', re.IGNORECASE)
    _HEADER_LOAN = re.compile(
        r'Name\s+Pos\s+Age\s+Wage\s+\[CA PA\].*Loan\s+Tier', re.IGNORECASE
    )

    _RECORD = re.compile(
        r'^\s*P(\d+)\s*-\s*W(\d+)\s*-\s*D(\d+)\s*-\s*L(\d+)\s*-\s*'
        r'Goals For\s+(\d+)\s*-\s*Goals Against\s+(\d+)\s*-\s*'
        r'Goal Difference\s+(minus \d+|\d+)\s*-\s*Points\s+(\d+)\*?\s*$',
        re.IGNORECASE,
    )

    def convert(self, text: str) -> str:
        """Rephrase roster blocks and record lines; leave all else untouched."""
        lines = text.split('\n')
        result: List[str] = []
        i = 0

        while i < len(lines):
            record = self._convert_record_line(lines[i])
            if record is not None:
                result.append(record)
                i += 1
                continue

            block = self._extract_roster_block(lines, i)
            if block:
                converted, consumed = block
                result.append(converted)
                i += consumed
                continue

            result.append(lines[i])
            i += 1

        return '\n'.join(result)

    def _convert_record_line(self, line: str) -> Optional[str]:
        """Rephrase a P-W-D-L league-record line, or return None."""
        m = self._RECORD.match(line)
        if not m:
            return None
        p, w, d, l, gf, ga, gd, pts = m.groups()
        return (
            f"Played {p}, won {w}, drawn {d}, lost {l}. "
            f"Goals for {gf}, goals against {ga}, goal difference {gd}, {pts} points."
        )

    def _extract_roster_block(
        self, lines: List[str], start: int
    ) -> Optional[Tuple[str, int]]:
        """Convert a roster block whose header sits at ``start``.

        Consumes following rows (skipping internal blank lines) until the first
        non-blank line that is not a roster row. Returns the converted prose and
        the number of source lines consumed, or None if ``start`` is not a header
        or the block has no rows.
        """
        header = lines[start].strip()
        is_loan = bool(self._HEADER_LOAN.match(header))
        if not is_loan and not self._HEADER_STD.match(header):
            return None

        rows: List[str] = []
        last_row = start
        j = start + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            if not self._is_row(stripped):
                break
            rows.append(self._convert_row(stripped, is_loan))
            last_row = j
            j += 1

        if not rows:
            return None

        return '\n\n'.join(rows), last_row - start + 1

    def _is_row(self, line: str) -> bool:
        """A roster row has a [CA PA] bracket or a leading ``N. Name``."""
        return bool(self._BRACKET.search(line) or re.match(r'\d+\.\s+[A-Z]', line))

    def _convert_row(self, line: str, is_loan: bool) -> str:
        """Rephrase a single roster row into a speakable sentence."""
        line = line.strip()

        num_match = self._LEADING_NUMBER.match(line)
        number = num_match.group(1) if num_match else None
        rest = line[num_match.end():] if num_match else line

        bracket = self._BRACKET.search(rest)
        if bracket:
            ca = bracket.group(1)
            pa = int(bracket.group(2))
            pre, post = rest[:bracket.start()], rest[bracket.end():]
        else:
            ca = pa = None
            pre, post = rest, ''

        name, position, age, nationality, wage = self._parse_identity(pre)
        ca_change, club, tier = self._parse_trailer(post, is_loan)

        segments = [f"Number {number}, {name}" if number else name]
        if position:
            segments.append(position)
        if age is not None:
            segments.append(f"age {age}")
        if nationality:
            segments.append(nationality)
        if wage is not None:
            segments.append(f"wage £{wage}")
        sentence = ', '.join(segments) + '.'

        if ca is not None:
            # PA (potential) first, then CA (current) so the improvement reads next
            # to the thing that improved. PA/CA stay as acronyms — the normalizer
            # voices them "P A"/"C A", which is familiar shorthand in this book.
            # Keep a negative PA sentinel (-1/-2) rather than hiding it as "unknown".
            pa_word = f"minus {abs(pa)}" if pa < 0 else str(pa)
            ability = f" PA {pa_word}, CA {ca}"
            change = self._render_change(ca_change)
            if change:
                ability += f", {change}"
            sentence += ability + '.'

        if is_loan and club:
            sentence += f" On loan at {club}, loan tier {tier}."

        return sentence

    def _parse_identity(self, pre: str):
        """Split the pre-bracket portion into name, position, age, nat, wage."""
        tokens = pre.split()
        age_idx = next(
            (i for i, t in enumerate(tokens) if re.match(r'^\d+$', t)), None
        )
        if age_idx is None:
            name_pos, after_age, age = tokens, [], None
        else:
            name_pos = tokens[:age_idx]
            after_age = tokens[age_idx + 1:]
            age = tokens[age_idx]

        # Positions are the trailing run of position tokens; the rest is the name.
        split = len(name_pos)
        while split > 0 and self._is_position_token(name_pos[split - 1]):
            split -= 1
        name_tokens = name_pos[:split]
        pos_tokens = name_pos[split:]

        name = ' '.join(name_tokens).replace('*', '')
        position = self._expand_positions(pos_tokens)

        nationality = None
        wage = None
        for tok in after_age:
            if self._INT.match(tok):
                if wage is None:
                    wage = tok
            elif self._YOUTH.match(tok):
                continue
            elif self._NAT_CODE.match(tok) and nationality is None:
                nationality = self.NATIONALITY_MAP.get(tok)

        return name, position, age, nationality, wage

    def _parse_trailer(self, post: str, is_loan: bool):
        """Parse the post-bracket portion: CA change, and loan club/tier."""
        tokens = post.split()
        ca_change = None
        idx = 0
        if tokens and self._INT.match(tokens[0]):
            ca_change = int(tokens[0])
            idx = 1

        club = tier = None
        if is_loan:
            rest = tokens[idx:]
            if rest:
                tier = rest[-1]
                club = ' '.join(rest[:-1]) if len(rest) > 1 else None

        return ca_change, club, tier

    def _render_change(self, change: Optional[int]) -> Optional[str]:
        """Render a CA improvement value as up/down/no change, or None."""
        if change is None:
            return None
        if change > 0:
            return f"up {change}"
        if change < 0:
            return f"down {abs(change)}"
        return "no change"

    def _is_position_token(self, token: str) -> bool:
        """True if every comma-part of the token is a position or side code."""
        if token == 'Omni':
            return True
        parts = [p for p in token.split(',') if p]
        if not parts:
            return False
        return all(self._classify_part(p) is not None for p in parts)

    def _classify_part(self, part: str):
        """Classify a position subtoken as a role, bare sides, or None."""
        if part == 'Omni':
            return ('role', 'utility player', set())
        m = self._POSITION.match(part)
        if m:
            return ('role', self.ROLE_MAP[m.group(2)], set(m.group(1) + m.group(3)))
        if self._SIDES_ONLY.match(part):
            return ('sides', None, set(part))
        return None

    def _expand_positions(self, pos_tokens: List[str]) -> str:
        """Expand position codes into 'defender, attacking midfielder left'."""
        parts: List[str] = []
        for token in pos_tokens:
            parts.extend(p for p in token.split(',') if p)

        roles: List[List] = []  # [role_name, {sides}]
        for part in parts:
            classified = self._classify_part(part)
            if classified is None:
                continue
            kind, value, sides = classified
            if kind == 'role':
                roles.append([value, set(sides)])
            elif roles:  # bare sides attach to the previous role
                roles[-1][1] |= sides

        phrases = []
        for role_name, sides in roles:
            if sides:
                phrases.append(f"{role_name} {self._sides_phrase(sides)}")
            else:
                phrases.append(role_name)
        return ', '.join(phrases)

    def _sides_phrase(self, sides: set) -> str:
        """Render a set of side letters in canonical left/right/centre order."""
        words = [self.SIDE_WORDS[s] for s in ('L', 'R', 'C') if s in sides]
        if len(words) == 1:
            return words[0]
        if len(words) == 2:
            return f"{words[0]} and {words[1]}"
        return f"{words[0]}, {words[1]} and {words[2]}"
