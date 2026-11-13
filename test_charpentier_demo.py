"""Compare actual portal responses, including the score a visitor downloads."""
import base64
import io
import wave
import unittest
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient
from app import app


def voices(xml):
    root = ET.fromstring(xml)
    values = []
    for part in root.findall('part'):
        measures = part.findall('measure')
        assert len(measures) == 8
        events = []
        for measure in measures:
            total = 0
            for n in measure.findall('note'):
                p = n.find('pitch')
                semitone = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[p.findtext('step')]
                midi = 12*(1+int(p.findtext('octave'))) + semitone + int(p.findtext('alter', '0'))
                dur = int(n.findtext('duration'))
                events.append((midi, total, dur, n.findtext('lyric/text')))
                total += dur
            bar_length = 4 * int(part.findtext('.//time/beats')) / int(part.findtext('.//time/beat-type'))
            assert total == bar_length * int(part.findtext('.//divisions'))
        values.append(events)
    return root, values


class DemoTest(unittest.TestCase):
    def test_public_contract_and_invariants(self):
        with TestClient(app) as client:
            library = client.get('/api/text-to-charpentier/library').json()
            ids = {s['id'] for s in library['sources']}
            self.assertGreater(len({s['composer'] for s in library['sources']}), 1)
            def generate(shift, meter, mode='major', cadence='perfect'):
                response = client.post('/api/text-to-charpentier', params=dict(
                    pool='expanded', seed=2026, shift=shift, meter=meter, mode=mode, cadence=cadence), content='Gloria in excelsis Deo')
                self.assertEqual(response.status_code, 200, response.text[:200])
                data = response.json()
                self.assertEqual(ET.fromstring(data['svg']).tag.split('}')[-1], 'svg')
                self.assertEqual(base64.b64decode(data['audio'])[:4], b'RIFF')
                return data
            first = generate(0, '4/4')
            second = generate(2, '2/2')
            self.assertEqual(first['trace'], second['trace'])
            self.assertEqual(len(first['trace']), 8)
            self.assertTrue(all(t['source']['id'] in ids for t in first['trace'] if t['source']))
            root1, a = voices(first['xml'])
            root2, b = voices(second['xml'])
            self.assertEqual(len(a), 4)
            self.assertEqual([[(m+2,*rest) for m,*rest in part] for part in a], b)
            self.assertEqual(root1.find('.//sound').get('tempo'), root2.find('.//sound').get('tempo'))
            for time in root2.findall('.//time'):
                self.assertEqual((time.findtext('beats'), time.findtext('beat-type')), ('2','2'))
            for meter, mode, shift, cadence in [('2/4','major',-5,'plagal'), ('3/4','minor',3,'half'), ('6/8','minor',5,'deceptive')]:
                result = generate(shift, meter, mode, cadence)
                xml, events = voices(result['xml'])
                self.assertEqual(result['analysis']['cadence'], cadence)
                self.assertEqual([i+1 for i,row in enumerate(result['trace']) if not row['source']], [4,8])
                audio = wave.open(io.BytesIO(base64.b64decode(result['audio'])))
                beats, unit = map(int, meter.split('/'))
                expected = 8 * (beats*4/unit) * 60 / float(xml.find('.//sound').get('tempo'))
                self.assertAlmostEqual(audio.getnframes()/audio.getframerate(), expected, places=3)
            self.assertEqual(client.post('/api/text-to-charpentier?meter=6/8', content='Gloria').status_code, 422)
