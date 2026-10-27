# -*- coding: utf-8 -*-
"""
Last updated on Tue Oct 27, 2026

@author: bhejazi

Finding crack thickness from segmented images (command line version, see
crack_thickness_gui.py for the GUI)
crack and other features in image should be labeled as integer values
images should also be in .tif format

Thickness methods (see crack_thickness.py):
  1. binned max-min: max(z) - min(z) of the crack points in square xy bins
  2. continuous columns: longest unbroken run of crack voxels per (y, x)
     column, corrected for crack tilt (t * cos(phi))
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from colorama import Fore, Style

import crack_thickness as ct


def ask(prompt):
    print(Fore.MAGENTA + Style.BRIGHT + prompt + Fore.BLUE + Style.BRIGHT)
    answer = input("-> ")
    print("\n")
    return answer


def plot_result(res, voxel_size):
    px = res["pixel_mm"]
    ny, nx = res["thickness"].shape
    ext = [0, nx * px, ny * px, 0]
    if res["method"] == "maxmin":
        panels = [(res["height"], "Mean relative height of crack (mm)", {}),
                  (res["thickness_raw"], "Thickness before removing \n misidentified points (μm)", {}),
                  (res["thickness"], "Thickness after removing \n misidentified points (μm)", {})]
    else:
        panels = [(res["height"], "Mean relative height of crack (mm)", {}),
                  (res["inclination_deg"], "Local crack inclination (deg)", dict(vmin=0, vmax=90)),
                  (res["thickness"], "Continuous-column thickness (μm)", {})]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, (data, title, kw) in zip(axes, panels):
        im = ax.imshow(data, interpolation='none', extent=ext, **kw)
        ax.set_title(title)
        ax.set_xlabel("x (mm)", fontsize=15)
        ax.set_ylabel("y (mm)", fontsize=15)
        fig.colorbar(im, ax=ax)
    plt.show()
    return fig


def main():
    while True:
        path = ask("\nEnter image file path:")
        if os.path.exists(path):  # check if path is valid
            break
        print(Fore.RED + Style.BRIGHT + "Path does not exist, re-enter correct path")

    vox_tag = ct.voxel_size_from_tags(path)
    hint = f" (press enter to use {vox_tag:.4g} from TIFF tags)" if vox_tag else ""
    answer = ask("What is the voxel size? (in μm)" + hint)
    voxel_size = float(answer) if answer or not vox_tag else vox_tag

    print(Fore.MAGENTA + Style.NORMAL + "Loading images..")
    images = ct.load_images(path)

    print("\n")
    print(Fore.MAGENTA + Style.NORMAL + "Calculating pixel values..")
    print("\n")
    maxx = (images.shape[2] - 1) * voxel_size / ct.MM2UM
    maxy = (images.shape[1] - 1) * voxel_size / ct.MM2UM
    vals, counts = ct.pixel_value_counts(images)

    fig, ax = plt.subplots()
    temp_img = ax.imshow(images[images.shape[0] // 2], interpolation='none', extent=[0, maxx, maxy, 0])
    ax.set_title('Pixel values of mid slice of crack image stack')
    ax.set_xlabel("x (mm)", fontsize=15)
    ax.set_ylabel("y (mm)", fontsize=15)
    if vals.size > 10:
        fig.colorbar(temp_img)
    else:
        fig.colorbar(temp_img, ticks=vals)
    plt.show()

    for v, c in zip(vals, counts):
        print(Fore.MAGENTA + Style.BRIGHT + f"{c}" + Fore.MAGENTA + Style.NORMAL + " pixels with value"
              + Fore.MAGENTA + Style.BRIGHT + f" {v}")
    print("\n")
    crack_pix_val = images.dtype.type(float(ask("What is the crack pixel value? (check image and pixel counts)")))

    print(Fore.MAGENTA + Style.NORMAL + "Calculating pixel coordinates..")
    mask = ct.crack_mask(images, crack_pix_val)
    z_mm = np.nonzero(mask)[0] * voxel_size / ct.MM2UM

    # Eliminate some outliers
    fig, ax = plt.subplots()
    ax.violinplot(z_mm, showmedians=True)
    ax.set_title(f"z spread of crack, median is {np.median(z_mm):.4f} mm")
    ax.set_ylabel("z (mm)")
    plt.show()

    print("\n")
    if ask("Do you want to remove outliers in z? (y/n)") == "y":
        zthresh = float(ask("Set threshold for z, removes points which are >(median val + threshold) "
                            "& <(median val - threshold)"))
        mask = ct.crack_mask(images, crack_pix_val, zthresh, voxel_size)

    while True:
        method = ask("Select thickness method:\n"
                     "  1 = binned max-min (max(z) - min(z) per bin)\n"
                     "  2 = continuous columns (longest unbroken run per column, tilt-corrected)")
        if method == "2":
            tilt = ask("Correct for crack tilt? (y/n)") != "n"
            sigma, max_incl = 15.0, 60.0
            if tilt:
                answer = ask("Smoothing of crack mid-surface for the tilt in μm (enter for 15)")
                sigma = float(answer) if answer else sigma
                answer = ask("Exclude columns steeper than (deg, enter for 60)")
                max_incl = float(answer) if answer else max_incl
            print(Fore.MAGENTA + Style.NORMAL + "Calculating crack thickness..")
            res = ct.continuous_columns(mask, voxel_size, "longest", tilt, sigma, max_incl)
        else:
            binsize = float(ask("Set binsize for crack thickness calculation in mm "
                                "(start with 0.01 and adjust for higher or lower resolution)"))
            print(Fore.MAGENTA + Style.NORMAL + "Calculating crack thickness..")
            res = ct.binned_maxmin(mask, voxel_size, binsize)

        fig = plot_result(res, voxel_size)
        print("\n")
        for line in ct.summary_text(res, voxel_size).splitlines():
            print(Fore.MAGENTA + Style.NORMAL + line)

        print("\n")
        if ask("Do you want to save the figure? (y/n)") == "y":
            save_path = ask("Enter save path:")
            fig.savefig(os.path.join(save_path, "thickness.pdf"), dpi=150)

        if ask("Do you want to try another method or binsize? (y/n)") == "n":
            print(Fore.MAGENTA + Style.NORMAL + "Analysis complete")
            break


if __name__ == "__main__":
    main()
