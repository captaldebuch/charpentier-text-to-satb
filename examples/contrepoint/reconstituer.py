"""Rebuild the two editions from the screenshot (scientific pitch notation)."""
import sys
from pathlib import Path
from music21 import stream, note, key, meter, tempo, metadata, clef
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
from charpentier_audit import audit

LINES = (
    'A4 E5 A4 C#5 C#5 E5 E5 E5 F#4 C#5 F#4 C#5 B4 F#5 E5 E5',
    'E4 E4 E4 E4 E4 E4 E4 E4 D4 E4 D4 E4 D4 D4 E4 E4',
    'C#4 C#4 C#4 C#4 C#4 C#4 B3 C#4 D4 C#4 D4 C#4 D4 D4 B3 C#4',
    'A2 A2 A2 A2 A2 A2 G2 A2 A2 A2 A2 A2 B2 A2 G2 A2'
)
def reconstruct():
    s = stream.Score()
    s.metadata = metadata.Metadata(title='Le chien saute dans le lac · relevé de la capture')
    for i,(name,line,sign) in enumerate(zip(('Dessus','Haute-contre','Taille','Basse'),LINES,
                                            (clef.TrebleClef,clef.TrebleClef,clef.AltoClef,clef.BassClef))):
        p = stream.Part(); p.partName = name
        for j,token in enumerate(line.split()):
            if j%2==0:
                m = stream.Measure(number=j//2+1)
                if j==0:
                    m.insert(0,meter.TimeSignature('6/8')); m.insert(0,key.Key('D')); m.insert(0,sign())
                    if i==0: m.insert(0,tempo.MetronomeMark(number=88))
            n=note.Note(token,quarterLength=1.5)
            if i==0 and j in (0,3,6,10,12,14): n.lyric = {0:'le',3:'chien',6:'saute',10:'dans',12:'le',14:'lac'}[j]
            m.append(n)
            if j%2: p.append(m)
        s.append(p)
    return s

if __name__=='__main__':
    from charpentier_cadences import finalize
    from charpentier_example import render_audio
    import json
    s=reconstruct()
    before=audit(s)
    s.write('musicxml',fp=HERE/'releve.musicxml')
    import copy
    unchanged = copy.deepcopy(s)
    unchanged.metadata.title='Le chien saute dans le lac · réharmonisation à dessus inchangé'
    finalize(unchanged, 'major', '6/8', 'half', 2, 'D', preserve_soprano=True)
    unchanged.write('musicxml',fp=HERE/'dessus-identique.musicxml')
    s.parts[0].measure(5).notes[0].pitch.nameWithOctave='A4'
    s.metadata.title='Le chien saute dans le lac · proposition de correction'
    finalize(s, 'major', '6/8', 'half', 2, 'D', preserve_soprano=True)
    after=audit(s)
    s.write('musicxml',fp=HERE/'corrige.musicxml')
    render_audio(s,HERE/'corrige.wav',60/88, measures=8)
    (HERE/'audit.json').write_text(json.dumps(dict(avant=before,apres=after),indent=2,ensure_ascii=False))
