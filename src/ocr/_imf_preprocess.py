"""Frozen IMF2 resize/grayscale arithmetic; preserve uint8 truncation."""

import numpy as np


def resize_image(image: np.ndarray, new_size: tuple) -> np.ndarray:
    """
    Resize an image using bilinear interpolation with numpy (vectorized).
    Equivalent to cv2.resize(..., INTER_LINEAR).

    Parameters
    ----------
    image : np.ndarray
        Input image (H, W) or (H, W, C).
    new_size : tuple
        (new_width, new_height)

    Returns
    -------
    np.ndarray
        Resized image.
    """
    h, w = image.shape[:2]
    new_w, new_h = new_size

    # Generate grid of coordinates in output image
    x = (np.arange(new_w) + 0.5) * (w / new_w) - 0.5
    y = (np.arange(new_h) + 0.5) * (h / new_h) - 0.5

    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    dx = (x - x0)[None, :]  # shape (1, new_w)
    dy = (y - y0)[:, None]  # shape (new_h, 1)

    # Clip to valid range
    x0 = np.clip(x0, 0, w - 1)
    y0 = np.clip(y0, 0, h - 1)

    if image.ndim == 3:
        # Expand dimensions for broadcasting
        Ia = image[y0[:, None], x0[None, :]]  # top-left
        Ib = image[y0[:, None], x1[None, :]]  # top-right
        Ic = image[y1[:, None], x0[None, :]]  # bottom-left
        Id = image[y1[:, None], x1[None, :]]  # bottom-right
    else:
        Ia = image[np.ix_(y0, x0)]
        Ib = image[np.ix_(y0, x1)]
        Ic = image[np.ix_(y1, x0)]
        Id = image[np.ix_(y1, x1)]

    # Bilinear interpolation
    wa = (1 - dx) * (1 - dy)
    wb = dx * (1 - dy)
    wc = (1 - dx) * dy
    wd = dx * dy

    out = (
        (
            wa[..., None] * Ia
            + wb[..., None] * Ib
            + wc[..., None] * Ic
            + wd[..., None] * Id
        )
        if image.ndim == 3
        else (wa * Ia + wb * Ib + wc * Ic + wd * Id)
    )

    return np.clip(out, 0, 255).astype(image.dtype)


def to_gray(image: np.ndarray) -> np.ndarray:
    """
    Convert a BGR image to grayscale using numpy only.
    Equivalent to cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).

    Parameters
    ----------
    image : np.ndarray
        Input image in BGR format, shape (H, W, 3).

    Returns
    -------
    np.ndarray
        Grayscale image, shape (H, W).
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Input must be a BGR image with shape (H, W, 3).")

    # Extract B, G, R channels
    B = image[:, :, 0].astype(np.float32)
    G = image[:, :, 1].astype(np.float32)
    R = image[:, :, 2].astype(np.float32)

    # Apply standard BGR ¡æ Gray conversion formula
    gray = 0.114 * B + 0.587 * G + 0.299 * R

    # Clip to valid range and convert back to uint8
    return np.clip(gray, 0, 255).astype(np.uint8)
