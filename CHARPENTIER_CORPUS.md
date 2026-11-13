# Source scores for Text to Charpentier

The local builder reads a curated set of original score files from CSMD and HARMONIA. Each entry records the encoded part and a checksum of the MusicXML or MXL used. Each pattern identifies the first matching measure in that part, the meter of the source, and the starting offset in quarter notes. The same shape can be attested by several scores. The collection name identifies where the encoding came from. The composer field identifies whose music it represents.

**CSMD.** Xavier Fresquet, [Charpentier Sacred Music Dataset, v1.0](https://doi.org/10.5281/zenodo.20450425), CC BY 4.0 (dataset). Only top-level MXL files are read. Transposed copies, reduced voices and duplicates are excluded. The encoded credits identify Lully in *Ave coeli munus supernum* and Étienne Moulinié in *Flores apparuerunt*. They enter the comparison repertoire under those names. Some vocal movements of the same mass are indexed separately. A score count therefore describes source files, rather than a count of distinct compositions.

**HARMONIA.** The nine selected local records come from [PDMX](https://doi.org/10.5281/zenodo.15571083), Long et al. The builder checks each HARMONIA score.json against the original archive and reads its per-score public-domain mark or CC0 declaration, contributor and upstream score URL. This supplies evidence missing from the legacy HARMONIA records without changing their catalogue status. Two Lully dance movements and *Stingo*, an anonymous tune in John Playford’s collection, contribute instrumental parts. The other selections contribute vocal parts. The source labels the composer of *Venez approchons nous* simply “Dumont”. Its catalogue attribution remains qualified.

**Meter and provenance.** The 21 scores yield 676 source-specific patterns and 430 distinct combinations of output meter, rhythm and contour. Four output meters have both Charpentier and expanded coverage. Compound duple 6/8 draws on the expanded repertoire. The 6/8 edition of *O Come Divine Messiah* in HARMONIA credits Charpentier, but its attribution requires work-level confirmation before inclusion in the strict pool. CSMD’s *Salve puerule* supplies native 3/4 examples. A second arrangement of Purcell’s *In these delightful pleasant groves* duplicates the vocal patterns and was omitted.

| Output meter | Source-specific patterns | Source unit |
| --- | ---: | --- |
| 4/4 | 78 | Complete 4/4 bar |
| 2/2 | 162 | Complete 2/2 bar |
| 2/4 | 351 | First or second half of a 4/4 or 2/2 bar |
| 3/4 | 72 | Complete 3/4 bar |
| 6/8 | 13 | Complete 6/8 bar |

The counts describe each source meter separately. A consumer may group 4/4 and 2/2 for common-time retrieval and label the adopted notation in its trace. Three quarter notes per bar can describe 3/4 or 6/8, so the builder preserves the encoded meter to distinguish those families.

**Extraction.** The builder requires complete source measures of the expected duration and a single voice and staff. Each selected window contains two to four positive-duration notes. Rests, ties, chords, grace notes, cues and nonbinary note lengths are excluded from that window. To extract a 2/4 cell, the builder requires an existing boundary between notes at exactly two quarter notes. A half-bar keeps its source durations, source meter, measure number, and offset (zero or two quarter notes). Diatonic distance counts written letter steps from the first pitch and omits accidentals. The pitch and harmony engine supplies absolute pitches, harmonization and lyrics for the new study.

Each supported combination of repertoire and meter was checked for usable openings and tonic endings with two, three, and four notes. The 6/8 witnesses in the expanded repertoire come from *Stingo* and *Venez approchons nous*.

To rebuild from the lab checkout, run:

```sh
python3 1-MELODY-LAB/SUITE/melody-web/build_charpentier_library.py --pdmx /path/to/PDMX.zip
```

The source archive must contain PDMX/PDMX.csv and its data and metadata directories. The browser and local app use the built JSON and do not require this archive.
