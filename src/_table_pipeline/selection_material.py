"""Actual union alternatives; no approval or adoption policy."""
from dataclasses import dataclass

@dataclass
class Selection:
    original: object
    chosen: object
    split: bool


class StructureSelection:
    def __init__(self): self.items=[]
    def add(self, original, chosen, *, split=False):
        self.items.append(Selection(original, chosen, split))

