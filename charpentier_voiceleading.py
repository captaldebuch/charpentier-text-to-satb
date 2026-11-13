"""Whole-study SATB voicing by shortest path across successive note attacks.

Each state is a complete triad voiced for four distinct registers. A transition
considers simultaneous motion in every pair of parts, including between bars.
The soprano is fixed except where a new cadence melody has been requested.
"""
from functools import lru_cache
from itertools import combinations, product

import numpy as np
from music21 import key, pitch, roman


def progressions(mode):
    tonic, predominant, subdominant, submediant = (
        ('i', 'iio6', 'iv', 'VI') if mode == 'minor' else ('I', 'ii6', 'IV', 'vi'))
    return {'perfect': ('V', tonic), 'half': (predominant, 'V'),
            'plagal': (subdominant, tonic), 'deceptive': ('V', submediant)}


def events(score, bar):
    voices = [list(part.measure(bar).flatten().notes) for part in score.parts]
    if len(voices) != 4:
        raise ValueError('SATB writing needs four parts.')
    grid = [(event.offset, event.quarterLength) for event in voices[0]]
    if not 2 <= len(grid) <= 4 or any(
        [(event.offset, event.quarterLength) for event in voice] != grid for voice in voices[1:]
    ):
        raise ValueError('Each measure needs 2–4 synchronized attacks per part.')
    return voices


@lru_cache(maxsize=1024)
def _triad(tonic, mode, figure, shift):
    tonality = key.Key(tonic, mode)
    chord = roman.RomanNumeral(figure, tonality)
    names = {p.pitchClass: p.name for p in chord.pitches}
    leading = (tonality.tonic.pitchClass - 1) % 12
    ranges = ((58, 81), (53, 75), (46, 68), (38, 62))
    pitches = [[n for n in range(lo + shift, hi + shift + 1) if n % 12 in names]
               for lo, hi in ranges]
    choices = []
    for line in product(*pitches):
        s, a, t, b = line
        if not (0 < s-a <= 12 and 0 < a-t <= 12 and 0 < t-b <= 19):
            continue
        if b % 12 != chord.bass().pitchClass:
            continue
        classes = [n % 12 for n in line]
        if set(classes) != names.keys() or classes.count(leading) > 1:
            continue
        choices.append(line)
    return tuple(choices), names, chord.root().pitchClass


def _figures(mode):
    return (('I', 'I6', 'ii', 'ii6', 'iii', 'IV', 'IV6', 'V', 'V6', 'vi', 'vi6')
            if mode == 'major' else
            ('i', 'i6', 'iio6', 'III', 'III6', 'iv', 'iv6', 'V', 'V6', 'VI', 'VI6', 'VII', 'v'))


def _candidates(tonality, shift, figures, soprano, anchor):
    def collect(allowed):
        rows = []
        for figure in allowed:
            lines, names, root = _triad(tonality.tonic.name, tonality.mode, figure, shift)
            for line in lines:
                if soprano is not None and line[0] != soprano:
                    continue
                if anchor and line[0] % 12 != tonality.tonic.pitchClass:
                    continue
                rows.append((line, figure, names, root))
        return rows

    rows = collect(figures or _figures(tonality.mode))
    if not rows and not figures:
        # Also permit a chromatic fixed melody in an imported study. Secondary
        # dominants and the Neapolitan sixth accommodate such inflections.
        rows = collect(('bII6', 'V/ii', 'V/iii', 'V/IV', 'V/V', 'V/vi', 'V/VI'))
    if not rows:
        raise ValueError('The fixed soprano is incompatible with the cadence or SATB ranges.')
    return rows


