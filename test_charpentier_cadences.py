"""Read the harmony and timing from all four written voices."""
from music21 import chord, converter, key, meter, note, roman, stream
import pytest

from charpentier_cadences import finalize


def study(tonic, mode, transposition, n):
    score = stream.Score()
    for voice, start in enumerate((72, 67, 60, 48)):
        part = stream.Part()
        for bar in range(1, 9):
            measure = stream.Measure(number=bar)
            if bar == 1:
                measure.insert(0, key.Key(tonic, mode))
                measure.timeSignature = meter.TimeSignature('4/4')
            for i in range(n):
                event = note.Note(start + transposition + i, quarterLength=4 / n)
                if voice == 0:
                    event.lyric = 'laus'
                measure.append(event)
            part.append(measure)
        score.append(part)
    return score


@pytest.mark.parametrize('cadence,n', [('perfect', 4), ('plagal', 2), ('half', 3), ('deceptive', 4)])
@pytest.mark.parametrize('mode', ['major', 'minor'])
def test_shifted_cadence_round_trip(tmp_path, mode, cadence, n):
    tunings = [('C', 0 if mode == 'major' else 3, 0), ('D', 2 if mode == 'major' else 5, 2)]
    pitches = []
    for tonic, shift, transposition in tunings:
        source = study(tonic, mode, transposition, n)
        result = finalize(source, mode, '4/4', cadence, shift, tonic)
        parsed = converter.parse(source.write('musicxml', fp=tmp_path / f'{tonic}.musicxml'))
        tonality = key.Key(tonic, mode)
        for ending, kind in [(4, 'half'), (8, cadence)]:
            bars = [list(p.measure(ending).recurse().notes) for p in parsed.parts]
            assert len(bars) == 4 and all(len(v) == n for v in bars)
            assert all(note.lyric == 'laus' for note in bars[0])
            assert all(p.measure(ending).quarterLength == 4 for p in parsed.parts)
            pair = []
            for i in (-2, -1):
                midi = [v[i].pitch.midi for v in bars]
                assert all(a > b for a, b in zip(midi, midi[1:]))
                rn = roman.romanNumeralFromChord(chord.Chord([v[i].pitch for v in bars]), tonality)
                pair.append((rn.scaleDegree, rn.inversion(), rn.quality))
            assert pair[-1][1] == 0
            expected = {'perfect': [(5, 0), (1, 0)], 'plagal': [(4, 0), (1, 0)],
                        'deceptive': [(5, 0), (6, 0)], 'half': [(2, 1), (5, 0)]}
            assert [(d, inv) for d, inv, _ in pair] == expected[kind]
            if kind in ('perfect', 'deceptive'):
                assert pair[0][-1] == 'major'
                leading = (tonality.tonic.pitchClass - 1) % 12
                assert any(v[-2].pitch.pitchClass == leading and v[-1].pitch.midi == v[-2].pitch.midi + 1 for v in bars)
            if kind == 'perfect':
                assert bars[0][-1].pitch.name == tonic
        all_pitches = list(parsed.parts[0].pitches)
        assert result['cadence'] == cadence and result['openingCadence'] == 'half'
        assert result['peakBars'] == sorted({m.number for m in parsed.parts[0].getElementsByClass(stream.Measure)
                                            if max(p.midi for p in m.pitches) == max(p.midi for p in all_pitches)})
        pitches.append([p.midi for p in parsed.pitches])
    assert pitches[1] == [m + 2 for m in pitches[0]]
