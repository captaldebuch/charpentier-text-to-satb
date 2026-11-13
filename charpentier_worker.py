"""Generate one eight-bar study using the Text to Charpentier rule engine."""
import argparse
import base64
import json
import re
import random
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
engine = ROOT / 'charpentier-engine'
if not engine.is_dir():
    engine = ROOT.parents[1] / 'MODELS/CHARPENTIER/charpentier-notagen/backend/src'
sys.path[:0] = [str(engine), str(ROOT / 'charpentier-runtime')]

import verovio
from music21 import key, tempo
from melody import build_soprano_part
from harmonize import harmonize_soprano
from charpentier_example import render_audio
from charpentier_cadences import finalize
from charpentier_audit import audit
from charpentier_settings import INTERVALS, MINOR_INTERVALS, METERS, meter_family


LIBRARY = json.loads((ROOT / 'charpentier-library.json').read_text())
SOURCES = {s['id']: s for s in LIBRARY['sources']}


def compose_line(lyrics, emphasis, rng, pool, meter='4/4', mode='major'):
    scale = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5', 'D5', 'E5']
    if mode == 'minor':
        scale = ['C4', 'D4', 'E-4', 'F4', 'G4', 'A-4', 'B-4', 'C5', 'D5', 'E-5']
    pitches, durations = [], []
    trace = []
    previous = None
    # Canonical shapes get one vote, however many sources attest them.
    shapes = {}
    for record in LIBRARY['patterns']:
        if meter_family(record.get('family', record['meter'])) != meter_family(meter):
            continue
        source = SOURCES[record['source']]
        if pool == 'core' and source['composer'] != 'Marc-Antoine Charpentier':
            continue
        shape = tuple(record['rhythm']), tuple(record['contour'])
        shapes.setdefault(shape, []).append(record)
    for bar in range(8):
        start, stop = bar * len(lyrics) // 8, (bar + 1) * len(lyrics) // 8
        if bar in (3, 7):
            # Two harmonic arrivals. Keep every word attack and make the last
            # note at least as long as the preceding ones where possible.
            units = {'2/4':4, '3/4':6, '6/8':6, '4/4':8, '2/2':8}[meter]
            n = stop - start
            # In compound duple the second chord begins on the second dotted beat
            # for two attacks; shorter declamations subdivide the preceding beat.
            split = units // 2
            first_units = [split // (n-1) + (i < split % (n-1)) for i in range(n-1)]
            if min(first_units) == 0:
                first_units = [1] * (n-1)
            rhythm = [v / 2 for v in first_units + [units-sum(first_units)]]
            pitches.extend(['C5'] * n)
            durations.extend(rhythm)
            trace.append(dict(source=None, rhythm=rhythm))
            previous = None
            continue
        choices, weights = [], []
        for (rhythm, contour), witnesses in shapes.items():
            if len(rhythm) != stop - start:
                continue
            for anchor in range(len(scale)):
                line = [anchor + step for step in contour]
                if min(line) < 0 or max(line) >= len(scale):
                    continue
                # Retain an attested contour, but exclude written sevenths or
                # larger leaps within it and at joins between retrieved bars.
                if any(abs(a-b) >= 6 for a,b in zip(line,line[1:])) or (previous is not None and abs(previous-anchor) >= 6):
                    continue
                if previous is None and anchor not in (0, 2, 4, 7):
                    continue
                join = abs(previous - anchor) if previous is not None else 0
                stress = sum(duration * accent for duration, accent in zip(rhythm, emphasis[start:stop]))
                weight = (1 + stress) ** 2 / (1 + join ** 2)
                choices.append((line, rhythm, witnesses))
                weights.append(weight)
        line, rhythm, witnesses = rng.choices(choices, weights=weights)[0]
        witness = rng.choice(witnesses)
        source = SOURCES[witness['source']]
        trace.append(dict(source=source, measure=witness['measure'], sourceMeter=witness['meter'], startQuarter=witness.get('startQuarter'), contour=[n-line[0] for n in line], rhythm=rhythm))
        pitches.extend(scale[degree] for degree in line)
        durations.extend(rhythm)
        previous = line[-1]
    return trace, {'syllables': lyrics, 'pitches': pitches, 'durations': durations,
            'phrase_ends': [len(lyrics) - 1]}


def compose(phrase, pool='core', seed=1, shift=0, meter='4/4', mode='major', cadence='perfect'):
    if pool == 'core' and meter == '6/8':
        raise ValueError('Le 6/8 nécessite le répertoire élargi.')
    # Keep Arabic vowel and recitation marks attached to their letters.
    letter = r"[^\W\d_][\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]*"
    word = rf"(?:{letter})+(?:[’'-](?:{letter})+)*"
    words = re.findall(word, unicodedata.normalize('NFC', phrase))
    if not 1 <= len(words) <= 32:
        raise ValueError('Entrez une phrase de 1 à 32 mots.')
    # Give longer words room to sing. Each word starts once; extra notes are melismas.
    weights = [max(1, len(re.findall(r'[aeiouyàâäéèêëîïôöùûüœæاويىَُِ]+', word.lower()))) for word in words]
    counts = [1] * len(words)
    for _ in range(min(32, max(16, sum(weights))) - len(words)):
        i = max(range(len(words)), key=lambda j: weights[j] / counts[j])
        counts[i] += 1
    lyrics = [token for word, n in zip(words, counts) for token in [word] + [''] * (n - 1)]
    rng = random.Random(seed)
    emphasis = [accent for weight, n in zip(weights, counts)
                for accent in [0] * (n - 1) + [weight]]
    tonality = key.Key('C', mode)
    trace, data = compose_line(lyrics, emphasis, rng, pool, meter, mode)
    soprano = build_soprano_part(data, tonality, time_sig=meter)
    for event, lyric in zip(soprano.recurse().notes, lyrics, strict=True):
        if not lyric:
            event.lyrics = []
    score = harmonize_soprano(soprano, tonality, time_sig=meter, title=phrase, composer='MELODY · étude expérimentale', tempo_bpm=rng.choice([66, 72, 80, 88, 96]))

    interval = (MINOR_INTERVALS if mode == 'minor' else INTERVALS)[shift]
    if interval != 'P1':
        score.transpose(interval, inPlace=True)
    tonic = tonality.tonic.transpose(interval).name
    analysis = finalize(score, mode, meter, cadence, shift, tonic)
    analysis['counterpoint'] = audit(score)[0]
    analysis['sources'] = len({row['source']['id'] for row in trace if row['source']})
    for index, name in ((3, 'half'), (7, cadence)):
        notes = list(score.parts[0].measure(index+1).recurse().notes)
        trace[index].update(cadence=name, contour=[n.pitch.diatonicNoteNum-notes[0].pitch.diatonicNoteNum for n in notes])
    return score, trace, analysis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pool', choices=['core','expanded'], default='core')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--shift', type=int, choices=INTERVALS, default=0)
    parser.add_argument('--mode', choices=['major','minor'], default='major')
    parser.add_argument('--meter', choices=METERS, default='4/4')
    parser.add_argument('--cadence', choices=['perfect','half','plagal','deceptive'], default='perfect')
    args = parser.parse_args()
    if args.mode == 'minor' and args.shift not in MINOR_INTERVALS:
        parser.error('Unsupported minor key')
    try:
        score, trace, analysis = compose(sys.stdin.read(), **vars(args))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / 'etude.musicxml'
        wav = Path(tmp) / 'etude.wav'
        score.write('musicxml', fp=xml)
        bpm = score.recurse().getElementsByClass(tempo.MetronomeMark).first().number
        render_audio(score, wav, 60 / bpm, measures=8)
        tk = verovio.toolkit()
        tk.setOptions({'pageWidth': 3100, 'adjustPageHeight': True, 'footer': 'none', 'header': 'none', 'breaks': 'auto', 'pageHeight': 6500, 'scale': 40})
        if not tk.loadFile(str(xml)) or tk.getPageCount() != 1:
            raise RuntimeError('Gravure indisponible')
        print(json.dumps({'trace': trace, 'analysis': analysis, 'seed': args.seed, 'xml': xml.read_text(), 'svg': tk.renderToSVG(1),
                          'audio': base64.b64encode(wav.read_bytes()).decode()}))
