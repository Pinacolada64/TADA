#!/usr/bin/env python3
#
# GBBS Pro Message Database Tool
#
# 2026-02-05, Brian J. Bernstein
#
# Analyzes and extracts messages from GBBS Pro message database files.
# Supports both bulletin board and email formats.
#

import struct
import sys
import os
import re
from datetime import datetime
from pathlib import Path

def read_data2_file(filename):
    """
    Read GBBS Pro DATA2 file and return a dictionary mapping board filenames to board names.
    
    DATA2 file format:
    - 128-byte fixed-length records
    - Records 0-8: Access level descriptions
    - Records 9+: Message base definitions
    
    Message base record structure (128 bytes):
    - Board name (null-terminated, ends with \\r)
    - Filename in format F:B#\\r (e.g., F:B1, F:B2)
    - Additional fields (access levels, limits, etc.)
    
    Returns dict mapping filename to board name, e.g.:
    {'B1': 'System News', 'B2': 'Public Base', ...}
    """
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except:
        return {}
    
    boards = {}
    record_size = 128
    num_records = len(data) // record_size
    
    # Start at record 9 (offset 1152) where message bases begin
    for rec_num in range(9, num_records):
        offset = rec_num * record_size
        record = data[offset:offset+record_size]
        
        # Look for pattern: name\rF:filename\r
        if b'\rF:' not in record:
            continue
        
        # Extract board name (up to first \r)
        name_end = record.find(0x0d)
        if name_end <= 0:
            continue
        
        board_name = record[:name_end].decode('ascii', errors='replace').strip()
        
        # Extract filename (F:B#)
        file_start = record.find(b'\rF:')
        if file_start < 0:
            continue
        
        file_end = record.find(0x0d, file_start + 1)
        if file_end <= 0:
            continue
        
        filename = record[file_start+2:file_end].decode('ascii', errors='replace').strip()
        
        # Only process message base files (B#)
        if filename.startswith(':B') or filename.startswith('B'):
            # Normalize to just B# format
            if filename.startswith(':'):
                filename = filename[1:]
            
            boards[filename] = board_name
    
    return boards

def read_users_file(filename):
    """
    Read GBBS Pro USERS file and return a dictionary mapping user_id to user info.
    While the USERS file is completely unnecessary for the message database files,
    MAIL files do not contain the name of the recipient of an email, rather, the
    message entry record corresponds to the user ID of the recipeient, so the
    parsing of the USERS file enables us to put an actual name for a recipient.
    
    USERS file format (128 bytes per record):
    - Record N corresponds to User ID N
    - Record 0 is typically unused (no user ID 0)
    
    Record structure:
    - First_name,Last_Name\r (uppercase)
    - Full_name\r (proper case, preferred for display)
    - City,State\r
    - ... (padding bytes)
    - Offset 70: password (8 bytes)
    - Offset 78: phone_number (12 bytes)
    
    Note: This format may vary between GBBS Pro systems if modified by sysops.
    This implementation assumes the standard GBBS Pro USERS file format.
    """
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except:
        return {}
    
    users = {}
    record_size = 128
    num_records = len(data) // record_size
    
    for user_id in range(num_records):
        offset = user_id * record_size
        record = data[offset:offset+record_size]
        
        # Parse first line: First_name,Last_Name\r
        first_line_end = record.find(0x0d)
        if first_line_end <= 0:
            continue
        
        # Parse second line: Full_name\r
        second_start = first_line_end + 1
        second_line_end = record.find(0x0d, second_start)
        if second_line_end <= 0:
            continue
        
        full_name = record[second_start:second_line_end].decode('ascii', errors='replace').strip()
        
        # Parse third line: City,State\r
        third_start = second_line_end + 1
        third_line_end = record.find(0x0d, third_start)
        if third_line_end > 0:
            city_state = record[third_start:third_line_end].decode('ascii', errors='replace').strip()
        else:
            city_state = ""
        
        if full_name:
            users[user_id] = {
                'full_name': full_name,
                'city_state': city_state
            }
    
    return users

def detect_format(data):
    """Detect database format from header byte 0."""
    return 'email' if data[0] == 0x04 else 'bulletin'

