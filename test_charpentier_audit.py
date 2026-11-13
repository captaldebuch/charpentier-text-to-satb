from pathlib import Path
from music21 import converter, instrument, note, stream
from charpentier_audit import audit


def test_reconstructed_example_and_correction():
    directory = Path(__file__).parent / 'examples/contrepoint'
    original = converter.parse(directory / 'releve.musicxml')
    fixed = converter.parse(directory / 'corrige.musicxml')
    counts, findings = audit(original)
    assert counts == dict(parallelFifths=0, parallelOctaves=0, directOuter=0, largeLeaps=1,
                          crossings=0, unisons=4, wideUpper=1, incompleteTriads=1)
    assert not any(audit(fixed)[0].values())
    def soprano(s):
        return [(n.pitch.nameWithOctave, n.offset, n.quarterLength, n.lyric) for n in s.parts[0].flatten().notes]
    old,new = soprano(original),soprano(fixed)
    assert [(i,x[0],y[0]) for i,(x,y) in enumerate(zip(old,new,strict=True)) if x != y] == [(8,'F#4','A4')]
    assert all(x[1:]==y[1:] for x,y in zip(old,new))


def test_perfects_and_oblique_motion():
    s = stream.Score()
    # Outer voices C5/F3 then D5/G3: consecutive compound perfect fifths.
    # Alto and tenor move C4/C3 to D4/D3 in octaves, then stand still.
    for line in ('C5 D5 E5', 'C4 D4 D4', 'C3 D3 D3', 'F2 G2 G2'):
        p=stream.Part(); m=stream.Measure(number=1)
        for token in line.split(): m.append(note.Note(token))
        p.append(m);s.append(p)
    counts, rows=audit(s)
    assert any(r['kind']=='parallelFifths' and r['voices']==['Dessus','Basse'] for r in rows)
    assert any(r['kind']=='parallelOctaves' and r['voices']==['Haute-contre','Taille'] for r in rows)
    assert not any(r['kind'].startswith('parallel') and r['attack']==3 for r in rows)
