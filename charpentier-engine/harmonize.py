"""
harmonize.py — Soprano → SATB Harmonizer.

Given a soprano Part (with lyrics from melody.py), generates Alto, Tenor, Bass parts
using scale-degree chord selection and greedy voice-leading.
Returns a 4-part music21 Score ready for export.
"""

from __future__ import annotations
import copy
from typing import List, Tuple, Optional, Set

from music21 import (
    stream, note, pitch, key as m21key, clef as m21clef,
    meter, tempo as m21tempo, metadata, roman
)

# ── MIDI note ranges for each voice ──────────────────────────────────────────
VOICE_MIDI = {
    "S": (60, 81),   # C4–A5
    "A": (55, 76),   # G3–E5
    "T": (47, 69),   # B2–A4
    "B": (38, 64),   # Eb2–E4
}

# ── Preferred Roman numerals per soprano scale degree ────────────────────────
_MAJOR_PREF: dict = {
    1: ["I",  "vi"],
    2: ["V",  "ii"],
    3: ["I",  "iii"],
    4: ["IV", "ii"],
    5: ["V",  "I"],
    6: ["vi", "IV"],
    7: ["V"],
}
_MINOR_PREF: dict = {
    1: ["i",   "VI"],
    2: ["V",   "iv"],
    3: ["III", "i"],
    4: ["iv",  "ii"],
    5: ["V",   "v"],
    6: ["VI",  "iv"],
    7: ["V"],
}


def _rn_steps(rn_str: str, key_sig: m21key.Key) -> Optional[Set[str]]:
    """Pitch step names for a Roman numeral chord in the given key."""
    try:
        rn = roman.RomanNumeral(rn_str, key_sig)
        return {p.name for p in rn.pitches}
    except Exception:
        return None


def _soprano_degree(p: pitch.Pitch, key_sig: m21key.Key) -> int:
    """Scale degree (1–7) of a pitch in the key."""
    try:
        deg = key_sig.getScaleDegreeFromPitch(p, comparisonAttribute='step')
        return deg or 1
    except Exception:
        return 1


def _midi_for_steps(steps: Set[str], lo: int, hi: int) -> List[int]:
    """All MIDI values for the given pitch step names within [lo, hi]."""
    result: List[int] = []
    for step in steps:
        for octave in range(1, 8):
            try:
                m = pitch.Pitch(f"{step}{octave}").midi
                if lo <= m <= hi:
                    result.append(m)
            except Exception:
                pass
    return sorted(result)


def _nearest(options: List[int], target: int) -> Optional[int]:
    return min(options, key=lambda m: abs(m - target)) if options else None


def _smooth(options: List[int], target: int, max_leap: int = 7) -> int:
    """Pick option closest to target, strongly preferring leaps ≤ max_leap semitones."""
    if not options:
        return target
    close = [m for m in options if abs(m - target) <= max_leap]
    if close:
        return min(close, key=lambda m: abs(m - target))
    # Accept up to an octave before falling back to global nearest
    reachable = [m for m in options if abs(m - target) <= 12]
    if reachable:
        return min(reachable, key=lambda m: abs(m - target))
    return _nearest(options, target)


def _select_rn(
    deg: int, key_sig: m21key.Key, soprano_step: str,
    is_final: bool, is_phrase_end: bool, prev_rn: Optional[str],
) -> str:
    """Pick the best Roman numeral for the given soprano scale degree and context."""
    mode = key_sig.mode
    pref = _MINOR_PREF if mode == "minor" else _MAJOR_PREF
    tonic_rn = "i" if mode == "minor" else "I"

    if is_final:
        return tonic_rn
    if is_phrase_end and deg in (2, 5, 7):
        return "V"

    for rn_str in pref.get(deg, [tonic_rn]):
        steps = _rn_steps(rn_str, key_sig)
        if steps and soprano_step in steps:
            return rn_str
    return pref.get(deg, [tonic_rn])[0]


def _parallel_interval(v1p: int, v1c: int, v2p: int, v2c: int) -> bool:
    """True if two voices move in parallel to a perfect 5th or octave."""
    int_before = abs(v1p - v2p) % 12
    int_after  = abs(v1c - v2c) % 12
    if int_after not in (0, 7):
        return False
    if int_before != int_after:
        return False
    return (v1c - v1p) * (v2c - v2p) > 0


