"""Standalone edition of the MELODY text-to-SATB API."""
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from charpentier_settings import INTERVALS, MINOR_INTERVALS, METERS, meter_family

app = FastAPI()
arrange_slots = asyncio.Semaphore(1)

@app.get("/")
def home():
    return RedirectResponse("/en/text-to-charpentier/")

@app.get('/api/text-to-charpentier/library')
def charpentier_library():
    library = json.loads(Path(__file__).with_name('charpentier-library.json').read_text())
    shapes = {(meter_family(row.get('family', row['meter'])), tuple(row['contour']), tuple(row['rhythm'])) for row in library['patterns']}
    return {'sources': library['sources'], 'shapes': len(shapes)}


@app.post('/api/text-to-charpentier')
async def generate_charpentier(request: Request, pool: Literal['core','expanded']='core',
                               seed: int = Query(default=1, ge=0, le=2147483647),
                               shift: int=0, meter: str='4/4', mode: Literal['major','minor']='major',
                               cadence: Literal['perfect','half','plagal','deceptive']='perfect'):
    if shift not in (MINOR_INTERVALS if mode == 'minor' else INTERVALS) or meter not in METERS:
        raise HTTPException(422, 'Tonalité ou mesure non prise en charge.')
    if pool == 'core' and meter == '6/8':
        raise HTTPException(422, 'Le 6/8 est disponible dans le répertoire élargi.')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 640:
            raise HTTPException(422, 'La phrase est limitée à 160 caractères.')
    try:
        phrase = body.decode('utf-8').strip()
    except UnicodeDecodeError:
        raise HTTPException(422, 'Texte illisible.')
    if not 1 <= len(phrase) <= 160 or any(not c.isprintable() for c in phrase):
        raise HTTPException(422, 'Entrez une phrase sur une ligne, de 1 à 160 caractères.')
    if arrange_slots.locked():
        raise HTTPException(429, 'Un calcul est en cours. Réessayez dans quelques secondes.')
    async with arrange_slots:
        worker = Path(__file__).with_name('charpentier_worker.py')
        proc = await asyncio.create_subprocess_exec(sys.executable, str(worker), '--pool', pool, '--seed', str(seed),
                    '--shift', str(shift), '--meter', meter, '--mode', mode, '--cadence', cadence, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(phrase.encode()), timeout=30)
        except asyncio.TimeoutError:
            raise HTTPException(504, 'La génération a dépassé le délai prévu.')
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        if proc.returncode == 2:
            raise HTTPException(422, 'Entrez une phrase de 1 à 32 mots.')
        if proc.returncode:
            import logging
            logging.getLogger(__name__).error('Charpentier worker: %s', err[-1000:].decode(errors='replace'))
            raise HTTPException(503, 'La génération est momentanément indisponible.')
        return json.loads(out)

app.mount('/',StaticFiles(directory=Path(__file__).parent/'site',html=True),name='portal')
