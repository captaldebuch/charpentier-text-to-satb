"""Build the demo's attributed metrical patterns from CSMD and HARMONIA.

Run with --pdmx /path/to/PDMX.zip (the distribution containing PDMX/PDMX.csv).
Source notation is read locally; the public artifact contains only features.
"""
import argparse
import csv
import hashlib
import io
import json
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, is_zipfile

HERE = Path(__file__).resolve().parent
LAB = HERE
CHAR = 'Marc-Antoine Charpentier'
LULLY = 'Jean-Baptiste Lully'
PURCELL = 'Henry Purcell'
BAR_LENGTH = {('2', '2'): 4, ('4', '4'): 4, ('2', '4'): 2, ('3', '4'): 3, ('6', '8'): 3}
CSMD = {
    'Salve_puerule': ('Salve puerule, H.414', CHAR),
    'Kyrie_minuit_Charpentier': ('Messe de minuit · Kyrie', CHAR),
    'Gloria_minuit_Charpentier': ('Messe de minuit · Gloria', CHAR),
    'Laudate_Dominum_Charpentier': ('Laudate Dominum', CHAR),
    'Char-osac': ('O sacrum convivium, H.235', CHAR),
    'H_189_De_profundis': ('De profundis, H.189', CHAR),
    'Char-suflu': ('Super flumina Babylonis', CHAR),
    'Char-h196': ('Usquequo Domine, H.196', CHAR),
    'Magnificat_H79_Charpentier_CONDUCTOR': ('Magnificat, H.79', CHAR),
    'Charpentier-Veni_creator_Spiritus_H.54-partitura': ('Veni creator Spiritus, H.54', CHAR),
    'Ave_coeli_munus_supernum': ('Ave coeli munus supernum', LULLY),
    'Flores-apparuerunt': ('Flores apparuerunt', 'Étienne Moulinié'),
}

# Exact HARMONIA record IDs plus the part index (zero-based in encoded order).
# Purcell's two versions of In these delightful pleasant groves are represented
# only by the version explicitly scored for voices. Lully's dance is marked
# instrumental. The source's composer attribution is retained for each title.
HARMONIA = {
    'QmSS111LdorcmvMzubyJ9BKQBjaXHxPXJwYvwqCt3UiVEm': ('Stingo · The English Dancing Master', 'Anonymous (Playford collection)', 0, 'instrumental'),
    'QmQM4FucfGBzPfHLL2wkL6nqdPGw41Pc5mMFmVXUSayhgJ': ('Venez approchons nous', 'Dumont (source attribution)', 0, 'vocal'),
    'QmNYfgJCc27WHMYJY172uZHPenciEAZo9XqXJgQvRZ5iaW': ('Le Bourgeois gentilhomme · Premier intermède', LULLY, 0, 'instrumental'),
    'QmVnTHqUkS9D48s4yMAiJVtRTQc39ogVeeGz5X9zsSvkKK': ('Le Triomphe de l’amour', LULLY, 0, 'instrumental'),
    'QmWTwrnzGtvGsXGhE3WYq7NukL5zdfosCSEiPW4RUbvSQL': ('Qui veut chasser une migraine', 'Gabriel Bataille', 1, 'vocal'),
    'QmQuCga23qcJc4MAScu4GyNVdFkvEGjzzVTqmDoFcQNMgh': ('Close thine eyes', PURCELL, 0, 'vocal'),
    'QmSAWwnm2mkdgrnNtrKFRXU5k2qy1zEjuzoJuVwQeo9cHY': ('In these delightful pleasant groves', PURCELL, 0, 'vocal'),
    'QmTx8hbr3PHoFpQvneeQw99DhDH17yF8y7ED9JdVY5BEU8': ('The Fairy Queen · Hail! Hail! Great Parent', PURCELL, 0, 'vocal'),
    'QmTDdDbGrqoueNksFJ6j6dd8RuwtwoT6fZmqMBysSp1qHy': ('Gaudia Virginis Mariae, H.59', CHAR, 1, 'vocal'),
}


def read_score(path):
    if is_zipfile(path):
        with ZipFile(path) as archive:
            container = ET.fromstring(archive.read('META-INF/container.xml'))
            return ET.fromstring(archive.read(container.find('.//{*}rootfile').get('full-path')))
    return ET.parse(path).getroot()


