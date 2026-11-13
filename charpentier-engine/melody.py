"""
melody.py — Text → Soprano Melody Generator.

Converts a sentence/verse into a Charpentier-style soprano melody (dessus):
1. LLM syllabifies the text and assigns pitches (expressive declamation)
2. Phrase breaks come from punctuation (. , : ; // /)
3. Returns a music21 Part with notes and lyrics attached
"""

from __future__ import annotations
import json
import re
from typing import List, Dict, Optional

import httpx
from music21 import stream, note, key as m21key, pitch, tempo as m21tempo, meter
from music21.note import Lyric as m21Lyric

OLLAMA_BASE = "http://localhost:11434"
CHAT_MODEL  = "llama3.1:8b"

_MELODY_SYSTEM = """You are a music specialist in Marc-Antoine Charpentier's style. Given a text (Latin or French) and a musical key, compose a soprano melody (dessus) that follows French Baroque declamation principles — one note per syllable, reflecting the natural prosody.

RULES:
1. Syllabification: Split every word into syllables (hyphenate: "glo-ri-a", "chan-ter").
2. Phrase Structure: Use punctuation (. , : ; // /) as phrase markers. Charpentier's phrases are flexible and expressive, not strictly periodic.
3. Melodic Contour:
   • Speech-like declamation: follow the natural accents of the language.
   • Elegant contours: mostly stepwise, with expressive leaps (3rds, 4ths) for important words.
   • Range: Stay within C4 to G5 (soprano/dessus).
4. Rhythm:
   • Flexible, guided by the text.
   • Stressed syllables: quarter notes (1) or dotted rhythms.
   • Unstressed syllables: quarter notes (1) or eighth notes (0.5 if you can, but use 1 for simplicity if needed).
   • Phrase ends: longer durations (2 or 4).
5. Cadences:
   • Final phrase: end on the tonic (scale degree 1).
   • Inner phrases: can end on scale degree 2, 5, or 3 (modal flavor).

Return ONLY valid JSON, no markdown fences, no commentary:
{
  "key": "G minor",
  "syllables": ["Ve-", "ni", "Cre-", "a-", "tor", "Spi-", "ri-", "tus"],
  "pitches": ["G4", "A4", "Bb4", "A4", "G4", "C5", "Bb4", "A4"],
  "durations": [1, 1, 1, 1, 2, 1, 1, 4],
  "phrase_ends": [4, 7]
}

NOTES: use pitch names with octave (C4=middle C). Support durations like 0.5, 1, 1.5, 2, 4.
Always ensure the last note is the tonic with duration 4.
"""


async def text_to_melody(
    text: str,
    ollama_base: str = OLLAMA_BASE,
    model: str = CHAT_MODEL,
) -> Optional[Dict]:
    """Call LLM to parse text into soprano melody data."""
    user_msg = f"Text to set as a Charpentier-style melody:\n\n\"{text}\"\n\nGenerate the JSON now."
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{ollama_base}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _MELODY_SYSTEM},
                        {"role": "user",   "content": user_msg},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.4, "num_predict": 400},
                },
            )
            r.raise_for_status()
            content = r.json().get("message", {}).get("content", "")
            # Extract JSON from response
            start = content.find("{")
            end   = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
    except Exception as e:
        print(f"[Melody] LLM call failed: {e}")
    return None