def decode_7bit(compressed_data, stop_at_null=True):
    """Decode 7-bit compressed data to ASCII text."""
    result = []
    i = 0
    while i + 6 < len(compressed_data):
        bytes_7 = compressed_data[i:i+7]
        char8 = 0
        chars = []
        for b in bytes_7:
            char8 = (char8 >> 1) | ((b & 0x80) >> 0)
            chars.append(b & 0x7F)
        char8 = char8 >> 1
        chars.append(char8)
        
        for c in chars:
            if stop_at_null and c == 0:
                return bytes(result).decode('ascii', errors='replace').replace('\r', '\n')
            result.append(c)
        i += 7
    return bytes(result).decode('ascii', errors='replace').replace('\r', '\n')

def parse_date(text):
    """
    Extract and parse date from message text.

    The date tag is key to determining if we're looking at the start of a message versus
    a chained continuation. As well, it is used to set the timestamp of the extracted files.

    The header of messages was something that Sysops could customize, so it is quite
    possible that the two formats here might not cover all implementations of GBBS Pro systems.
    As such, try adding your own format below if you encounter a different one.
    """
    # Try standard format: Date : MM/DD/YY HH:MM:SS AM/PM
    date_match = re.search(r'Date\s*[:-]\s*(\d{1,2}/\d{1,2}/\d{2})\s+(\d{1,2}:\d{2}:\d{2})\s+([AP]M)', text)
    if date_match:
        date_str = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}"
        try:
            return datetime.strptime(date_str, "%m/%d/%y %I:%M:%S %p")
        except:
            pass
    
    # Try alternate format: Date ->MM/DD/YY HH:MM:SS AM/PM
    date_match = re.search(r'Date\s*->\s*(\d{1,2}/\d{1,2}/\d{2})\s+(\d{1,2}:\d{2}:\d{2})\s+([AP]M)', text)
    if date_match:
        date_str = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}"
        try:
            return datetime.strptime(date_str, "%m/%d/%y %I:%M:%S %p")
        except:
            pass
    
    return None

def read_msginfo(data):
    """Read and parse MSGINFO header (8 bytes)."""
    if len(data) < 8:
        return None
    
    return {
        'bitmap_blocks': data[0],
        'dir_blocks': data[1],
        'used_blocks': struct.unpack('<H', data[2:4])[0],
        'msg_count': struct.unpack('<H', data[4:6])[0],
        'new_msg_num': struct.unpack('<H', data[6:8])[0],
        'bitmap_offset': 8,
        'dir_offset': 8 + (data[0] * 128),
        'data_offset': 8 + (data[0] * 128) + (data[1] * 128),
        'max_dir_entries': (data[1] * 128) // 4
    }

def is_message_start(decoded_text):
    """
    Check if decoded text looks like a message start (subject/to/from/date pattern).

    Like with the parse_date() header comment, this function assumes the message header
    displaying the timestamp would be 'Date :' or 'Date ->' or something similar. If
    your data file has a different format, you need to add this on the line 3 below since
    this whole area of a message header was customizable by a BBS sysop.
    """
    lines = decoded_text.split('\n')
    if len(lines) < 4:
        return False
    
    # Line 0: Subject (any text)
    # Line 1: To (number,name format)
    # Line 2: From (number,name format)
    # Line 3: Date line
    
    # Check line 1 and 2 for "number,text" pattern
    if not (re.match(r'^\d+,', lines[1]) and re.match(r'^\d+,', lines[2])):
        return False
    
    # Check line 3 for Date pattern
    if not ('Date' in lines[3] and (':' in lines[3] or '->' in lines[3])):
        return False
    
    return True

