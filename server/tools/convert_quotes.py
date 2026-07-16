#!/bin/env python3
"""
convert_quotes.py

Converts MONSTER.QUOTE.TXT (Apple II fixed-record ASCII, CR line endings,
null-padded records) to monster_quotes.json.

Quote format in JSON:
  [
    { "number": 51, "quote": "But I is mien!" },
    ...
  ]

  $ in quote text = replaced at runtime with the character's name.
"""

import json
import logging

TXT_FILE  = 'MONSTER.QUOTE.TXT'
JSON_FILE = 'monster_quotes.json'

# If more than this fraction of alpha chars are uppercase, treat as all-caps.
UPPER_THRESHOLD = 0.8


def is_allcaps(text: str) -> bool:
    """Return True if the text is predominantly uppercase."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return (upper / len(letters)) >= UPPER_THRESHOLD


def sentence_case(text: str) -> str:
    """
    Convert an all-caps string to sentence case, preserving $ placeholders.
    Capitalizes the first letter and after '. ', '! ', '? '.
    Leaves $ and its surrounding context alone.
    """
    result = text.lower()
    # Capitalize first non-space character
    for i, ch in enumerate(result):
        if ch.isalpha():
            result = result[:i] + result[i].upper() + result[i+1:]
            break
    # Capitalize after sentence-ending punctuation followed by a space
    import re
    result = re.sub(r'([.!?])\s+([a-z])',
                    lambda m: m.group(1) + ' ' + m.group(2).upper(),
                    result)
    return result


def normalize(text: str) -> str:
    """Sentence-case if all-caps, otherwise leave alone."""
    if is_allcaps(text):
        return sentence_case(text)
    return text


def convert(txt_filename: str, json_filename: str):
    with open(txt_filename, 'rb') as f:
        raw = f.read()

    # Split on CR (0x0D), strip null bytes from each record
    records = [r.replace(b'\x00', b'').decode('ascii', errors='replace').strip()
               for r in raw.split(b'\x0d')]

    # Drop empty records
    records = [r for r in records if r]
    logging.info(f'Records after stripping: {len(records)}')

    # First record should be the count
    try:
        count = int(records[0])
        records = records[1:]
        logging.info(f'Quote count from file: {count}')
    except ValueError:
        logging.warning(f'First record is not a count: {records[0]!r}, proceeding anyway')
        count = None

    if count is not None and len(records) != count:
        logging.warning(f'Expected {count} quotes, found {len(records)}')

    quotes = []
    for i, raw_text in enumerate(records, start=1):
        text = normalize(raw_text)
        logging.info(f'Quote {i}: {text!r}')
        quotes.append({'number': i, 'quote': text})

    with open(json_filename, 'w') as f:
        json.dump(quotes, f, indent=4)

    print(f"Wrote {len(quotes)} quotes to '{json_filename}'.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')
    convert(TXT_FILE, JSON_FILE)
