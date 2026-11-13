"""Check the musical invariants through MusicXML export and reimport."""
from pathlib import Path

import pytest
from music21 import converter, meter, stream, tempo

from charpentier_variants import apply_variant


# Optional integration fixture from the separately distributed CSMD dataset.
import os
SOURCE = Path(os.environ.get("CSMD_STABAT", "Charp-Stabat.mxl"))
pytestmark = pytest.mark.skipif(not SOURCE.is_file(), reason="Set CSMD_STABAT to the original Stabat MXL")


def timeline(part):
    return [(event.offset, event.quarterLength, event.isRest,
             tuple((pitch.ps, pitch.diatonicNoteNum) for pitch in event.pitches),
             tuple(lyric.text for lyric in event.lyrics))
            for event in part.flatten().notesAndRests]


@pytest.mark.parametrize(('shift', 'target_meter'), [(2, '4/4'), (-2, '2/2'), (0, '4/4')])
def test_score_export_preserves_music(tmp_path, shift, target_meter):
    canonical = converter.parse(SOURCE)
    # Give this unmarked source an explicit half-note tempo to exercise cut time.
    canonical.parts[0].measure(1).insert(0, tempo.MetronomeMark(number=42, referent=2))
    variant = apply_variant(canonical, shift, target_meter)
    restored = converter.parse(variant.write('musicxml', fp=tmp_path / 'variant.musicxml'))
    assert len(canonical.parts) == len(restored.parts) == 3
    for source, result in zip(canonical.parts, restored.parts, strict=True):
        assert source.measure(1).timeSignature.ratioString == '2/2'
        assert result.measure(1).timeSignature.ratioString == target_meter
        assert result.measure(1).keySignature.sharps == source.measure(1).keySignature.sharps + shift
        assert [(m.number, m.offset, m.quarterLength) for m in result.getElementsByClass(stream.Measure)] == [
            (m.number, m.offset, m.quarterLength) for m in source.getElementsByClass(stream.Measure)]
        for left, right in zip(timeline(source), timeline(result), strict=True):
            assert left[:3] == right[:3]
            assert left[4] == right[4]
            for a, b in zip(left[3], right[3], strict=True):
                assert b == (a[0] + shift, a[1] + shift // 2)
    assert restored.recurse().getElementsByClass(tempo.MetronomeMark).first().getQuarterBPM() == 84


def test_rejects_changed_groupings_and_unbounded_shifts():
    source = converter.parse(SOURCE)
    for shift, target in ((7, '4/4'), (0, '6/8')):
        with pytest.raises(ValueError):
            apply_variant(source, shift, target)
    source.parts[0].measure(2).timeSignature = meter.TimeSignature('3/4')
    variant = apply_variant(source, -2)
    assert variant.parts[0].measure(1).timeSignature.ratioString == '2/2'
    assert variant.parts[0].measure(2).timeSignature.ratioString == '3/4'
    with pytest.raises(ValueError, match='uniform'):
        apply_variant(source, 0, '4/4')
