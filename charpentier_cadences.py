"""Write and read the cadences of an eight-measure, two-phrase SATB study."""
from music21 import key, meter as m21meter, roman, stream
from music21.interval import Interval

from charpentier_settings import INTERVALS, MINOR_INTERVALS
from charpentier_voiceleading import events, harmonize_study, progressions


def _read_chord(voices, at, figure, tonality):
    actual = [voice[at].pitch for voice in voices]
    chord = roman.RomanNumeral(figure, tonality)
    return ({p.name for p in actual} == {p.name for p in chord.pitches}
            and actual[-1].name == chord.bass().name)


def _read_cadence(score, bar, tonality):
    voices = events(score, bar)
    for kind, (before, after) in progressions(tonality.mode).items():
        if (kind != 'perfect' or voices[0][-1].pitch.name == tonality.tonic.name
            ) and _read_chord(voices, -2, before, tonality) and _read_chord(voices, -1, after, tonality):
            return kind, before.replace('o', '°'), after
    raise ValueError('Could not identify the cadence in the written voices.')


def _display(p):
    return p.nameWithOctave.replace('-', '♭').replace('#', '♯')


def finalize(score, mode, meter, cadence, shift, tonic, *, preserve_soprano=False):
    """Harmonize eight bars in place and return an analysis of the resulting score.

    shift is the public key-selector value from charpentier_settings, tonic the
    music21 tonic name of the already transposed score (e.g., 'B-').
    """
    tonality = key.Key(tonic, mode)
    transposition = Interval((MINOR_INTERVALS if mode == 'minor' else INTERVALS)[shift]).semitones
    if cadence not in progressions(mode):
        raise ValueError('Unknown cadence.')
    harmonize_study(score, tonality, transposition, cadence, preserve_soprano=preserve_soprano)
    opening, _, _ = _read_cadence(score, 4, tonality)
    final_kind, penultimate, final = _read_cadence(score, 8, tonality)
    if (opening, final_kind) != ('half', cadence):
        raise ValueError('Unexpected written cadence.')
    soprano = score.parts[0]
    actual_key = soprano.recurse().getElementsByClass(key.KeySignature).first()
    actual_meter = soprano.recurse().getElementsByClass(m21meter.TimeSignature).first()
    if actual_key.sharps != tonality.sharps or actual_meter.ratioString != meter:
        raise ValueError('Score signature and generation settings disagree.')
    notes = [(m.number, n.pitch) for m in soprano.getElementsByClass(stream.Measure) for n in m.flatten().notes]
    low, high = min(p for _, p in notes), max(p for _, p in notes)
    return dict(mode=mode, meter=actual_meter.ratioString, tonic=tonality.tonic.name,
                cadence=final_kind, openingCadence=opening, penultimate=penultimate, final=final,
                low=_display(low), high=_display(high), peakBars=sorted({b for b, p in notes if p.ps == high.ps}))