def patterns_for(part, source):
    seen = set()
    divisions = None
    meter = None
    for measure in part.findall('measure'):
        divisions = int(measure.findtext('attributes/divisions', divisions or 1))
        time = measure.find('attributes/time')
        if time is not None:
            meter = (time.findtext('beats'), time.findtext('beat-type'))
        if meter not in BAR_LENGTH or any(measure.find(x) is not None for x in ('backup', 'forward')):
            continue
        notes = measure.findall('note')
        if not notes or any(n.find('duration') is None or n.find('chord') is not None for n in notes):
            continue
        if len({(n.findtext('voice'), n.findtext('staff')) for n in notes}) != 1:
            continue
        lengths = [Fraction(int(n.findtext('duration')), divisions) for n in notes]
        if min(lengths) <= 0 or sum(lengths) != BAR_LENGTH[meter]:
            continue
        windows = [(0, len(notes), '/'.join(meter), 0)]
        if meter in {('2', '2'), ('4', '4')}:
            elapsed = 0
            for index, duration in enumerate(lengths, 1):
                elapsed += duration
                if elapsed == 2:
                    windows.extend([(0, index, '2/4', 0), (index, len(notes), '2/4', 2)])
                    break
        for start, end, family, offset in windows:
            events = notes[start:end]
            rhythm = tuple(lengths[start:end])
            if not 2 <= len(events) <= 4 or any(d.denominator not in (1, 2, 4) for d in rhythm):
                continue
            if any(n.find('pitch') is None or any(n.find(tag) is not None for tag in ('tie', 'grace', 'chord', 'cue')) for n in events):
                continue
            pitches = [int(n.findtext('pitch/octave')) * 7 + 'CDEFGAB'.index(n.findtext('pitch/step')) for n in events]
            contour = tuple(p - pitches[0] for p in pitches)
            signature = meter, family, rhythm, contour
            if signature in seen:
                continue
            seen.add(signature)
            yield dict(source=source, measure=measure.get('number'), meter='/'.join(meter),
                       family=family, startQuarter=offset, rhythm=list(map(float, rhythm)), contour=list(contour))


def add_source(library, path, part_index, **details):
    score = read_score(path)
    if details['collection'] == 'CSMD' and score.findtext('identification/rights'):
        raise ValueError(f'Check edition-specific rights before adding {path.name}')
    parts = score.findall('part')
    if part_index is None:
        part_index = next(i for i, part in enumerate(parts) if part.find('.//lyric') is not None)
    part = parts[part_index]
    patterns = list(patterns_for(part, details['id']))
    if not patterns:
        raise ValueError(f'No usable measures in {path.name}, part {part_index + 1}')
    label = score.findtext(f"part-list/score-part[@id='{part.get('id')}']/part-name")
    library['sources'].append(dict(**details, part=label or f'Part {part_index + 1}',
                                   partNumber=part_index + 1, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    library['patterns'].extend(patterns)


def build(pdmx):
    library = {'sources': [], 'patterns': []}
    for stem, (title, composer) in CSMD.items():
        path = LAB / 'MODELS/Charpentier_Dataset' / (stem + '.mxl')
        add_source(library, path, 5 if stem == 'H_189_De_profundis' else None, id='csmd:'+stem, title=title, composer=composer, collection='CSMD',
                   kind='vocal', license='CC BY 4.0 (dataset)', url='https://doi.org/10.5281/zenodo.20450425',
                   attribution='Xavier Fresquet, Charpentier Sacred Music Dataset v1.0. Relative contours and durations extracted from the cited score.')
    records = LAB / 'DATA/HARMONIA/records'
    with ZipFile(pdmx) as archive:
        rows = csv.DictReader(io.TextIOWrapper(archive.open('PDMX/PDMX.csv'), encoding='utf-8'))
        selected = {Path(r['path']).stem: r for r in rows if Path(r['path']).stem in HARMONIA}
        # This macOS repack of PDMX uses inconsistent directory capitalization.
        archived = {name.rsplit('/', 1)[-1]: name for name in archive.namelist()
                    if name.startswith('PDMX/data/') and name.rsplit('/', 1)[-1][:-5] in HARMONIA}
        for identifier, (title, composer, part, kind) in HARMONIA.items():
            row = selected[identifier]
            score_dir, = records.glob('*/*/' + identifier)
            original = json.loads(archive.read(archived[identifier + '.json']))
            if original != json.loads((score_dir / 'score.json').read_bytes()):
                raise ValueError('HARMONIA record differs from upstream PDMX payload: ' + identifier)
            license_name = {'cc-zero': 'CC0 1.0', 'publicdomain': 'Public Domain Mark 1.0'}[row['license']]
            meta = json.loads(archive.read('PDMX/' + row['metadata'].removeprefix('./')))['data']['score']
            add_source(library, score_dir / 'score.musicxml', part, id=identifier, title=title,
                       composer=composer, collection='HARMONIA', kind=kind, license=license_name, licenseUrl=row['license_url'],
                       url=meta['share']['publicUrl'], attribution='HARMONIA / PDMX (Long et al.); MuseScore contributor: '+meta['user']['name'])
    return library


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdmx', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=HERE / 'charpentier-library.json')
    parser.add_argument('--lab-root', required=True, type=Path, help='Path to the 1-MELODY-LAB sources')
    args = parser.parse_args()
    LAB = args.lab_root
    result = build(args.pdmx)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(len(result['sources']), 'scores;', len(result['patterns']), 'source-specific patterns')
