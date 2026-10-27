# -*- coding: utf-8 -*-
"""
Crack thickness calculations from segmented image stacks (z, y, x).

Two methods are available:

  "maxmin"      Binned max-min (original method). The xy plane is divided into
                square bins of binsize; in every bin the thickness is
                max(z) - min(z) of the crack voxel centres. Empty or zero bins
                are ignored and bins thicker than 5x the mean are discarded as
                misidentified points.

  "continuous"  Continuous columns (as in device-comparison/crack_compare.py).
                In every (y, x) column the longest unbroken run of crack voxels
                along z is taken as the crack opening (or, optionally, the total
                number of crack voxels in the column). The value is corrected
                for crack tilt to the local crack-plane normal:
                    t_perp = t_run * cos(phi)
                where phi is the local inclination of the Gaussian-smoothed
                crack mid-surface. Columns steeper than max_inclination_deg are
                excluded.

Thickness values are returned in um, xy coordinates in mm.

@author: bhejazi
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

MM2UM = 1000.0
IMAGE_EXT = (".tif", ".tiff")


# ---------------------------------------------------------------- loading
def list_images(path):
    return sorted(f for f in os.listdir(path) if f.lower().endswith(IMAGE_EXT))


def load_images(path, progress=None):
    """Load a folder of segmented .tif slices into a (z, y, x) array."""
    files = list_images(path)
    if not files:
        raise FileNotFoundError(f"No .tif images found in {path}")
    first = np.array(Image.open(os.path.join(path, files[0])))
    images = np.zeros((len(files),) + first.shape, dtype=first.dtype)
    for i, f in enumerate(files):
        images[i] = np.array(Image.open(os.path.join(path, f)))
        if progress is not None:
            progress(i + 1, len(files))
    return images


def voxel_size_from_tags(path):
    """Voxel size (um) from the TIFF resolution tags of the first slice, or
    None if the tags are missing or not physical."""
    files = list_images(path)
    if not files:
        return None
    try:
        with Image.open(os.path.join(path, files[0])) as img:
            xres = img.tag_v2.get(282)
            unit = img.tag_v2.get(296, 2)
    except (AttributeError, OSError):
        return None
    if not xres or float(xres) <= 1:
        return None
    per_unit_um = {2: 25400.0, 3: 1e4}.get(unit)
    return per_unit_um / float(xres) if per_unit_um else None


def pixel_value_counts(images):
    vals, counts = np.unique(images, return_counts=True)
    return vals, counts


def crack_mask(images, crack_pix_val, zthresh_mm=None, voxel_size=None):
    """Boolean crack mask. If zthresh_mm is given, slices further than zthresh
    from the median crack height are removed (z outlier removal)."""
    mask = images == crack_pix_val
    if zthresh_mm is not None:
        z_counts = mask.sum((1, 2))
        if z_counts.sum() == 0:
            return mask
        z = np.repeat(np.arange(mask.shape[0]), z_counts)
        z_med = np.median(z) * voxel_size / MM2UM
        z_mm = np.arange(mask.shape[0]) * voxel_size / MM2UM
        mask[np.abs(z_mm - z_med) > zthresh_mm] = False
    return mask


# ---------------------------------------------------------------- statistics
def describe(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return dict(mean=np.nan, median=np.nan, sd=np.nan, p10=np.nan, p90=np.nan, n=0)
    return dict(mean=float(v.mean()), median=float(np.median(v)), sd=float(v.std()),
                p10=float(np.percentile(v, 10)), p90=float(np.percentile(v, 90)), n=int(v.size))


# ---------------------------------------------------------------- binned max-min
def binned_maxmin(mask, voxel_size, binsize_mm=0.01, outlier_factor=5.0):
    """Binned max-min thickness (um) and mean crack height (mm) per square xy
    bin of binsize_mm, anchored at the volume origin. Bins without crack are
    NaN, as are zero-extent bins (excluded from the mean as in the original
    method). Bins thicker than outlier_factor x mean are removed in
    'thickness'; 'thickness_raw' keeps them."""
    z, y, x = np.nonzero(mask)
    b = binsize_mm * MM2UM / voxel_size                     # bin size in voxels
    ny, nx = int(np.ceil(mask.shape[1] / b)), int(np.ceil(mask.shape[2] / b))
    key = (y // b).astype(np.int64) * nx + (x // b).astype(np.int64)
    zmax = np.full(ny * nx, -1, np.int64)
    zmin = np.full(ny * nx, np.iinfo(np.int64).max, np.int64)
    np.maximum.at(zmax, key, z)
    np.minimum.at(zmin, key, z)
    cnt = np.bincount(key, minlength=ny * nx)
    zsum = np.bincount(key, weights=z, minlength=ny * nx)

    has = zmax >= 0
    t_raw = np.where(has, (zmax - zmin) * voxel_size, np.nan).astype(float)
    t_raw[t_raw == 0] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        height = np.where(has, zsum / cnt * voxel_size / MM2UM, np.nan)
    mean_before = np.nanmean(t_raw) if np.isfinite(t_raw).any() else np.nan
    t = t_raw.copy()
    t[t > outlier_factor * mean_before] = np.nan
    return dict(method="maxmin",
                thickness=t.reshape(ny, nx),
                thickness_raw=t_raw.reshape(ny, nx),
                height=height.reshape(ny, nx),
                pixel_mm=binsize_mm,
                mean_before=float(mean_before),
                stats=describe(t),
                stats_raw=describe(t_raw))


# ---------------------------------------------------------------- continuous columns
def column_maps(mask, voxel_size):
    """Per-(y, x) column: voxel count, longest contiguous run, number of runs
    and mean crack height (um)."""
    count = mask.sum(0).astype(np.int32)
    run = np.zeros(mask.shape[1:], np.int32)
    longest = np.zeros_like(run)
    nruns = np.zeros_like(run)
    zsum = np.zeros(mask.shape[1:], np.float64)
    prev = np.zeros(mask.shape[1:], bool)
    for k in range(mask.shape[0]):
        m = mask[k]
        run = (run + 1) * m
        np.maximum(longest, run, out=longest)
        nruns += m & ~prev
        prev = m
        zsum += k * m
    with np.errstate(invalid="ignore", divide="ignore"):
        height = np.where(count > 0, zsum / count * voxel_size, np.nan)
    return dict(count=count, longest=longest, nruns=nruns, height=height)


def inclination(height, voxel_size, sigma_um=15.0):
    """Local inclination (rad) of the crack mid-surface h(x, y) relative to
    the slice plane, from a normalised-Gaussian-smoothed height map."""
    valid = np.isfinite(height)
    sig = sigma_um / voxel_size
    num = ndimage.gaussian_filter(np.where(valid, height, 0.0), sig)
    den = ndimage.gaussian_filter(valid.astype(float), sig)
    with np.errstate(invalid="ignore", divide="ignore"):
        hs = np.where(den > 0.2, num / den, np.nan)
    gy, gx = np.gradient(hs, voxel_size)
    return np.arctan(np.hypot(gx, gy))


def continuous_columns(mask, voxel_size, measure="longest", tilt_correction=True,
                       sigma_um=15.0, max_inclination_deg=60.0):
    """Per-column thickness (um). measure = 'longest' (longest unbroken run,
    main crack opening) or 'count' (all crack voxels in the column). With
    tilt_correction the value is projected onto the local crack-plane normal
    and columns steeper than max_inclination_deg are excluded."""
    maps = column_maps(mask, voxel_size)
    has = maps["count"] > 0
    t_z = (maps["longest"] if measure == "longest" else maps["count"]) * voxel_size
    phi = inclination(maps["height"], voxel_size, sigma_um)
    if tilt_correction:
        ok = has & np.isfinite(phi) & (phi < np.deg2rad(max_inclination_deg))
        t = np.where(ok, t_z * np.cos(phi), np.nan)
    else:
        ok = has
        t = np.where(ok, t_z, np.nan).astype(float)
    return dict(method="continuous",
                thickness=t,
                thickness_z=np.where(has, t_z, np.nan).astype(float),
                height=maps["height"] / MM2UM,
                inclination_deg=np.where(has, np.rad2deg(phi), np.nan),
                pixel_mm=voxel_size / MM2UM,
                frac_single_run=float((maps["nruns"][has] == 1).mean()) if has.any() else np.nan,
                frac_columns_used=float(ok.sum() / has.sum()) if has.any() else np.nan,
                median_inclination_deg=float(np.rad2deg(np.nanmedian(phi[ok]))) if ok.any() else np.nan,
                stats=describe(t),
                stats_z=describe(t_z[has]))


def summary_text(res, voxel_size):
    s = res["stats"]
    lines = []
    if res["method"] == "maxmin":
        lines.append(f"Method: binned max-min, bin size {res['pixel_mm']:g} mm")
        lines.append(f"Mean before removing misidentified bins: {res['stats_raw']['mean']:.2f} um "
                     f"(n = {res['stats_raw']['n']})")
        lines.append(f"Mean after removing misidentified bins:  {s['mean']:.2f} um")
    else:
        lines.append("Method: continuous columns")
        lines.append(f"Columns with a single crack run: {100 * res['frac_single_run']:.1f} %")
        lines.append(f"Columns used: {100 * res['frac_columns_used']:.1f} %")
        if np.isfinite(res["median_inclination_deg"]):
            lines.append(f"Median crack inclination: {res['median_inclination_deg']:.1f} deg")
        lines.append(f"Mean thickness along z (no tilt correction): {res['stats_z']['mean']:.2f} um")
        lines.append(f"Mean thickness: {s['mean']:.2f} um")
    lines.append(f"Median {s['median']:.2f} um, SD {s['sd']:.2f} um, "
                 f"P10-P90 {s['p10']:.2f}-{s['p90']:.2f} um, n = {s['n']}")
    lines.append(f"Mean thickness in voxels: {s['mean'] / voxel_size:.2f}")
    return "\n".join(lines)
