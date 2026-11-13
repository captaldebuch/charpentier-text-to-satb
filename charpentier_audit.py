"""Audit the synchronous, four-part, note-against-note texture of this demo."""
from itertools import combinations
from music21 import stream

VOICES = ('Dessus', 'Haute-contre', 'Taille', 'Basse')
CHECKS = ('parallelFifths', 'parallelOctaves', 'directOuter', 'largeLeaps',
          'crossings', 'unisons', 'wideUpper', 'incompleteTriads')


def audit(score):
    counts = dict.fromkeys(CHECKS, 0)
    findings = []
    def report(kind, voices, notes):
        counts[kind] += 1
        findings.append(dict(kind=kind, bar=bar, attack=attack,
                             voices=[VOICES[i] for i in voices], notes=notes))

    def perfect(hi, lo):
        quality = ((hi.diatonicNoteNum-lo.diatonicNoteNum) % 7, (hi.midi-lo.midi) % 12)
        return {(0, 0): 'parallelOctaves', (4, 7): 'parallelFifths'}.get(quality)

    previous = None
    for measure in score.parts[0].getElementsByClass(stream.Measure):
        bar = measure.number
        groups = [list(p.measure(bar).flatten().notes) for p in score.parts]
        if len(groups) != 4 or any([(n.offset, n.quarterLength) for n in g] !=
                                    [(n.offset, n.quarterLength) for n in groups[0]] for g in groups[1:]):
            raise ValueError('Expected four synchronized monophonic parts.')
        for attack, notes in enumerate(zip(*groups, strict=True), 1):
            now = [n.pitch for n in notes]
            for i in range(3):
                gap = now[i].midi-now[i+1].midi
                if gap <= 0:
                    report('unisons' if gap == 0 else 'crossings', (i,i+1), [p.nameWithOctave for p in now[i:i+2]])
                if i < 2 and gap > 12:
                    report('wideUpper', (i,i+1), [p.nameWithOctave for p in now[i:i+2]])
            pcs = {p.pitchClass for p in now}
            if not any({(pc-root)%12 for pc in pcs} in ({0,3,7},{0,4,7},{0,3,6},{0,4,8}) for root in pcs):
                report('incompleteTriads', range(4), [p.nameWithOctave for p in now])
            if previous is not None:
                motion = [p.midi-q.midi for p,q in zip(now,previous)]
                for i in range(4):
                    if abs(now[i].diatonicNoteNum-previous[i].diatonicNoteNum) >= 6:
                        report('largeLeaps', (i,), [previous[i].nameWithOctave,now[i].nameWithOctave])
                for i,j in combinations(range(4),2):
                    if motion[i]*motion[j] <= 0:
                        continue
                    end = perfect(now[i],now[j])
                    if not end:
                        continue
                    last = perfect(previous[i],previous[j])
                    pitches = [p.nameWithOctave for p in (previous[i],previous[j],now[i],now[j])]
                    if last == end:
                        report(end, (i,j), pitches)
                    elif (i,j) == (0,3) and abs(now[i].diatonicNoteNum-previous[i].diatonicNoteNum)>1:
                        report('directOuter', (i,j), pitches)
            previous = now
    return counts, findings
