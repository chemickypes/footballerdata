# core

## 1. Divulgativo
Il cuore del motore — qui vivono la configurazione e tutta la raccolta dati. Qui si decide dove leggere i file, quali sorgenti usare e come trasformare numeri sparsi in un dataset unico che poi alimenta tutti gli altri moduli. In pratica, `core/` prepara il terreno: senza questo strato, i moduli analitici e la web app non avrebbero dati affidabili né regole comuni.

## 2. Tecnico
Package layout:

```text
core/
├── config.py           # cascading configuration layer: paths, constants, source mappings, scoring weights
├── ingestion/          # static preseason pipeline + dynamic in-season feed builders and clients
├── models/             # documentation-only package for quantile/VORP model concepts; code stays in ingestion/static
└── copilot/            # provider-agnostic AI backends and diagnostics for the tactical copilot
```

`core.config` è il foundation point per path, `HEADERS`, team maps, file locations e coefficienti di scoring. `core.ingestion` separa il flusso statico pre-asta dal flusso dinamico settimanale. `core.models` documenta gli algoritmi senza duplicarne il codice. `core.copilot` espone provider interfaces e failover logic per la parte AI.

## 3. Screenshot
> 📸 *Screenshot da aggiungere dopo il redesign UI (glow up).*

## 4. Dipendenze
- Dipende solo da file dati, configurazione locale ed endpoint esterni.
- Non dipende da `modules/` né da `web/`: è il foundation layer del repository.
- Viene consumato da `modules/common/data_provider.py`, dai moduli analitici e da `web/app.py`.