def build_soprano_part(
    melody_data: Dict,
    key_sig: m21key.Key,
    time_sig: str = "4/4",
) -> stream.Part:
    """Convert melody dict → music21 Part with notes and lyrics."""
    part = stream.Part()
    part.partName = "Soprano"
    part.partAbbreviation = "S"

    syllables = melody_data.get("syllables", [])
    pitches   = melody_data.get("pitches",   [])
    durations = melody_data.get("durations", [])
    phrase_ends = set(melody_data.get("phrase_ends", []))

    # Pad / trim to same length
    n = min(len(syllables), len(pitches), len(durations))
    syllables = syllables[:n]
    pitches   = pitches[:n]
    durations = durations[:n]

    # Build measures
    ts = meter.TimeSignature(time_sig)
    beats_per_measure = ts.barDuration.quarterLength
    current_measure = stream.Measure()
    current_measure.timeSignature = ts
    current_measure.number = 1
    current_beats = 0
    m_num = 1

    for i, (syl, pit, dur) in enumerate(zip(syllables, pitches, durations)):
        # Parse pitch
        try:
            p = pitch.Pitch(pit)
            n_obj = note.Note(p, quarterLength=float(dur))
        except Exception:
            n_obj = note.Note("C4", quarterLength=float(dur))

        # Add lyric — determine syllabic position from hyphen markers
        syl_clean = syl.strip("-")
        if not syl_clean:
            syl_clean = syl  # fallback if entirely hyphens
        starts_dash = syl.startswith("-")
        ends_dash   = syl.endswith("-")
        if starts_dash and ends_dash:
            syllabic = "middle"
        elif starts_dash:
            syllabic = "end"
        elif ends_dash:
            syllabic = "begin"
        else:
            syllabic = "single"
        lyric_obj = m21Lyric(text=syl_clean, number=1, syllabic=syllabic)
        n_obj.lyrics.append(lyric_obj)

        remaining = beats_per_measure - current_beats
        if float(dur) <= remaining:
            current_measure.append(n_obj)
            current_beats += float(dur)
        else:
            # Note doesn't fit: close current measure and start new one
            if current_beats < beats_per_measure:
                from music21 import note as m21note
                rest = m21note.Rest(quarterLength=float(beats_per_measure - current_beats))
                current_measure.append(rest)
            part.append(current_measure)
            m_num += 1
            current_measure = stream.Measure(number=m_num)
            current_measure.append(n_obj)
            current_beats = float(dur)

        # After phrase end: close measure
        if i in phrase_ends and current_beats > 0:
            if current_beats < beats_per_measure:
                from music21 import note as m21note
                rest = m21note.Rest(quarterLength=float(beats_per_measure - current_beats))
                current_measure.append(rest)
            part.append(current_measure)
            m_num += 1
            current_measure = stream.Measure(number=m_num)
            current_beats = 0

    # Append last measure
    if current_beats > 0 or len(list(current_measure.flatten().notes)) > 0:
        if current_beats < beats_per_measure:
            from music21 import note as m21note
            rest = m21note.Rest(quarterLength=float(beats_per_measure - current_beats))
            current_measure.append(rest)
        part.append(current_measure)

    return part


def fallback_melody(text: str, key_sig: m21key.Key) -> Dict:
    """
    Simple rule-based fallback if LLM fails.
    Treats each word as one syllable and walks up/down the scale.
    """
    # Clean text
    clean = re.sub(r"[^a-zA-Z\s//]", " ", text)
    words = clean.split()

    scale = key_sig.getScale()
    tonic_midi = pitch.Pitch(key_sig.tonic.name + "4").midi
    scale_pitches = []
    for deg in range(1, 9):
        try:
            p = scale.pitchFromDegree(deg)
            p.octave = 4
            # Keep in soprano range 60-79
            while p.midi < 60: p.octave += 1
            while p.midi > 79: p.octave -= 1
            scale_pitches.append(p.nameWithOctave)
        except Exception:
            scale_pitches.append("G4")

    # Simple arch: rise for first half, fall for second half
    n = len(words)
    pitches = []
    for i, word in enumerate(words):
        progress = i / max(n - 1, 1)
        if progress < 0.5:
            deg = int(progress * 2 * 4) + 1  # degrees 1-5
        else:
            deg = int((1 - progress) * 2 * 4) + 1
        deg = max(1, min(deg, len(scale_pitches)))
        pitches.append(scale_pitches[deg - 1])

    # Last note = tonic
    pitches[-1] = pitch.Pitch(key_sig.tonic.name + "4").nameWithOctave

    # Find phrase breaks at sentence markers
    phrase_ends = []
    full_words = text.split()
    syl_idx = 0
    for i, w in enumerate(full_words):
        syl_idx += 1
        if any(c in w for c in [".", ":", ";", "//", "/"]):
            phrase_ends.append(min(syl_idx - 1, n - 1))

    return {
        "key": f"{key_sig.tonic.name} {key_sig.mode}",
        "syllables": words,
        "pitches": pitches,
        "durations": [1 if i < n - 1 else 2 for i in range(n)],
        "phrase_ends": phrase_ends or [n - 1],
    }