def scan_database_bulletin(data):
    """Scan bulletin board format database with priority-based block allocation."""
    msginfo = read_msginfo(data)
    if not msginfo:
        return None
    
    data_offset = msginfo['data_offset']
    data_area_size = len(data) - data_offset
    total_blocks = data_area_size // 128
    max_entries = msginfo['max_dir_entries']
    dir_offset = msginfo['dir_offset']
    
    used_blocks = set()  # Track all blocks claimed by any message
    
    # PHASE 1: Extract active messages from directory
    active_messages = []
    for entry_num in range(max_entries):
        entry_offset = dir_offset + (entry_num * 4)
        if entry_offset + 4 > len(data):
            break
        entry = data[entry_offset:entry_offset+4]
        if len(entry) < 4:
            break
        block_num = struct.unpack('<H', entry[2:4])[0]
        
        if block_num == 0:
            continue
        
        # Validate block is within bounds
        if block_num > total_blocks:
            continue
        
        # Extract message and mark all blocks in chain as used
        message, chain_blocks = follow_chain_with_tracking(data, block_num, total_blocks, used_blocks, data_offset)
        used_blocks.update(chain_blocks)
        
        date = parse_date(message)
        active_messages.append({
            'entry': entry_num,
            'block': block_num,
            'message': message,
            'date': date
        })
    
    # PHASE 2: Find deleted messages (message start pattern in unused blocks)
    deleted_messages = []
    deleted_all_blocks = set()  # Track all blocks used by deleted messages
    all_blocks = set(range(1, total_blocks + 1))
    unused_blocks = all_blocks - used_blocks
    
    for block_num in sorted(unused_blocks):
        if block_num in used_blocks:
            continue
        
        block_offset = data_offset + (block_num - 1) * 128
        if block_offset + 128 > len(data):
            continue
        block_data = data[block_offset:block_offset+126]
        
        non_null_count = sum(1 for b in block_data if b != 0)
        if non_null_count < 10:
            continue
        
        decoded = decode_7bit(block_data)
        if not is_message_start(decoded):
            continue
        
        # Found deleted message start - extract and mark blocks
        message, chain_blocks = follow_chain_with_tracking(data, block_num, total_blocks, used_blocks, data_offset)
        used_blocks.update(chain_blocks)
        deleted_all_blocks.update(chain_blocks)
        
        date = parse_date(message)
        deleted_messages.append({
            'block': block_num,
            'message': message,
            'date': date
        })
    
    # PHASE 3: Extract orphaned blocks (remaining unused blocks with data)
    orphaned_messages = []
    unused_blocks = all_blocks - used_blocks
    
    for block_num in sorted(unused_blocks):
        if block_num in used_blocks:
            continue
        
        block_offset = data_offset + (block_num - 1) * 128
        if block_offset + 128 > len(data):
            continue
        block_data = data[block_offset:block_offset+126]
        
        non_null_count = sum(1 for b in block_data if b != 0)
        if non_null_count < 10:
            continue
        
        # Extract orphaned block and follow chain
        message, chain_blocks = follow_chain_with_tracking(data, block_num, total_blocks, used_blocks, data_offset)
        used_blocks.update(chain_blocks)
        
        orphaned_messages.append({
            'block': block_num,
            'message': message
        })
    
    deleted_messages.sort(key=lambda x: x['date'] if x['date'] else datetime.min)
    
    # Calculate active blocks (all blocks used by active messages)
    active_all_blocks = set()
    for msg in active_messages:
        # Add header block
        active_all_blocks.add(msg['block'])
        # Follow chain to get all blocks
        current = msg['block']
        visited = set([current])
        block_offset = data_offset + (current - 1) * 128
        if block_offset + 128 <= len(data):
            next_block = struct.unpack('<H', data[block_offset+126:block_offset+128])[0]
            while next_block != 0 and next_block not in visited:
                active_all_blocks.add(next_block)
                visited.add(next_block)
                block_offset = data_offset + (next_block - 1) * 128
                if block_offset + 128 > len(data):
                    break
                next_block = struct.unpack('<H', data[block_offset+126:block_offset+128])[0]
    
    return {
        'format': 'bulletin',
        'msginfo': msginfo,
        'total_blocks': total_blocks,
        'active_all_blocks': active_all_blocks,
        'deleted_all_blocks': deleted_all_blocks,
        'allocated_blocks': set(msg['block'] for msg in active_messages),
        'deleted_blocks': set(msg['block'] for msg in deleted_messages),
        'orphaned_blocks': set(msg['block'] for msg in orphaned_messages),
        'active_messages': active_messages,
        'deleted_messages': deleted_messages,
        'orphaned_messages': orphaned_messages
    }

