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
    return timestamp_to_seconds(start_str), timestamp_to_seconds(end_str), start_str, end_str

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
        raw_block: str = ""
    ):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.text = text
        self.raw_block = raw_block

def parse_srt(srt_content: str) -> List[ParsedCue]:
    """Parse raw SRT content string into a list of ParsedCue objects."""
    if not srt_content or not srt_content.strip():
        raise ValueError("SRT content is empty.")

    content = srt_content.strip("\ufeff")
    # Preserve original line endings by splitting blocks
    blocks = re.split(r"(?:\r?\n){2,}", content.strip())
    cues: List[ParsedCue] = []

    for block_idx, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        
        if lines[0].isdigit():
            idx = int(lines[0])
            time_line_idx = 1
        elif "-->" in lines[0]:
            idx = block_idx
            time_line_idx = 0
        else:
            raise ValueError(f"SRT block #{block_idx} has invalid format: '{lines[0]}'")
        
        if time_line_idx >= len(lines) or "-->" not in lines[time_line_idx]:
            raise ValueError(f"SRT block #{block_idx} missing valid '-->' timestamp line.")
        
        start_sec, end_sec, start_str, end_str = timestamp_to_seconds_pair(lines[time_line_idx])
        
        text_lines = lines[time_line_idx + 1:]
        text = "\n".join(text_lines)
        
        cues.append(ParsedCue(
            index=idx,
            start_time=start_str,
            end_time=end_str,
            start_seconds=start_sec,
            end_seconds=end_sec,
            text=text,
            raw_block=block
        ))

    if not cues:
        raise ValueError("No valid SRT cues could be parsed.")

    return cues

def export_srt(cues_with_revisions: List[Dict[str, Any]]) -> str:
    """
    Build an SRT string from cue objects.
    Preserves exact original block structure for unmodified cues.
    Modifies text for cues with accepted revisions.
    """
    blocks = []
    for cue in sorted(cues_with_revisions, key=lambda c: c["index"]):
        idx = cue["index"]
        start = cue["start_time"]
        end = cue["end_time"]
        text = cue["text"].strip()
        
        # If text is unchanged and original raw_block is present, use raw_block
        if cue.get("is_modified", True) is False and cue.get("raw_block"):
            blocks.append(cue["raw_block"].strip())
        else:
            blocks.append(f"{idx}\n{start} --> {end}\n{text}")
    
    return "\n\n".join(blocks) + "\n"
