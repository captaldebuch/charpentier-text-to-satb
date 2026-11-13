"""Exercise all voice pairs, including the two sides of each cadence boundary."""
from itertools import combinations, pairwise

from music21 import key, meter, note, stream
import pytest

from charpentier_cadences import finalize
from charpentier_worker import compose


def check_voices(score, fixed_leaps=()):
    lines = [tuple(p.midi for p in attack) for attack in zip(*(p.pitches for p in score.parts))]
    for s, a, t, b in lines:
        assert 0 < s-a <= 12 and 0 < a-t <= 12 and 0 < t-b <= 19
        assert len({n % 12 for n in (s,a,t,b)}) == 3
    for attack, (left, right) in enumerate(pairwise(lines), 1):
        motion = [b-a for a,b in zip(left,right)]
        for voice, leap in enumerate(motion):
            assert abs(leap) < 10 or (attack, voice) in fixed_leaps
        for i, j in combinations(range(4), 2):
            before, after = (left[i]-left[j]) % 12, (right[i]-right[j]) % 12
            if motion[i]*motion[j] > 0 and after in (0, 7):
                assert before != after
                if (i,j) == (0,3):
                    assert abs(motion[0]) <= 2


@pytest.mark.parametrize('fifth_opening', ['F#4', 'A4'])
def test_imported_study_revoicing(fifth_opening):
    melody = ['A4','E5','A4','C#5','C#5','E5','E5','E5',fifth_opening,'C#5','F#4','C#5','B4','F#5','E5','E5']
    score = stream.Score()
    for voice in range(4):
        part = stream.Part()
        for bar in range(8):
            measure = stream.Measure(number=bar+1)
            if not bar:
                measure.insert(0, key.Key('D'))
                measure.timeSignature = meter.TimeSignature('6/8')
            for name in melody[bar*2:bar*2+2]:
                measure.append(note.Note(name if voice == 0 else 'D4', quarterLength=1.5))
            part.append(measure)
        score.append(part)
    analysis = finalize(score, 'major', '6/8', 'half', 2, 'D', preserve_soprano=True)
    assert analysis['cadence'] == analysis['openingCadence'] == 'half'
    assert [p.nameWithOctave for p in score.parts[0].pitches] == melody
    check_voices(score, fixed_leaps={(8,0)} if fifth_opening == 'F#4' else {})


@pytest.mark.parametrize('mode,meter,cadence', [('major','4/4','perfect'), ('minor','3/4','deceptive'),
                                               ('major','2/4','plagal'), ('minor','2/2','half')])
def test_generated_study(mode, meter, cadence):
    score, _, _ = compose('La lumière se lève sur la mer.', seed=19, mode=mode, meter=meter, cadence=cadence)
    # Source contours can already contain a seventh; exclude just these fixed
    # soprano intervals from the check on newly written notes.
    bars = [m.number for m in score.parts[0].getElementsByClass(stream.Measure) for _ in m.flatten().notes]
    fixed = {(i,0) for i in range(1,len(bars)) if bars[i] not in (4,8) and bars[i-1] not in (4,8)}
    check_voices(score, fixed)