def scan_database_email(data, users=None):
    """Scan email format database - directory entries map to user IDs.
    
    Args:
        data: Raw database file bytes
        users: Optional dict mapping user_id to user info (from read_users_file)
    """
    msginfo = read_msginfo(data)
    if not msginfo:
        return None
    
    data_offset = msginfo['data_offset']
    data_area_size = len(data) - data_offset
    total_blocks = data_area_size // 128
    max_entries = msginfo['max_dir_entries']
    dir_offset = msginfo['dir_offset']
    
    all_messages = []
    used_blocks = set()
    
    # Each directory entry corresponds to a user ID
    for user_id in range(max_entries):
        entry_offset = dir_offset + (user_id * 4)
        if entry_offset + 4 > len(data):
            break
        
        entry = data[entry_offset:entry_offset+4]
        if len(entry) < 4:
            break
        
        block_num = struct.unpack('<H', entry[2:4])[0]
        if block_num == 0:
            continue
        
        # Get user info if available
        user_info = users.get(user_id) if users else None
        
        # Follow chain for this user
        chain_text, chain_blocks = follow_chain_with_tracking(data, block_num, total_blocks, set(), data_offset)
        used_blocks.update(chain_blocks)
        
        # Split on EOT (0x04) to get individual messages
        messages = chain_text.split('\x04')
        
        for msg in messages:
            msg = msg.replace('\x00', '').strip()
            if len(msg) < 20:
                continue
            
            date = parse_date(msg)
            all_messages.append({
                'user_id': user_id,
                'user_info': user_info,
                'message': msg,
                'date': date
            })
    
    # Sort by date
    all_messages.sort(key=lambda x: x['date'] if x['date'] else datetime.min)
    
    return {
        'format': 'email',
        'msginfo': msginfo,
        'total_blocks': total_blocks,
        'allocated_blocks': used_blocks,
        'deleted_blocks': set(),
        'orphaned_blocks': set(),
        'active_messages': all_messages,
        'deleted_messages': [],
        'orphaned_messages': []
    }

def scan_database(data, users=None):
    """Scan database and categorize all blocks."""
    fmt = detect_format(data)
    if fmt == 'email':
        return scan_database_email(data, users)
    else:
        return scan_database_bulletin(data)

def follow_chain_with_tracking(data, start_block, total_blocks, stop_blocks, data_offset):
    """Follow block chain, stopping at already-used blocks.
    
    Returns tuple: (message_text, set_of_blocks_used)
    """
    message_parts = []
    current_block = start_block
    visited = set()
    blocks_used = set()
    first_block = True
    
    while current_block != 0 and current_block not in visited:
        # Stop if this block is already claimed by higher priority
        if current_block in stop_blocks:
            break
        
        visited.add(current_block)
        blocks_used.add(current_block)
        
        block_offset = data_offset + (current_block - 1) * 128
        if block_offset + 128 > len(data) or current_block > total_blocks:
            break
        
        block_data = data[block_offset:block_offset+126]
        next_block = struct.unpack('<H', data[block_offset+126:block_offset+128])[0]
        
        decoded = decode_7bit(block_data, stop_at_null=False)
        
        # If continuation block has message start pattern, stop before it
        if not first_block and is_message_start(decoded):
            break
        
        if not first_block:
            decoded = decoded.lstrip('\x00')
        
        message_parts.append(decoded)
        first_block = False
        
        if next_block == 0:
            break
        
        # Handle self-referencing pointer
        if next_block == current_block:
            next_sequential = current_block + 1
            if next_sequential <= total_blocks and next_sequential not in stop_blocks:
                next_seq_offset = data_offset + (next_sequential - 1) * 128
                if next_seq_offset + 128 <= len(data):
                    next_seq_data = data[next_seq_offset:next_seq_offset+126]
                    next_seq_decoded = decode_7bit(next_seq_data, stop_at_null=False)
                    if not is_message_start(next_seq_decoded) and len(next_seq_decoded.strip()) > 10:
                        current_block = next_sequential
                        continue
            break
        
        if next_block in visited:
            break
        
        current_block = next_block
    
    full_message = ''.join(message_parts)
    null_pos = full_message.find('\x00')
    if null_pos >= 0:
        full_message = full_message[:null_pos]
    
    return full_message, blocks_used