def _transition(previous, current, prior_roots, roots, tonic_class):
    before, after = previous[:, None, :], current[None, :, :]
    motion = after - before
    size = np.abs(motion)
    cost = (size + 2 * np.maximum(0, size - [4, 4, 4, 7]) ** 2).sum(axis=2)
    # An immutable source melody can force a large soprano leap. Keep the other
    # lines singable and avoid creating additional large leaps at cadence bars.
    cost += 900 * (size >= 10).sum(axis=2)
    for i, j in combinations(range(4), 2):
        similar = motion[:, :, i] * motion[:, :, j] > 0
        old = (before[:, :, i] - before[:, :, j]) % 12
        new = (after[:, :, i] - after[:, :, j]) % 12
        perfect = (new == 7) | (new == 0)
        cost += 4000 * (similar & perfect & (old == new))
        if (i, j) == (0, 3):
            cost += 4000 * (similar & perfect & (size[:, :, 0] > 2))
    for i in range(3):
        cost += 22 * ((after[:, :, i] < before[:, :, i+1]) |
                      (after[:, :, i+1] > before[:, :, i]))
    # Prefer a harmonic change on successive attacks. Common-tone continuations
    # are still available when the fixed melody or cadence makes them preferable.
    distance = (roots[None, :] - prior_roots[:, None]) % 12
    cost += 15 * (distance == 0) - 5 * (distance == 5) - 2 * (distance == 2)
    resolution = ((prior_roots[:, None] - tonic_class) % 12 == 7) & np.isin(
        (roots[None, :] - tonic_class) % 12, (0, 8, 9))
    cost += 150 * (resolution * (((before % 12 == (tonic_class - 1) % 12)
                                 & (motion != 1)).sum(axis=2)))
    return cost


def harmonize_study(score, tonality, shift, cadence, *, preserve_soprano=False):
    """Revoice the whole score in place. shift is the actual displacement from C."""
    attacks = []
    endings = progressions(tonality.mode)
    for bar in range(1, 9):
        columns = list(zip(*events(score, bar)))
        kind = 'half' if bar == 4 else cadence if bar == 8 else None
        for i, column in enumerate(columns):
            prescribed = kind is not None and i >= len(columns) - 2
            figures = (endings[kind][i-len(columns)],) if prescribed else None
            # Hold the observed melody on every attack outside the two written
            # cadence measures and, for revoicing, also inside those measures.
            soprano = column[0].pitch.midi if preserve_soprano or not kind else None
            anchor = kind == 'perfect' and i == len(columns)-1
            rows = _candidates(tonality, shift, figures, soprano, anchor)
            attacks.append((column, rows, i == 0, soprano is not None))
    predecessors = []
    for idx, (_, rows, downbeat, _) in enumerate(attacks):
        pitches = np.array([r[0] for r in rows])
        roots = np.array([r[3] for r in rows])
        local = np.array([(3 if r[1].endswith('6') and downbeat else 0)
                          + (2 if r[1] in ('iii', 'v', 'VII') else 0)
                          + (2 if r[0][0] - r[0][1] > 9 else 0) for r in rows])
        if idx == 0:
            centers = np.array([69, 63, 55, 48]) + shift
            accumulated = np.abs(pitches - centers).sum(axis=1) + local + 9 * (roots != tonality.tonic.pitchClass)
        else:
            costs = _transition(last_pitches, pitches, last_roots, roots, tonality.tonic.pitchClass)
            costs += accumulated[:, None]
            best = costs.argmin(axis=0)
            predecessors.append(best)
            accumulated = costs[best, np.arange(len(rows))] + local
        last_pitches, last_roots = pitches, roots
    path = [int(accumulated.argmin())]
    for prior in reversed(predecessors):
        path.append(int(prior[path[-1]]))
    for (column, rows, _, fixed), idx in zip(attacks, reversed(path)):
        line, _, names, _ = rows[idx]
        for voice, (event, midi) in enumerate(zip(column, line)):
            if voice == 0 and fixed:
                continue
            written = pitch.Pitch(names[midi % 12])
            written.octave = 4
            written.octave += (midi - written.midi) // 12
            event.pitch = written
