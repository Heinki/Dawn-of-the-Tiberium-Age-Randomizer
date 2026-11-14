"""Native ground metadata for Conquest; retain Fortress's placement policy."""

from randomizer.final_fortress.terrain import Terrain as FortressTerrain, BUILDABLE_TILES
from .ground import native_ground


class Terrain(FortressTerrain):
    def __init__(self, source):
        super().__init__(source)
        self.ground = native_ground(self.theater)

    def flat(self, cell):
        tile, sub, _ = self.cells.get(cell, (-1, 0, 0))
        return self.ground.flat(tile, sub)

    def clear(self, cells, *, occupied=()):
        cells = set(cells)
        if not cells or not all(self.flat(cell) for cell in cells):
            return False
        return super().clear(cells, flat_tiles={self.cells[cell][0] for cell in cells}, occupied=occupied)
