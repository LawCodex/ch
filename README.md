# LawCodex — Switzerland (ch)

Swiss federal law as Markdown: every text **in force** in the
**Systematic Collection of Federal Law** — *Systematische Rechtssammlung* (SR),
*Recueil systématique* (RS), *Raccolta sistematica* (RS) — generated from the official
Akoma Ntoso XML published by the Federal Chancellery on [Fedlex](https://www.fedlex.admin.ch/).

Consolidation state: latest consolidated version applicable on **2026-10-11** (retrieval date).

## Coverage

**15,286 Markdown files** for **5,072 SR texts** in force (5,069 with text):

| Language | Directory | Internal law (SR 1–9) | International law (SR 0.x) | Total |
|---|---|---|---|---|
| German | `de/` | 1,990 | 3,079 | 5,069 |
| French | `fr/` | 1,990 | 3,079 | 5,069 |
| Italian | `it/` | 1,990 | 3,079 | 5,069 |
| Romansh | `rm/` | 76 | 3 | 79 |

Every SR entry with Fedlex status *In Kraft* ("in force") is included, both internal law
(*Landesrecht*, SR 1–9) and international law (*Staatsvertragsrecht*, SR 0.x: treaties,
agreements and their annexes and *Geltungsbereich* / scope-of-application tables). For each
text and language the most recent consolidation whose date of applicability is not in the
future is used.

| Type (front-matter `type`) | Fedlex document type | Texts (per language) |
|---|---|---|
| `constitution` | Federal Constitution (SR 101) | 1 |
| `cantonal_constitution` | Kantonsverfassung (guaranteed cantonal constitutions) | 26 |
| `code` | Bundesgesetz (major codes, see below) | 8 |
| `act` | Bundesgesetz, dringliches Bundesgesetz | 332 |
| `ordinance` | Verordnung der Bundesversammlung / des Bundesrates / Departements- und Amtsverordnung, Erlasse der Gerichte, Anstalten, Kommissionen | 1,556 |
| `federal_decree` | Bundesbeschluss (referendum / einfach) | 53 |
| `agreement` | Verträge zwischen Bund und Kantonen | 14 |
| `treaty` | Internationaler Rechtstext bilateral / multilateral (SR 0.x) | 3,079 |

`type: code` is used for the big codes (ZGB/CC 210, OR/CO 220, StGB/CP 311.0, StPO/CPP 312.0,
ZPO/CPC 272, SchKG/LP 281.1, MStG/CPM 321.0, BGG/LTF 173.110); `cantonal_constitution` are
the cantonal constitutions guaranteed by the Confederation (SR 131.x).

### Not covered

- **Repealed / superseded texts** and historical consolidations (Fedlex status *Nicht mehr in
  Kraft*, *Nicht mehr in der SR publiziert*) and texts **not yet in force**.
- The **Official Compilation** (AS/RO/RU, amending acts as published) and the **Federal
  Gazette** (BBl/FF/FF) — only the consolidated SR is mirrored.
- **Cantonal law** (each canton publishes its own collection).
- **English** translations (unofficial, available on Fedlex for ~260 texts) — Switzerland's
  official languages only.
- **Romansh** (`rm/`): only the texts the Confederation translates into Romansh (Romansh is a
  partially official language; Fedlex itself notes that the Romansh versions are for
  information and are not legally binding) — about 80 texts, including the Federal
  Constitution, ZGB, OR and StGB.
- 3 in-force SR entries have no text manifestation at all on Fedlex (only metadata) and are
  therefore missing: SR 0.142.114.548 (CH–IT agreement on emigration of Italian workers, 1964),
  SR 0.142.116.362 (CH–NL declaration, 1862), SR 672.946.3 (federal decree approving a
  double-taxation protocol, 2011). 28 entries still flagged "in force" but whose end-of-validity
  date has passed or whose entry into force lies in the future were excluded.
- Images (a few hundred diagrams/forms, e.g. road signs) are not copied into the repository;
  they are linked to the Fedlex file store.

## Structure

One Markdown file per SR number and language, in a tree that mirrors the SR numbering:

```
de/ fr/ it/ rm/                       one directory per language
  1/10/101-bv.md                      internal law: <1st digit>/<first 2 digits>/<SR>-<slug>.md
  2/21/210-zgb.md
  3/31/311.0-stgb.md
  0/0.1/0.10/0.101-emrk.md            international law: 0/0.<d>/0.<dd>/<SR>-<slug>.md
```

The slug is the official abbreviation in that language when there is one (`zgb`, `cc`),
otherwise the beginning of the title, so file names differ between languages but the SR number
prefix is always the same (`de/2/21/210-zgb.md` ↔ `fr/2/21/210-cc.md` ↔ `it/2/21/210-cc.md`).
No directory holds more than ~420 files.

Each file has YAML front matter:

```yaml
title: "Schweizerisches Zivilgesetzbuch vom 10. Dezember 1907"
short_title: "ZGB"
identifier: "SR 210"                 # SR number
eli: "https://fedlex.data.admin.ch/eli/cc/24/233_245_233"
type: code
jurisdiction: ch
language: de
date: 1907-12-10                     # date of the act (dateDocument)
in_force_since: 1912-01-01           # dateEntryInForce
last_amended: 2026-07-01             # date of applicability of the consolidation used
status: in_force
source: "https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de"
retrieved: 2026-10-11
```

Body: the cover block (SR number, title, date and "Stand am …"), preamble, then the
hierarchy (Teil/Titel/Kapitel/Abschnitt… → `##`, `###`, …) with articles as headings
(`Art. 1 Sachüberschrift`; below `######` articles fall back to bold). Numbered paragraphs
(*Absätze*) are rendered as `<sup>1</sup> text`, enumerations as lists, the official footnotes
(amendment history, AS references, cross-references) as Markdown footnotes `[^n]`, annexes
(*Anhänge*) and scope-of-application tables as `##` sections at the end. Simple tables become
Markdown tables; tables with merged cells are kept as HTML. Text that an amending provision
inserts into another act (quoted structures) is rendered as a block quote.

## Source

- Fedlex linked data (JOLux ontology), SPARQL endpoint
  <https://fedlex.data.admin.ch/sparqlendpoint> — catalogue of `jolux:ConsolidationAbstract`
  with `jolux:inForceStatus` = in force, their consolidations and manifestations.
- Fedlex file store <https://fedlex.data.admin.ch/filestore/…> — Akoma Ntoso 3.0 XML of each
  consolidation (`…/<lang>/xml/…xml`). Every in-force text that has a text manifestation is available as XML, so no HTML/PDF fallback was needed.
- Human-readable pages: `https://www.fedlex.admin.ch/eli/cc/<…>/<lang>` (link in each file's
  `source`).

## Licence / copyright

Under Art. 5 of the Federal Act on Copyright (URG/LDA, SR 231.1), acts, ordinances,
international treaties and other official enactments are **not protected by copyright**. The
Fedlex data are published as Open Government Data. Note that only the publications in the
Official Compilation (AS) and the SR consolidation published electronically on Fedlex are
legally authoritative (Publication Act, SR 170.512); this repository is an unofficial
conversion — consult Fedlex for authoritative texts.

## Regenerate

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/fetch.py ../_raw/ch --refresh          # catalogue (SPARQL) + XML download, cached
python3 scripts/convert.py ../_raw/ch . --retrieved $(date +%F)
```

`fetch.py` writes `catalog.json` and the XML files to the raw directory (≈ 1 GB for de/fr/it/rm;
not committed), 4 parallel requests with retries and a `LawCodex/1.0` User-Agent.
`convert.py` (lxml) rewrites the language trees. Before regenerating, delete the language
directories so that texts that have left the SR disappear.