def cmd_analyze(filename, users_file=None):
    """Display database statistics and block map."""
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{filename}': {e}")
        sys.exit(1)
    
    users = None
    if users_file:
        users = read_users_file(users_file)
        if not users:
            print(f"Warning: Could not read USERS file '{users_file}' or file is empty")
    
    fmt = detect_format(data)
    result = scan_database(data, users)
    
    print(f"=== Database Analysis: {filename} ===\n")
    print(f"Format: {fmt.upper()}")
    print(f"File size: {len(data)} bytes")
    
    if result.get('msginfo'):
        msginfo = result['msginfo']
        print(f"\nHeader (MSGINFO):")
        print(f"  Bitmap blocks: {msginfo['bitmap_blocks']} ({msginfo['bitmap_blocks'] * 128} bytes)")
        print(f"  Directory blocks: {msginfo['dir_blocks']} ({msginfo['dir_blocks'] * 128} bytes)")
        print(f"  Used data blocks: {msginfo['used_blocks']}")
        print(f"  Message count: {msginfo['msg_count']}")
        print(f"  New message number: {msginfo['new_msg_num']}")
        print(f"\nFile layout:")
        print(f"  0x000-0x007: Header (8 bytes)")
        print(f"  0x{msginfo['bitmap_offset']:03x}-0x{msginfo['dir_offset']-1:03x}: Bitmap ({msginfo['bitmap_blocks']} blocks)")
        print(f"  0x{msginfo['dir_offset']:03x}-0x{msginfo['data_offset']-1:03x}: Directory ({msginfo['dir_blocks']} blocks, max {msginfo['max_dir_entries']} entries)")
        print(f"  0x{msginfo['data_offset']:03x}+: Data blocks")
        
        data_area_size = len(data) - msginfo['data_offset']
        print(f"\nData area: {data_area_size} bytes")
        print(f"Total blocks: {result['total_blocks']}\n")
    
    print(f"Active messages: {len(result['active_messages'])}")
    print(f"Deleted messages: {len(result['deleted_messages'])}")
    
    if fmt == 'bulletin':
        print(f"Orphaned blocks: {len(result['orphaned_messages'])}")
        
        # Calculate detailed block breakdown
        # Active header blocks (directory entries)
        active_header_blocks = set(msg['block'] for msg in result['active_messages'])
        
        # Active chain blocks (all active blocks minus headers)
        active_chain_blocks = result['active_all_blocks'] - active_header_blocks
        
        # Deleted header blocks
        deleted_header_blocks = set(msg['block'] for msg in result['deleted_messages'])
        
        # Deleted chain blocks (all deleted blocks minus headers)
        deleted_chain_blocks = result['deleted_all_blocks'] - deleted_header_blocks
        
        # Orphaned blocks
        orphaned_blocks = result['orphaned_blocks']
        
        # Unused blocks
        all_used = result['active_all_blocks'] | result['deleted_all_blocks'] | orphaned_blocks
        unused_blocks = result['total_blocks'] - len(all_used)
        
        print(f"\nBlock breakdown:")
        print(f"  Active header blocks: {len(active_header_blocks)}")
        print(f"  Active chain blocks: {len(active_chain_blocks)}")
        print(f"  Deleted header blocks: {len(deleted_header_blocks)}")
        print(f"  Deleted chain blocks: {len(deleted_chain_blocks)}")
        print(f"  Orphaned blocks: {len(orphaned_blocks)}")
        print(f"  Unused blocks: {unused_blocks}")
        print(f"  Total: {result['total_blocks']}")
        
        total_active = len(result['active_all_blocks'])
        print(f"\nUsage: {total_active / result['total_blocks'] * 100:.1f}% active\n")
        
        # Block map for bulletin format only
        print("=== Block Map ===")
        print("Legend: [H]=Active header, [C]=Active chain, [D]=Deleted header, [d]=Deleted chain")
        print("        [o]=Orphaned, [ ]=Unused\n")
        
        for i in range(1, result['total_blocks'] + 1):
            if i in active_header_blocks:
                marker = 'H'
            elif i in active_chain_blocks:
                marker = 'C'
            elif i in deleted_header_blocks:
                marker = 'D'
            elif i in deleted_chain_blocks:
                marker = 'd'
            elif i in orphaned_blocks:
                marker = 'o'
            else:
                marker = ' '
            print(f"[{marker}]", end='')
            if i % 20 == 0:
                print(f"  {i}")
        print()
    else:
        print(f"Orphaned blocks: {len(result['orphaned_messages'])}")
        print(f"Blocks allocated: {len(result['allocated_blocks'])}")
        print(f"Blocks unused: {result['total_blocks'] - len(result['allocated_blocks'])}")
        print(f"Usage: {len(result['allocated_blocks']) / result['total_blocks'] * 100:.1f}%\n")
        print(f"Email format: Directory entries map to user IDs")
        print(f"Messages are EOT-separated (0x04) within user chains")