def _voice_chord(
    soprano_midi: int,
    steps: Set[str],
    key_sig: m21key.Key,
    rn_str: str,
    prev_soprano: Optional[int],
    prev_atb: Optional[Tuple[int, int, int]],
    is_phrase_end: bool,
) -> Tuple[int, int, int]:
    """Select (alto, tenor, bass) MIDI pitches for the chord and soprano."""
    a_lo, a_hi = VOICE_MIDI["A"]
    t_lo, t_hi = VOICE_MIDI["T"]
    b_lo, b_hi = VOICE_MIDI["B"]

    a_opts = _midi_for_steps(steps, a_lo, min(a_hi, soprano_midi - 1))
    t_opts = _midi_for_steps(steps, t_lo, t_hi)
    b_opts = _midi_for_steps(steps, b_lo, b_hi)

    # Prefer root in bass at phrase ends and on the first chord
    if is_phrase_end or prev_atb is None:
        try:
            rn = roman.RomanNumeral(rn_str, key_sig)
            root_pc = rn.root().pitchClass
            root_b = [m for m in b_opts if m % 12 == root_pc]
            if root_b:
                b_opts = root_b
        except Exception:
            pass

    prev_b = prev_atb[2] if prev_atb else 48   # C3
    prev_t = prev_atb[1] if prev_atb else 60   # C4
    prev_a = prev_atb[0] if prev_atb else 65   # F4

    # Bass — prefer ≤ P5 motion; avoid parallel 5th/8ve with soprano
    b_candidates = b_opts[:]
    if prev_soprano is not None and prev_atb and b_candidates:
        b_no_par = [m for m in b_candidates
                    if not _parallel_interval(prev_soprano, soprano_midi, prev_b, m)]
        if b_no_par:
            b_candidates = b_no_par
    bass = _smooth(b_candidates, prev_b, max_leap=7) if b_candidates else prev_b

    # Tenor — above bass; prefer stepwise; avoid parallel 5th/8ve with bass
    t_above = [m for m in t_opts if m > bass]
    t_candidates = t_above or t_opts
    if prev_atb and t_candidates:
        t_no_par = [m for m in t_candidates
                    if not _parallel_interval(prev_t, m, prev_b, bass)]
        if t_no_par:
            t_candidates = t_no_par
    tenor = _smooth(t_candidates, prev_t, max_leap=5) if t_candidates else max(bass + 4, prev_t)

    # Alto — between tenor and soprano; avoid parallel 5th/8ve with bass, tenor, soprano
    a_mid = [m for m in a_opts if tenor <= m < soprano_midi]
    a_candidates = a_mid or a_opts
    if prev_atb and a_candidates:
        a_no_par = [m for m in a_candidates
                    if not _parallel_interval(prev_a, m, prev_b, bass)
                    and not _parallel_interval(prev_a, m, prev_t, tenor)
                    and (prev_soprano is None
                         or not _parallel_interval(prev_soprano, soprano_midi, prev_a, m))]
        if a_no_par:
            a_candidates = a_no_par
    alto = _smooth(a_candidates, prev_a, max_leap=5) if a_candidates else max(tenor, min(soprano_midi - 1, prev_a))
    alto = max(tenor, min(soprano_midi - 1, alto))

    return (alto, tenor, bass)


