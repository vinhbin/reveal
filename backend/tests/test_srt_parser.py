import pytest
from backend.srt_parser import (
    parse_srt,
    export_srt,
    timestamp_to_seconds,
    seconds_to_timestamp
)

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:04,500
First Audio Description line.

2
00:00:05,000 --> 00:00:09,250
Second Audio Description line mentioning Detective Vance.
"""

def test_timestamp_conversions():
    sec = timestamp_to_seconds("00:01:15,500")
    assert sec == 75.5
    ts_str = seconds_to_timestamp(75.5)
    assert ts_str == "00:01:15,500"

def test_parse_srt():
    cues = parse_srt(SAMPLE_SRT)
    assert len(cues) == 2
    assert cues[0].index == 1
    assert cues[0].start_seconds == 1.0
    assert cues[0].end_seconds == 4.5
    assert cues[0].text == "First Audio Description line."

    assert cues[1].index == 2
    assert cues[1].start_seconds == 5.0
    assert cues[1].end_seconds == 9.25
    assert "Detective Vance" in cues[1].text

def test_untouched_export_preserves_content():
    cues = parse_srt(SAMPLE_SRT)
    cue_dicts = [
        {"index": c.index, "start_time": c.start_time, "end_time": c.end_time, "text": c.text}
        for c in cues
    ]
    exported = export_srt(cue_dicts)
    reparsed = parse_srt(exported)
    
    assert len(reparsed) == len(cues)
    for orig, rep in zip(cues, reparsed):
        assert orig.index == rep.index
        assert orig.start_time == rep.start_time
        assert orig.end_time == rep.end_time
        assert orig.text == rep.text

def test_export_with_revision():
    cues = parse_srt(SAMPLE_SRT)
    cue_dicts = [
        {"index": c.index, "start_time": c.start_time, "end_time": c.end_time, "text": c.text}
        for c in cues
    ]
    # Modify cue #2 text
    cue_dicts[1]["text"] = "Second line mentioning a masked investigator."

    exported = export_srt(cue_dicts)
    reparsed = parse_srt(exported)
    assert reparsed[1].text == "Second line mentioning a masked investigator."
    assert reparsed[1].start_time == cues[1].start_time
