"""Transparent views over the actual native producer, without R6 decisions."""
from collections import Counter
from contextlib import contextmanager


class NativePreparation:
    def __init__(self):
        self.decisions = {}
        self.stats = Counter()

    @contextmanager
    def lifetime(self):
        yield

    @contextmanager
    def refinement_scope(self):
        yield

    def placements(self, page, cells, produce, **kwargs):
        return produce(page, cells, **kwargs)

    def text_grid(self, grid, produce):
        return produce(grid)

    def matrices(self, grid, produce):
        return produce(grid)

    def bootstrap_region(self, rows, produce):
        return produce(rows)

    def valid_table(self, header, tab):
        return header.valid_table(tab)
