# Table Conversion Report

This document shows how all markdown tables from the book are converted to natural-sounding text for TTS generation.

## Summary

- **Total tables found**: 4 unique tables
- **Table types**: 
  - Full league tables (with all columns): 2 tables
  - Partial league tables (bottom of table): 2 tables
- **All tables convert successfully**: ✅
- **No table markers remain**: ✅

## Table Conversions

### Table 1: Chapter 02 - Full League Table (Top 4)

**Location**: `chapters/02/text.txt:273`

**Context**: "This match was one of our rescheduled ones, and our three closest rivals hadn't played. That put us six points clear at the top..."

**Original Table**:
```
|  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Team | P | W | D | L | F | A | GD | Pts |
| 1 | Chester | 29 | 22 | 2 | 5 | 78 | 27 | 51 | 68 |
| 2 | Kidderminster | 29 | 18 | 8 | 3 | 51 | 20 | 31 | 62 |
| 3 | York | 30 | 16 | 11 | 3 | 49 | 30 | 19 | 59 |
| 4 | Darlington | 29 | 16 | 10 | 3 | 45 | 28 | 17 | 58 |
```

**Converted Text**:
```
In 1st place, Chester, with 68 points, from 29 games, having won 22, drawn 2, lost 5, They've scored 78 goals and conceded 27, giving them a goal difference of plus 51.

In 2nd place, Kidderminster, with 62 points, from 29 games, having won 18, drawn 8, lost 3, They've scored 51 goals and conceded 20, giving them a goal difference of plus 31.

In 3rd place, York, with 59 points, from 30 games, having won 16, drawn 11, lost 3, They've scored 49 goals and conceded 30, giving them a goal difference of plus 19.

In 4th place, Darlington, with 58 points, from 29 games, having won 16, drawn 10, lost 3, They've scored 45 goals and conceded 28, giving them a goal difference of plus 17.
```

---

### Table 2: Chapter 04 - Full League Table (Top 4)

**Location**: `chapters/04/text.txt:89`

**Context**: "I wrote out the top four positions."

**Original Table**:
```
|  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Team | P | W | D | L | F | A | GD | Pts |
| 1 | Chester | 30 | 23 | 2 | 5 | 79 | 27 | 52 | 71 |
| 2 | Kidderminster | 30 | 18 | 9 | 3 | 53 | 22 | 31 | 63 |
| 3 | York | 31 | 17 | 11 | 3 | 51 | 30 | 21 | 62 |
| 4 | Darlington | 30 | 16 | 11 | 3 | 45 | 28 | 17 | 59 |
```

**Converted Text**:
```
In 1st place, Chester, with 71 points, from 30 games, having won 23, drawn 2, lost 5, They've scored 79 goals and conceded 27, giving them a goal difference of plus 52.

In 2nd place, Kidderminster, with 63 points, from 30 games, having won 18, drawn 9, lost 3, They've scored 53 goals and conceded 22, giving them a goal difference of plus 31.

In 3rd place, York, with 62 points, from 31 games, having won 17, drawn 11, lost 3, They've scored 51 goals and conceded 30, giving them a goal difference of plus 21.

In 4th place, Darlington, with 59 points, from 30 games, having won 16, drawn 11, lost 3, They've scored 45 goals and conceded 28, giving them a goal difference of plus 17.
```

---

### Table 3: Chapter 08 - Partial League Table (Bottom 5)

**Location**: `chapters/08/text.txt:349`

**Context**: "Here," I said, grabbing a piece of paper and writing out the bottom of the table.

**Original Table**:
```
|  |  |  |  |  |
| --- | --- | --- | --- | --- |
|  |  | P | GD | Pts |
| 20 | Colchester | 36 | -12 | 35 |
| 21 | Salford City | 36 | -13 | 35 |
| 22 | Forest Green Rovers | 36 | -26 | 30 |
| 23 | Grimsby Town | 36 | -21 | 29 |
| 24 | Sutton United | 36 | -24 | 25 |
```

**Converted Text**:
```
In 20th place, Colchester, with 35 points, from 36 games, giving them a goal difference of minus 12.

In 21st place, Salford City, with 35 points, from 36 games, giving them a goal difference of minus 13.

In 22nd place, Forest Green Rovers, with 30 points, from 36 games, giving them a goal difference of minus 26.

In 23rd place, Grimsby Town, with 29 points, from 36 games, giving them a goal difference of minus 21.

In 24th place, Sutton United, with 25 points, from 36 games, giving them a goal difference of minus 24.
```

**Note**: This table is missing the Team column header and W/D/L/F/A columns, but the converter correctly detects team names and positions from the data.

---

### Table 4: Chapter 11 - Partial League Table (Bottom 5)

**Location**: `chapters/11/text.txt:287`

**Context**: Alex Evans had been on the bench keeping track. "Everyone else lost, boss." He showed me the league table.

**Original Table**:
```
|  |  |  |  |  |
| --- | --- | --- | --- | --- |
|  |  | P | GD | Pts |
| 20 | Salford City | 39 | -16 | 38 |
| 21 | Colchester | 39 | -13 | 36 |
| 22 | Forest Green Rovers | 39 | -28 | 31 |
| 23 | Grimsby Town | 39 | -23 | 30 |
| 24 | Sutton United | 39 | -24 | 29 |
```

**Converted Text**:
```
In 20th place, Salford City, with 38 points, from 39 games, giving them a goal difference of minus 16.

In 21st place, Colchester, with 36 points, from 39 games, giving them a goal difference of minus 13.

In 22nd place, Forest Green Rovers, with 31 points, from 39 games, giving them a goal difference of minus 28.

In 23rd place, Grimsby Town, with 30 points, from 39 games, giving them a goal difference of minus 23.

In 24th place, Sutton United, with 29 points, from 39 games, giving them a goal difference of minus 24.
```

---

## Conversion Features

### What Works Well

1. **Position Detection**: Correctly identifies positions from numeric columns, even when header is empty
2. **Team Name Detection**: Finds team names from data when header column is missing
3. **Stats Inclusion**: Includes all available stats (points, games, wins/draws/losses, goals, goal difference)
4. **Natural Language**: Converts to readable prose that flows naturally
5. **Negative Numbers**: Handles negative goal differences correctly ("minus 12" instead of "negative 12")
6. **Ordinal Numbers**: Converts positions to ordinals (1st, 2nd, 20th, 21st, etc.)

### Table Types Handled

- ✅ Full league tables with all columns
- ✅ Partial league tables (bottom of table with fewer columns)
- ✅ Tables with empty header cells
- ✅ Tables with missing Team column header
- ✅ Tables with position numbers in data but not header

### Conversion Quality

All tables convert to natural-sounding prose that:
- Reads smoothly when spoken
- Includes all relevant information
- Maintains context (team names, positions, stats)
- Uses appropriate language ("minus" for negative goal differences, "plus" for positive)
- Separates each team's description with paragraph breaks for clarity

## Test Suite

A comprehensive test suite is available at:
- `backend/tests/text_processing/test_table_converter_book_tables.py`
- `backend/tests/text_processing/book_tables.json` (contains all extracted tables)

Run tests with:
```bash
cd backend
pytest tests/text_processing/test_table_converter_book_tables.py -v
```

Generate conversion report:
```bash
cd backend
python3 -c "from tests.text_processing.test_table_converter_book_tables import generate_table_conversion_report; generate_table_conversion_report()"
```