def prettify_message(message_text, fmt, board_name=None, board_file=None, user_info=None, users=None):
    """
    Convert raw GBBS message format to pretty format.
    
    CUSTOMIZATION NOTE: The header patterns below are based on standard GBBS Pro.
    If your BBS uses different header formats, modify the patterns in this function.
    """
    lines = message_text.split('\n')
    if len(lines) < 4:
        return message_text
    
    if fmt == 'bulletin':
        # Bulletin format:
        # Line 0: Subject
        # Line 1: To (format: "user_id,username" or "0,All")
        # Line 2: From (format: "user_id,username (#user_id)")
        # Line 3: Date line
        
        subject = lines[0]
        
        # Parse To line (CUSTOMIZATION: modify pattern if your BBS uses different format)
        to_match = re.match(r'^(\d+),(.+)$', lines[1])
        if to_match:
            to_id, to_name = to_match.groups()
            to_line = f"To: {to_name.strip()}"
        else:
            to_line = lines[1]
        
        # Parse From line (CUSTOMIZATION: modify pattern if your BBS uses different format)
        # Try format with (#id): "user_id,username (#user_id)"
        from_match = re.match(r'^(\d+),(.+?)\s*\(#(\d+)\)$', lines[2])
        if from_match:
            from_id, from_name, from_id2 = from_match.groups()
            from_name = from_name.strip()
            from_id_int = int(from_id)
            
            # Check if user posted with different name (requires USERS file)
            if users and from_id_int in users:
                actual_name = users[from_id_int].get('full_name', '')
                if actual_name and actual_name != from_name:
                    # User posted with alias
                    from_line = f"From: {from_name} (#{from_id}-{actual_name})"
                else:
                    from_line = f"From: {from_name} (#{from_id})"
            else:
                from_line = f"From: {from_name} (#{from_id})"
        else:
            # Try format without (#id): "user_id,username"
            from_match2 = re.match(r'^(\d+),(.+)$', lines[2])
            if from_match2:
                from_id, from_name = from_match2.groups()
                from_name = from_name.strip()
                from_id_int = int(from_id)
                
                # Check if user posted with different name (requires USERS file)
                if users and from_id_int in users:
                    actual_name = users[from_id_int].get('full_name', '')
                    if actual_name and actual_name != from_name:
                        # User posted with alias
                        from_line = f"From: {from_name} (#{from_id}-{actual_name})"
                    else:
                        from_line = f"From: {from_name} (#{from_id})"
                else:
                    from_line = f"From: {from_name} (#{from_id})"
            else:
                from_line = lines[2]
        
        # Date line (keep as-is, just ensure consistent format)
        date_line = lines[3]
        
        # Build pretty header
        pretty_lines = []
        if board_name and board_file:
            pretty_lines.append(f"Board: {board_name} ({board_file})")
        pretty_lines.append(f"Subject: {subject}")
        pretty_lines.append(to_line)
        pretty_lines.append(from_line)
        pretty_lines.append(date_line)
        pretty_lines.append('')
        
        # Add message body (everything after line 4)
        if len(lines) > 4:
            pretty_lines.extend(lines[4:])
        
        return '\n'.join(pretty_lines)
    
    elif fmt == 'email':
        # Email format (with To: line already prepended):
        # Line 0: To: username (#id)  [added by tool]
        # Line 1: (blank line)
        # Line 2: sender_user_id
        # Line 3: Subj : subject
        # Line 4: From : username (#user_id)
        # Line 5: Date : timestamp
        
        # CUSTOMIZATION: Modify these patterns if your BBS uses different email headers
        to_line = lines[0] if lines[0].startswith('To:') else None
        
        # Find the header lines (skip blank lines and To: line)
        start_idx = 0
        if to_line:
            start_idx = 2  # Skip "To:" and blank line
        
        # Look for sender ID, Subj, From, Date
        sender_id = None
        subject = None
        from_line = None
        date_line = None
        body_start = start_idx
        
        for i in range(start_idx, min(start_idx + 10, len(lines))):
            line = lines[i].strip()
            
            # Sender ID (just a number)
            if sender_id is None and line.isdigit():
                sender_id = line
                body_start = i + 1
                continue
            
            # Subject line (CUSTOMIZATION: modify pattern for your BBS)
            if subject is None and line.startswith('Subj '):
                subject = line.replace('Subj :', 'Subject:', 1).replace('Subj->', 'Subject:', 1)
                body_start = i + 1
                continue
            
            # From line (CUSTOMIZATION: modify pattern for your BBS)
            if from_line is None and line.startswith('From '):
                from_line = line.replace('From :', 'From:', 1).replace('From->', 'From:', 1)
                body_start = i + 1
                continue
            
            # Date line (CUSTOMIZATION: modify pattern for your BBS)
            if date_line is None and 'Date' in line:
                date_line = line.replace('Date :', 'Date:', 1).replace('Date->', 'Date:', 1)
                body_start = i + 1
                break
        
        # Build pretty header
        pretty_lines = []
        if to_line:
            pretty_lines.append(to_line)
        if from_line:
            pretty_lines.append(from_line)
        if subject:
            pretty_lines.append(subject)
        if date_line:
            pretty_lines.append(date_line)
        pretty_lines.append('')
        
        # Add message body
        if body_start < len(lines):
            pretty_lines.extend(lines[body_start:])
        
        return '\n'.join(pretty_lines)
    
    return message_text

