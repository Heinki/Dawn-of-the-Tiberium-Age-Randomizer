# DTA Archipelago integration

The preserved Archipelago mode now uses the `dta` APWorld and the launcher-owned DTA catalogue.

The generated world contains:

- 81 DTA missions;
- stable mission-completion reward locations;
- 117 mobile-unit and 16 defensive-building access rewards with their active buff catalogue;
- the five broad Player Army rewards;
- two power unlocks and five supported power-buff rewards;
- two optional enemy-only scaling rewards;
- the existing signed run-manifest, seed, placement, save/load, and client-handshake flow.

Build the world with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Archipelago\build_apworld.ps1
```

This writes `Archipelago/dta.apworld`. Use the APWorld and launcher from the same build because their catalogue checksums and versions must match.

Live multiworld connection and end-to-end item receipt still require verification with an Archipelago 0.6.7 installation.
