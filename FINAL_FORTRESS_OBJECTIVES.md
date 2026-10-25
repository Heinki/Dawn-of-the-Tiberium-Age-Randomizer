# Neutral objective candidates

These civilian/neutral building assets are present in this DTA installation's
`INI/Rules.ini` and `INI/Art.ini`. The selected objective is **Executive Building
(`V37`)**, using its native headquarters appearance. Its SHP and bib assets are
present in the installed MIX archives. The 2×2 foundation fits the reviewed
objective placement. Fortress health stays at 7,000 before durability upgrades,
independent of V37's native 3,000 HP. It remains visible on radar, cannot be sold
or captured, and retains the existing objective loss and reserve-shield logic.
The other candidates below remain reference alternatives.

| Native ID | Installed name | Why it could work |
| --- | --- | --- |
| `ARMORY` | Civilian Armory | Compact military facility; the clearest thematic fit for a fortress objective. |
| `ARMORYB` | Civilian Armory | Larger variant with a 3×3 foundation; more prominent than the compact armory. |
| `CA0007` | Field Generator | Distinctive technology structure; suitable for a shield-generator defense scenario. |
| `STEX` | Stock Exchange | Prominent 3×3 landmark with an easily recognizable silhouette. |
| `CHOSP` | Civilian Hospital | Clear civilian protection objective with a 2×3 foundation. |
| `ARCO` | Arcology | Large landmark; its visible art needs generous clearance despite its small configured foundation. |
| `V37` | Westwood Executive Building | Distinctive headquarters-style civilian landmark with a 2×2 foundation. |
| `CITY09` | Abandoned Warehouse | Industrial stronghold appearance without a faction-specific tech-building identity. |

Before switching to another candidate, validate its art and footprint beside the starting base. Keep
Fortress health, ownership, defeat conditions and durability upgrades independent
of the chosen building's native strength. Disable its native gameplay benefits:
armories train units, hospitals heal infantry, and the stock exchange produces
cash. A visual replacement must not silently add those bonuses.