def cmd_extract(filename, active=False, deleted=False, orphaned=False, output_dir=None, users_file=None, data2_file=None, force=False, pretty=False):
    """Extract messages from database."""
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{filename}': {e}")
        sys.exit(1)
    
    users = None
    if users_file:
        users = read_users_file(users_file)
        if not users:
            print(f"Warning: Could not read USERS file '{users_file}' or file is empty")
    
    boards = None
    if data2_file:
        boards = read_data2_file(data2_file)
        if not boards:
            print(f"Warning: Could not read DATA2 file '{data2_file}' or file is empty")
    
    result = scan_database(data, users)
    fmt = result['format']
    
    # Check if any messages have dates (indicates standard format)
    has_dates = any(msg.get('date') for msg in result['active_messages'])
    if not has_dates and result['active_messages']:
        print(f"Warning: No standard date headers found in '{filename}'")
        print(f"This file may use a non-standard format. Please report this for tool enhancement.")
        print()
    
    # Default to active if nothing specified
    if not (active or deleted or orphaned):
        active = True
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Check for existing files if not forcing
        if not force:
            existing_files = []
            
            if active:
                for i in range(1, len(result['active_messages']) + 1):
                    filename_out = Path(output_dir) / f"Msg-{i:04d}.txt"
                    if filename_out.exists():
                        existing_files.append(str(filename_out))
            
            if deleted:
                for i in range(1, len(result['deleted_messages']) + 1):
                    filename_out = Path(output_dir) / f"Deleted-{i:04d}.txt"
                    if filename_out.exists():
                        existing_files.append(str(filename_out))
            
            if orphaned:
                for msg in result['orphaned_messages']:
                    filename_out = Path(output_dir) / f"Orphan-{msg['block']:04d}.txt"
                    if filename_out.exists():
                        existing_files.append(str(filename_out))
            
            if existing_files:
                print(f"Error: The following files already exist:")
                for f in existing_files[:10]:  # Show first 10
                    print(f"  {f}")
                if len(existing_files) > 10:
                    print(f"  ... and {len(existing_files) - 10} more")
                print(f"\nUse --force to overwrite existing files")
                sys.exit(1)
    if not (active or deleted or orphaned):
        active = True
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get board name if available
    board_name = None
    board_file = None
    if boards and fmt == 'bulletin':
        board_file = Path(filename).name
        board_name = boards.get(board_file)
    
    # Extract active messages
    if active:
        if not output_dir:
            print("=" * 60)
            print("ACTIVE MESSAGES")
            if board_name:
                print(f"Board: {board_name}")
            print("=" * 60)
        
        for i, msg in enumerate(result['active_messages'], 1):
            # Prepend "To: " line for email format
            message_text = msg['message']
            if fmt == 'email' and msg.get('user_info'):
                message_text = f"To: {msg['user_info']['full_name']} (#{msg['user_id']})\n\n{message_text}"
            elif fmt == 'email':
                message_text = f"To: User ID {msg['user_id']} (#{msg['user_id']})\n\n{message_text}"
            
            # Apply pretty formatting if requested
            if pretty:
                message_text = prettify_message(message_text, fmt, board_name, board_file, msg.get('user_info'), users)
            
            if output_dir:
                filename_out = Path(output_dir) / f"Msg-{i:04d}.txt"
                with open(filename_out, 'w') as f:
                    f.write(message_text)
                if msg.get('date'):
                    timestamp = msg['date'].timestamp()
                    os.utime(filename_out, (timestamp, timestamp))
            else:
                print(f"\n{'='*60}")
                if fmt == 'bulletin':
                    header = f"Message {i} (Entry {msg['entry']}, Block {msg['block']})"
                    if board_name:
                        header += f" - {board_name}"
                    print(header)
                else:
                    # Email format - show user info if available
                    user_info = msg.get('user_info')
                    if user_info:
                        print(f"Message {i} (To: {user_info['full_name']} - User ID {msg['user_id']})")
                    else:
                        print(f"Message {i} (To: User ID {msg['user_id']})")
                print('='*60)
                print(message_text)
    
    # Extract deleted messages
    if deleted:
        if not output_dir:
            print("\n" + "=" * 60)
            print("DELETED MESSAGES")
            if board_name:
                print(f"Board: {board_name}")
            print("=" * 60)
        
        for i, msg in enumerate(result['deleted_messages'], 1):
            message_text = msg['message']
            
            # Apply pretty formatting if requested
            if pretty:
                message_text = prettify_message(message_text, fmt, board_name, board_file, None, users)
            
            if output_dir:
                filename_out = Path(output_dir) / f"Deleted-{i:04d}.txt"
                with open(filename_out, 'w') as f:
                    f.write(message_text)
                if msg.get('date'):
                    timestamp = msg['date'].timestamp()
                    os.utime(filename_out, (timestamp, timestamp))
            else:
                print(f"\n{'='*60}")
                header = f"Deleted Message {i} (Block {msg['block']})"
                if board_name:
                    header += f" - {board_name}"
                print(header)
                print('='*60)
                print(message_text)
    
    # Extract orphaned blocks
    if orphaned:
        if not output_dir:
            print("\n" + "=" * 60)
            print("ORPHANED BLOCKS")
            if board_name:
                print(f"Board: {board_name}")
            print("=" * 60)
        
        for msg in result['orphaned_messages']:
            if output_dir:
                filename_out = Path(output_dir) / f"Orphan-{msg['block']:04d}.txt"
                with open(filename_out, 'w') as f:
                    f.write(msg['message'])
            else:
                print(f"\n{'='*60}")
                header = f"Orphaned Block {msg['block']}"
                if board_name:
                    header += f" - {board_name}"
                print(header)
                print('='*60)
                print(msg['message'])

