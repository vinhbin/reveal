import re
from typing import List, Dict, Any, Tuple, Optional

TIMESTAMP_REGEX = re.compile(
    r"^(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})$"
)

def timestamp_to_seconds(ts_str: str) -> float:
    """Convert HH:MM:SS,mmm string to float seconds."""
    ts_str = ts_str.strip()
    match = TIMESTAMP_REGEX.match(ts_str)
    if not match:
        parts = re.split(r"[:,\.]", ts_str)
        if len(parts) >= 4:
            hours, mins, secs, millis = map(int, parts[:4])
            return hours * 3600 + mins * 60 + secs + millis / 1000.0
        raise ValueError(f"Invalid SRT timestamp format: '{ts_str}'")
    
    hours, mins, secs, millis = map(int, match.groups()[:4])
    return hours * 3600 + mins * 60 + secs + millis / 1000.0

def timestamp_to_seconds_pair(time_line: str) -> Tuple[float, float, str, str]:
    """Parse time line e.g., '00:00:01,000 --> 00:00:04,500' returning (start_sec, end_sec, start_str, end_str)."""
    if "-->" not in time_line:
        raise ValueError(f"Invalid timestamp line missing '-->': '{time_line}'")
    parts = time_line.split("-->")
    start_str = parts[0].strip()
    end_str = parts[1].strip()
    start_sec = timestamp_to_seconds(start_str)
    end_sec = timestamp_to_seconds(end_str)
    if start_sec >= end_sec:
        raise ValueError(f"Invalid timestamp interval: start ({start_str}) must be strictly before end ({end_str}).")
    return start_sec, end_sec, start_str, end_str

