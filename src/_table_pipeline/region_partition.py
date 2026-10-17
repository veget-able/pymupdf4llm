"""Shared node-center ownership contract for V7 region consumers."""


class InvalidRegionPartition(ValueError):
    """A proposed split cannot preserve unique, nonempty node ownership."""


def partition_node_centers(centers, boxes):
    """Return ordered local node indices, or None for an invalid partition.

    Uses the existing V7 page-space, inclusive-boundary convention. Every
    input node needs exactly one owner and every child needs at least one
    node. Does not infer text membership, change boxes, or perform inference.
    """
    if len(boxes) == 0 or len(centers) == 0:
        return None
    members = [[] for _ in boxes]
    for i, (x, y) in enumerate(centers):
        owners = [j for j, b in enumerate(boxes)
                  if b[0] <= x <= b[2] and b[1] <= y <= b[3]]
        if len(owners) != 1:
            return None
        members[owners[0]].append(i)
    return members if all(members) else None
