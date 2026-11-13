"""Representation variants of a measured, pitched MusicXML score.

Transposition preserves the written meter by default. Meter substitution
requires an explicitly marked, uniform 2/2 or 4/4 across all parts.
Tempo markings retain their original beat unit, speed and offset. Unmeasured
performance conventions, facsimile layout and free-text annotations are
outside the MusicXML event model used here. A variant belongs to the same
canonical source and is never written to the motif retrieval index.
"""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from music21 import converter, meter as m21meter, note, stream


def apply_variant(score: stream.Score, shift: int, meter: str | None = None) -> stream.Score:
    """Return a copy in the target meter, shifted by a spelled major second or unison."""
    if type(shift) is not int or shift not in (-2, 0, 2) or meter not in (None, '4/4', '2/2'):
        raise ValueError('Use -2, 0 or +2 semitones and a 4/4 or 2/2 target meter.')
    if not score.parts:
        raise ValueError('Expected a score with measured parts.')

    signatures = set()
    for part in score.parts:
        first = part.getElementsByClass(stream.Measure).first()
        if first is None or (meter is not None and first.timeSignature is None):
            raise ValueError('Each part must start with an explicit time signature.')
        signatures.update(ts.ratioString for ts in part.recurse().getElementsByClass(m21meter.TimeSignature))
        if part.recurse().getElementsByClass(note.Unpitched).first() is not None:
            raise ValueError('Unpitched percussion is outside the supported repertoire.')
    if meter is not None and signatures not in ({'4/4'}, {'2/2'}):
        raise ValueError('The score must use one uniform meter, either 2/2 or 4/4.')

    variant = copy.deepcopy(score)
    if shift:
        variant.transpose({2: 'M2', -2: '-M2'}[shift], inPlace=True)
    if meter is not None and meter not in signatures:
        for signature in list(variant.recurse().getElementsByClass(m21meter.TimeSignature)):
            signature.activeSite.replace(signature, m21meter.TimeSignature(meter))
    return variant


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Canonical .musicxml, .xml or .mxl file')
    parser.add_argument('output', type=Path, help='New directory for this variant and its manifest')
    parser.add_argument('--source-id', required=True, help='Canonical corpus ID shared by all variants')
    parser.add_argument('--shift', type=int, choices=(-2, 0, 2), default=0)
    parser.add_argument('--meter', choices=('2/2', '4/4'), help='Omit to retain the original signature(s)')
    options = parser.parse_args()
    if options.source.suffix.lower() not in ('.xml', '.musicxml', '.mxl'):
        parser.error('Expected MusicXML input.')
    if options.output.exists():
        parser.error('Choose a new output directory.')
    score = converter.parse(options.source, format='musicxml')
    variant = apply_variant(score, options.shift, options.meter)
    manifest = {
        'canonical_source_id': options.source_id,
        'canonical_source_file': options.source.name,
        'canonical_source_sha256': hashlib.sha256(options.source.read_bytes()).hexdigest(),
        'source_meters': sorted({ts.ratioString for ts in score.recurse().getElementsByClass(m21meter.TimeSignature)}),
        'target_meter': options.meter or 'as-written',
        'transpose_semitones_all_parts': options.shift,
        'variant_file': 'variant.musicxml',
    }
    with tempfile.TemporaryDirectory(dir=options.output.parent) as tmp:
        stage = Path(tmp) / 'variant'
        stage.mkdir()
        variant.write('musicxml', fp=stage / manifest['variant_file'])
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
        stage.rename(options.output)


if __name__ == '__main__':
    main()