def main():
    if len(sys.argv) < 2 or '--help' in sys.argv:
        print("GBBS Pro Message Database Tool v1.1.0")
        print("2026-02-05, Brian J. Bernstein  (brian@dronefone.com)")
        print("\nUsage:")
        print("  gbbsmsgtool.py analyze <msgdb_file>")
        print("  gbbsmsgtool.py extract <msgdb_file> [--active] [--deleted] [--orphaned] [--all] [--output-dir <path>] [--users <users_file>] [--data2 <data2_file>] [--pretty] [--force]")
        print("\nCommands:")
        print("  analyze    Show database statistics and block map")
        print("  extract    Extract messages from database")
        print("\nExtract options:")
        print("  --active       Extract active messages (default)")
        print("  --deleted      Extract deleted messages")
        print("  --orphaned     Extract orphaned blocks")
        print("  --all          Extract all types")
        print("  --output-dir   Write to directory instead of stdout")
        print("  --users        Path to USERS file (for email recipient names)")
        print("  --data2        Path to DATA2 file (for board names)")
        print("  --pretty       Format messages with readable headers (default: raw)")
        print("  --force        Overwrite existing files (default: abort if files exist)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Parse --users option
    users_file = None
    if '--users' in sys.argv:
        idx = sys.argv.index('--users')
        if idx + 1 < len(sys.argv):
            users_file = sys.argv[idx + 1]
    
    # Parse --data2 option
    data2_file = None
    if '--data2' in sys.argv:
        idx = sys.argv.index('--data2')
        if idx + 1 < len(sys.argv):
            data2_file = sys.argv[idx + 1]
    
    if command == "analyze":
        if len(sys.argv) < 3:
            print("Error: analyze requires filename")
            sys.exit(1)
        cmd_analyze(sys.argv[2], users_file)
    
    elif command == "extract":
        if len(sys.argv) < 3:
            print("Error: extract requires filename")
            sys.exit(1)
        
        filename = sys.argv[2]
        active = '--active' in sys.argv
        deleted = '--deleted' in sys.argv
        orphaned = '--orphaned' in sys.argv
        all_types = '--all' in sys.argv
        force = '--force' in sys.argv
        pretty = '--pretty' in sys.argv
        
        # Check if user specified what to extract
        if not (active or deleted or orphaned or all_types):
            print("Error: You must specify what to extract")
            sys.argv = []
            main()
        
        if all_types:
            active = deleted = orphaned = True
        
        output_dir = None
        if '--output-dir' in sys.argv:
            idx = sys.argv.index('--output-dir')
            if idx + 1 < len(sys.argv):
                output_dir = sys.argv[idx + 1]
        
        cmd_extract(filename, active, deleted, orphaned, output_dir, users_file, data2_file, force, pretty)
    
    else:
        print(f"Error: Unknown command '{command}'")
        sys.exit(1)

if __name__ == "__main__":
    main()

