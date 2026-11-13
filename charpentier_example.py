"""Prepare the portal's listening excerpt from the research prototype's own export."""
from pathlib import Path
import wave
from xml.etree import ElementTree as ET

import numpy as np
from music21 import converter, stream


def prepare_example(source: Path, destination: Path):
    destination.mkdir(exist_ok=True)
    tree = ET.parse(source)
    tree.find('./identification/creator').text = 'MELODY · réalisation expérimentale'
    for part, name in zip(tree.findall('./part-list/score-part'), ('Soprano', 'Alto', 'Ténor', 'Basse'), strict=True):
        part.find('part-name').text = name
    score_path = destination / 'gloria.musicxml'
    tree.write(score_path, encoding='utf-8', xml_declaration=True)
    score = converter.parse(score_path)
    render_audio(score, destination / 'gloria.wav', 0.56)


def render_audio(score, path, seconds_per_quarter, measures=4):
    rate = 22050
    lines = [list(part.getElementsByClass(stream.Measure))[:measures] for part in score.parts]
    end = max(float(m.offset + m.duration.quarterLength) for measures in lines for m in measures)
    samples = np.zeros(int(end * seconds_per_quarter * rate) + 1)
    for measures in lines:
        for measure in measures:
            for note in measure.flatten().notes:
                start = int(float(measure.offset + note.offset) * seconds_per_quarter * rate)
                length = int(float(note.quarterLength) * seconds_per_quarter * rate)
                t = np.arange(length) / rate
                envelope = np.clip(np.minimum(t, t[::-1]) / 0.02, 0, 1)
                for pitch in note.pitches:
                    samples[start:start + length] += np.sin(2 * np.pi * pitch.frequency * t) * envelope
    with wave.open(str(path), 'wb') as audio:
        audio.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        audio.writeframes((samples * (28000 / max(abs(samples)))).astype('<i2').tobytes())
