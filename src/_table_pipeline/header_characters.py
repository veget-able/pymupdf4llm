"""Character facts from already-produced raw blocks; no extraction."""
import numpy as np

def characters_from_blocks(blocks):
    chars = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    if char["c"].strip():
                        chars.append(
                            (char["bbox"], char["c"], span["size"], bool(span["flags"] & 16), bool(span["flags"] & 2))
                        )
    centers = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for b, *_ in chars]).reshape(-1, 2)
    return chars, centers
