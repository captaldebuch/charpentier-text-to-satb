# Charpentier text to SATB

MELODY research software by Xavier Fresquet, Sorbonne Université. Release 1.0.0.

Generate an eight-measure four-part setting from a short text. The index contains 408 distinct rhythm and contour patterns from 21 score files. Six measures identify a source witness and two cadences are composed. A whole-study voice-leading solver, score analysis, counterpoint audit, MusicXML, SVG and WAV accompany each setting.

## Run locally

Use Python 3.11 in a virtual environment.

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8816
```

Open http://127.0.0.1:8816/ or the [public demonstrator](https://melody.isir.upmc.fr/en/text-to-charpentier/). French and Arabic pages are at /text-to-charpentier/ and /ar/text-to-charpentier/. The standalone server exposes the same SATB API as the institutional portal.

## Verify

Install pytest and run `python -m pytest -q`. Four source-score round-trip tests additionally require `CSMD_STABAT` pointing to the original Charp-Stabat.mxl. The generated example and public feature index are bundled. Edition credits and original links appear in charpentier-library.json and [the selection notes](CHARPENTIER_CORPUS.md). Full historical scores are acquired separately. To rebuild use `python build_charpentier_library.py --lab-root /path/to/1-MELODY-LAB --pdmx /path/to/PDMX.zip`.

## Attribution

The software draws on the [CSMD](https://doi.org/10.5281/zenodo.20450425) and [PDMX](https://doi.org/10.5281/zenodo.15571083) collections. Source-specific rights and contributor credits accompany each indexed score. OpenAI Codex assisted with software implementation, testing and technical documentation.

Archived release and technical report: [10.5281/zenodo.24190673](https://doi.org/10.5281/zenodo.24190673).