def seconds_to_timestamp(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS,mmm format."""
    total_millis = int(round(seconds * 1000))
    hours = total_millis // (3600 * 1000)
    remainder = total_millis % (3600 * 1000)
    minutes = remainder // (60 * 1000)
    remainder %= (60 * 1000)
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

class ParsedCue:
    def __init__(
        self,
        index: int,
        start_time: str,
        end_time: str,
        start_seconds: float,
        end_seconds: float,
        text: str,
        raw_block: str = "",
        raw_header: str = "",
        start_char: int = 0,
        end_char: int = 0
    ):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.text = text
        self.raw_block = raw_block
        self.raw_header = raw_header
        self.start_char = start_char
        self.end_char = end_char

def detect_line_ending(content: str) -> str:
    """Detect whether file uses CRLF or LF."""
    if "\r\n" in content:
        return "\r\n"
    return "\n"

def parse_srt(srt_content: str) -> List[ParsedCue]:
    """Parse raw SRT content string into a list of ParsedCue objects with exact boundary tracking."""
    if not srt_content or not srt_content.strip():
        raise ValueError("SRT content is empty.")

    clean_content = srt_content.lstrip("\ufeff")
    
    # Split content by double newlines while tracking positions
    delimiter_regex = re.compile(r"(\r?\n){2,}")
    raw_blocks: List[Tuple[str, int, int]] = []
    
    last_end = 0
    for match in delimiter_regex.finditer(clean_content):
        block_str = clean_content[last_end:match.start()]
        if block_str.strip():
            raw_blocks.append((block_str, last_end, match.start()))
        last_end = match.end()
    
    remaining = clean_content[last_end:]
    if remaining.strip():
        raw_blocks.append((remaining, last_end, len(clean_content)))

    cues: List[ParsedCue] = []
    seen_indices = set()

    for block_idx, (block, start_pos, end_pos) in enumerate(raw_blocks, start=1):
        lines = block.splitlines(keepends=True)
        stripped_lines = [l.strip() for l in lines if l.strip()]
        if not stripped_lines:
            continue
        
        # Check ID line
        if stripped_lines[0].isdigit():
            idx = int(stripped_lines[0])
            time_line_idx = 1
        elif "-->" in stripped_lines[0]:
            idx = block_idx
            time_line_idx = 0
        else:
            raise ValueError(f"SRT block #{block_idx} has invalid format: '{stripped_lines[0]}'")
        
        if idx in seen_indices:
            raise ValueError(f"Duplicate cue index #{idx} found in SRT.")
        seen_indices.add(idx)

        if time_line_idx >= len(stripped_lines) or "-->" not in stripped_lines[time_line_idx]:
            raise ValueError(f"SRT block #{block_idx} missing valid '-->' timestamp line.")
        
        start_sec, end_sec, start_str, end_str = timestamp_to_seconds_pair(stripped_lines[time_line_idx])
        
        # Header is lines up to time_line_idx inclusive
        header_text = "".join(lines[:time_line_idx + 1])
        text_lines_raw = lines[time_line_idx + 1:]
        text = "".join(text_lines_raw).strip()
        
        cues.append(ParsedCue(
            index=idx,
            start_time=start_str,
            end_time=end_str,
            start_seconds=start_sec,
            end_seconds=end_sec,
            text=text,
            raw_block=block,
            raw_header=header_text,
            start_char=start_pos,
            end_char=end_pos
        ))

    if not cues:
        raise ValueError("No valid SRT cues could be parsed.")

    return cues

def _find_cue_spans(raw_bytes: bytes) -> Dict[int, Tuple[int, int]]:
    """Locate (text_start_byte, text_end_byte) for each cue index in raw_bytes."""
    delimiter = re.compile(rb"(\r?\n){2,}")
    spans = {}
    bom_len = 3 if raw_bytes.startswith(b"\xef\xbb\xbf") else 0
    last_end = bom_len
    block_seq = 1

    for m in delimiter.finditer(raw_bytes, bom_len):
        block_bytes = raw_bytes[last_end:m.start()]
        if block_bytes.strip():
            _process_byte_block(block_bytes, last_end, spans, block_seq)
            block_seq += 1
        last_end = m.end()

    rem = raw_bytes[last_end:]
    if rem.strip():
        _process_byte_block(rem, last_end, spans, block_seq)
    return spans

def _process_byte_block(block_bytes: bytes, block_start: int, spans: Dict[int, Tuple[int, int]], block_seq: int):
    lines = block_bytes.splitlines(keepends=True)
    if not lines:
        return
    idx = None
    time_line_idx = None
    first_clean = lines[0].strip()
    if first_clean.isdigit():
        idx = int(first_clean)
        time_line_idx = 1
    elif b"-->" in lines[0]:
        idx = block_seq
        time_line_idx = 0

    if time_line_idx is not None and time_line_idx < len(lines) and b"-->" in lines[time_line_idx]:
        header_len = sum(len(l) for l in lines[:time_line_idx + 1])
        text_start = block_start + header_len
        trailing_newlines = len(block_bytes) - len(block_bytes.rstrip(b"\r\n"))
        text_end = block_start + len(block_bytes) - trailing_newlines
        spans[idx] = (text_start, text_end)

def export_srt_bytes(
    raw_bytes: bytes,
    cues: List[Any],
    cue_revisions: Dict[int, str]
) -> bytes:
    """
    Build byte-exact SRT export.
    If no cues were revised, returns raw_bytes directly (100% byte-for-byte match).
    For revised cues, performs in-place byte span replacements, preserving BOM,
    cue ID formatting, timestamp spacing, line endings, and inter-block separators.
    """
    if not cue_revisions:
        return raw_bytes

    if not raw_bytes:
        return export_srt([
            {
                "index": getattr(c, "index", 0),
                "start_time": getattr(c, "start_time", ""),
                "end_time": getattr(c, "end_time", ""),
                "text": cue_revisions.get(getattr(c, "index", 0), getattr(c, "text", "")),
                "is_modified": getattr(c, "index", 0) in cue_revisions
            }
            for c in cues
        ]).encode("utf-8")

    spans = _find_cue_spans(raw_bytes)
    targets = [(spans[idx], cue_revisions[idx]) for idx in cue_revisions if idx in spans]

    if targets:
        # In-place byte replacement in reverse order so byte offsets do not shift
        targets.sort(key=lambda t: t[0][0], reverse=True)
        out = bytearray(raw_bytes)
        for (s, e), new_text in targets:
            encoded = new_text.strip().encode("utf-8")
            out[s:e] = encoded
        return bytes(out)

    # Fallback to rebuilding if byte spans could not be matched
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = raw_bytes.decode("utf-8-sig")

    line_ending = detect_line_ending(raw_text)
    blocks = []
    for cue in sorted(cues, key=lambda c: getattr(c, "index", 0)):
        idx = getattr(cue, "index", 0)
        raw_block = getattr(cue, "raw_block", "")
        raw_header = getattr(cue, "raw_header", "")
        start_time = getattr(cue, "start_time", "")
        end_time = getattr(cue, "end_time", "")

        if idx in cue_revisions:
            new_text = cue_revisions[idx].strip()
            if raw_header:
                header = raw_header
                if not header.endswith("\n"):
                    header += line_ending
                blocks.append(f"{header}{new_text}")
            else:
                blocks.append(f"{idx}{line_ending}{start_time} --> {end_time}{line_ending}{new_text}")
        else:
            if raw_block:
                blocks.append(raw_block.strip("\r\n"))
            else:
                text = getattr(cue, "text", getattr(cue, "original_text", "")).strip()
                blocks.append(f"{idx}{line_ending}{start_time} --> {end_time}{line_ending}{text}")

    separator = f"{line_ending}{line_ending}"
    exported_text = separator.join(blocks)
    if not exported_text.endswith(line_ending):
        exported_text += line_ending

    return exported_text.encode("utf-8")

def export_srt(cues_with_revisions: List[Dict[str, Any]]) -> str:
    """Fallback string export preserving block structure."""
    blocks = []
    sample_text = "\n"
    for cue in cues_with_revisions:
        if cue.get("raw_block") and "\r\n" in cue["raw_block"]:
            sample_text = "\r\n"
            break
    
    line_ending = sample_text
    
    for cue in sorted(cues_with_revisions, key=lambda c: c["index"]):
        idx = cue["index"]
        start = cue["start_time"]
        end = cue["end_time"]
        text = cue["text"].strip()
        raw_block = cue.get("raw_block", "")
        raw_header = cue.get("raw_header", "")
        
        if cue.get("is_modified", True) is False and raw_block:
            blocks.append(raw_block.strip("\r\n"))
        elif raw_header:
            header = raw_header
            if not header.endswith("\n"):
                header += line_ending
            blocks.append(f"{header}{text}")
        else:
            blocks.append(f"{idx}{line_ending}{start} --> {end}{line_ending}{text}")
    
    separator = f"{line_ending}{line_ending}"
    return separator.join(blocks) + line_ending