def harmonize_soprano(
    soprano_part: stream.Part,
    key_sig: m21key.Key,
    time_sig: str = "4/4",
    title: str = "",
    subtitle: str = "",
    tempo_bpm: int = 72,
    composer: str = "M.A. Charpentier × AI",
    copyright_str: str = "Xavier Fresquet · Sorbonne Université",
) -> stream.Score:
    """
    Takes a soprano Part with lyrics and returns a 4-voice SATB Score (Charpentier style).
    """
    # Gather soprano notes in measure order
    soprano_notes: List[note.Note] = []
    for m in soprano_part.getElementsByClass(stream.Measure):
        for elem in m.flatten().getElementsByClass(note.Note):
            soprano_notes.append(elem)

    n = len(soprano_notes)
    prev_atb: Optional[Tuple[int, int, int]] = None
    prev_rn: Optional[str] = None
    prev_soprano_midi: Optional[int] = None
    all_atb: List[Tuple[int, int, int]] = []

    for i, sn in enumerate(soprano_notes):
        is_final = (i == n - 1)
        # Charpentier uses longer notes at phrase ends, but often more fluidly than Bach
        is_phrase_end = is_final or sn.duration.quarterLength >= 2.0

        deg = _soprano_degree(sn.pitch, key_sig)
        rn_str = _select_rn(deg, key_sig, sn.pitch.name, is_final, is_phrase_end, prev_rn)
        steps = _rn_steps(rn_str, key_sig) or {sn.pitch.name}

        atb = _voice_chord(sn.pitch.midi, steps, key_sig, rn_str, prev_soprano_midi, prev_atb, is_phrase_end)
        all_atb.append(atb)
        prev_atb = atb
        prev_rn = rn_str
        prev_soprano_midi = sn.pitch.midi

    # ── Build Score ────────────────────────────────────────────────────────────
    score = stream.Score()

    md = metadata.Metadata()
    md.title = title or "Charpentier Motet"
    if subtitle:
        md.movementName = subtitle
    md.composer = composer
    md.copyright = copyright_str
    score.insert(0, md)

    # Clone soprano; set clef, key, tempo on first measure
    s_part = copy.deepcopy(soprano_part)
    s_part.partName = "Dessus"
    s_part.partAbbreviation = "D"
    s_measures = list(s_part.getElementsByClass(stream.Measure))
    if s_measures:
        m0 = s_measures[0]
        for c in list(m0.getElementsByClass(m21clef.Clef)):
            m0.remove(c)
        m0.insert(0, m21clef.TrebleClef())
        m0.insert(0, m21key.Key(key_sig.tonic.name, key_sig.mode))
        m0.insert(0, m21tempo.MetronomeMark(number=tempo_bpm))

    # Build ATB parts mirroring the soprano measure structure
    a_part = stream.Part(id="Haute-Contre")
    a_part.partName = "Haute-Contre"
    a_part.partAbbreviation = "HC"

    t_part = stream.Part(id="Taille")
    t_part.partName = "Taille"
    t_part.partAbbreviation = "T"

    b_part = stream.Part(id="Basse")
    b_part.partName = "Basse"
    b_part.partAbbreviation = "B"

    ts = meter.TimeSignature(time_sig)
    ks = m21key.Key(key_sig.tonic.name, key_sig.mode)

    note_idx = 0
    for s_m in soprano_part.getElementsByClass(stream.Measure):
        m_num = s_m.number
        a_m = stream.Measure(number=m_num)
        t_m = stream.Measure(number=m_num)
        b_m = stream.Measure(number=m_num)

        if m_num == 1:
            a_m.insert(0, m21clef.TrebleClef())
            a_m.insert(0, copy.deepcopy(ts))
            a_m.insert(0, copy.deepcopy(ks))
            t_m.insert(0, m21clef.AltoClef())
            t_m.insert(0, copy.deepcopy(ts))
            t_m.insert(0, copy.deepcopy(ks))
            b_m.insert(0, m21clef.BassClef())
            b_m.insert(0, copy.deepcopy(ts))
            b_m.insert(0, copy.deepcopy(ks))

        for elem in s_m:
            ql = elem.duration.quarterLength
            if isinstance(elem, note.Note):
                if note_idx < len(all_atb):
                    a_midi, t_midi, b_midi = all_atb[note_idx]
                    a_m.append(note.Note(pitch.Pitch(midi=a_midi), quarterLength=ql))
                    t_m.append(note.Note(pitch.Pitch(midi=t_midi), quarterLength=ql))
                    b_m.append(note.Note(pitch.Pitch(midi=b_midi), quarterLength=ql))
                    note_idx += 1
            elif isinstance(elem, note.Rest):
                a_m.append(note.Rest(quarterLength=ql))
                t_m.append(note.Rest(quarterLength=ql))
                b_m.append(note.Rest(quarterLength=ql))

        a_part.append(a_m)
        t_part.append(t_m)
        b_part.append(b_m)

    score.append(s_part)
    score.append(a_part)
    score.append(t_part)
    score.append(b_part)

    return score
