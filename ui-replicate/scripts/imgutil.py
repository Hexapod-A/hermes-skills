"""Shared image helpers for ui-replicate (Pillow + numpy only)."""
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # Dribbble originals can be 6000+ px wide


def load_rgb(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    return im.convert("RGB")


def to_float(im):
    return np.asarray(im, dtype=np.float64) / 255.0


def gray(arr):
    """Rec. 601 luma from an RGB float array."""
    return arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114


def _gauss_kernel(sigma=1.5, radius=5):
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-(x ** 2) / (2 * sigma ** 2))
    return k / k.sum()


def _blur(a, k):
    pad = len(k) // 2
    a = np.pad(a, pad, mode="reflect")
    a = _conv_rows(a, k)
    return _conv_rows(a.T, k).T


def _conv_rows(a, k):
    # 1-D convolution along axis 1 as a weighted sum of shifted slices (fast in numpy)
    n = len(k)
    out = np.zeros((a.shape[0], a.shape[1] - n + 1))
    for i, w in enumerate(k):
        out += w * a[:, i:i + out.shape[1]]
    return out


def ssim_map(x, y, data_range=1.0):
    """Gaussian-window SSIM (Wang et al. 2004) on two 2-D float arrays. Returns the map."""
    k = _gauss_kernel()
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    mx, my = _blur(x, k), _blur(y, k)
    sxx = _blur(x * x, k) - mx * mx
    syy = _blur(y * y, k) - my * my
    sxy = _blur(x * y, k) - mx * my
    num = (2 * mx * my + c1) * (2 * sxy + c2)
    den = (mx * mx + my * my + c1) * (sxx + syy + c2)
    return num / den


def srgb_to_lab(arr):
    """RGB float [0,1] (H,W,3) -> CIE Lab (D65)."""
    a = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = a @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    A = 500 * (f[..., 0] - f[..., 1])
    B = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, A, B], axis=-1)


def hex_of(rgb):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in rgb[:3])


def rgb_of_hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
