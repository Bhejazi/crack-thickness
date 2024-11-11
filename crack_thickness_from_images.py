# -*- coding: utf-8 -*-
"""
Last updated on Mon Apr 26, 2024

@author: bhejazi

Finding crack thickness from segmented images
crack and other features in image should be labeled as integer values
images should also be in .tif format
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from colorama import Fore, Style

#%%
def load_images(path):
    folder_info = os.listdir(path)
    print(Fore.MAGENTA + Style.NORMAL + "Loading images..")
    
    file_idx = [i for i, file_name in enumerate(folder_info) if file_name[-3:] == "tif"]
    #file_idx = [i for i, file_name in enumerate(folder_info)]
    
    n_images = len(file_idx)
    temp_img = np.array(Image.open(os.path.join(path, folder_info[file_idx[0]])))
    rows, cols = temp_img.shape
    
    images = np.zeros((n_images, rows, cols), dtype=int)

    for i, idx in enumerate(file_idx):
        images[i, :, :] = np.array(Image.open(os.path.join(path, folder_info[idx])))
      
    return images

def data_from_images(images, crack_pix_val):
    
    crack_images = np.zeros_like(images, dtype=int)
    crack_x, crack_y, crack_z = [], [], []

    for i in np.arange(crack_images.shape[0]):        
        
        crack_images[i, :, :] = (images[i, :, :] == int(crack_pix_val)) # set segmented feature pixel value
        rows, cols = np.where(crack_images[i, :, :] == 1)
        crack_x.extend(cols)
        crack_y.extend(rows)
        crack_z.extend(np.ones(len(rows)) * (i + 1))
        pnts_crack = np.column_stack([crack_x, crack_y, crack_z]) * voxel_size / mm2um
      
    return pnts_crack

# Set file paths
#path_INP = input ("Enter image file path:  ")         
while True:
    print(Fore.MAGENTA + Style.BRIGHT + "\n" + "Enter image file path:" + Fore.BLUE + Style.BRIGHT)
    path = input ("-> ")
    print("\n")

    if os.path.exists(path): #check if path is valid
        break
    else:
        print (Fore.RED + Style.BRIGHT + "Path does not exist, re-enter correct path")
        
print(Fore.MAGENTA + Style.BRIGHT + "What is the voxel size? (in \u03BCm)" + Fore.BLUE + Style.BRIGHT)
voxel_size = float(input("-> "))
print("\n")

images = load_images(path)

print("\n")
print(Fore.MAGENTA + Style.NORMAL + "Calculating pixel values..")
print("\n")

#%%
mm2um = 1000
minx, maxx = 0, (np.shape(images)[2]-1) * (voxel_size / mm2um)
miny, maxy = 0, (np.shape(images)[1]-1) * (voxel_size / mm2um)

pixel_values = np.resize(images, (images.shape[0]*images.shape[1]*images.shape[2], 1))
bins_init = np.arange(np.min(pixel_values), np.max(pixel_values)+2, 1)
counts, bins = np.histogram(pixel_values, bins_init)

non_zero_pix_counts = np.where(counts!=0)

fig, ax = plt.subplots()
temp_img = ax.imshow(images[int(np.shape(images)[0]/2),:,:], interpolation='none', extent=[minx, maxx, miny, maxy])
ax.set_title('Pixel values of mid slice of crack image stack')
ax.set_xlabel("x (mm)", fontsize=15)
ax.set_ylabel("y (mm)", fontsize=15)

if np.shape(bins_init)[0] > 10:
    fig.colorbar(temp_img)
else:
    fig.colorbar(temp_img, ticks = bins_init)

plt.show()

for i in np.arange(np.size(non_zero_pix_counts[0])):
    print(Fore.MAGENTA + Style.BRIGHT + f"{counts[non_zero_pix_counts[0][i]]}" + Fore.MAGENTA + Style.NORMAL + " pixels with value" + Fore.MAGENTA + Style.BRIGHT + f" {bins[non_zero_pix_counts[0][i]]}")

# fig, ax = plt.subplots()
# ax.hist(pixel_values, log = True)
# ax.set_title("Pixel values in images")
# ax.set_xlabel("pixel  values")
# ax.set_ylabel("counts")
# plt.show()

print("\n")
# print(Fore.MAGENTA + Style.BRIGHT + "What is the crack pixel value? (check histogram)" + Fore.BLUE + Style.BRIGHT)
print(Fore.MAGENTA + Style.BRIGHT + "What is the crack pixel value? (check image and pixel counts)" + Fore.BLUE + Style.BRIGHT)
crack_pix_val = float(input("-> "))

print("\n")
print(Fore.MAGENTA + Style.NORMAL + "Calculating pixel coordinates..")

pnts_crack = data_from_images(images, crack_pix_val)   

#%%
# Eliminate some outliers
fig, ax = plt.subplots()
ax.violinplot(pnts_crack[:,2], showmedians = True)
ax.set_title(f"z spread of crack, median is {np.median(pnts_crack[:, 2])} mm")
ax.set_ylabel("z (mm)")
plt.show()

print("\n")
print(Fore.MAGENTA + Style.BRIGHT + "Do you want to remove outliers in z? (y/n)" + Fore.BLUE + Style.BRIGHT)
remove_outliers = input("-> ")
if remove_outliers == "y":
    print(Fore.MAGENTA + Style.BRIGHT + "Set threshold for z, removes points which are >(median val + threshold) & <(median val - threshold)" + Fore.BLUE + Style.BRIGHT)
    zthresh = float(input("-> "))
    
    crack_zpos = np.median(pnts_crack[:, 2])
    indx_crack = np.where((pnts_crack[:, 2] > crack_zpos + zthresh) | (pnts_crack[:, 2] < crack_zpos - zthresh))[0]

    pnts_crack = np.delete(pnts_crack, indx_crack, axis=0)

x_crack, y_crack, z_crack = pnts_crack[:, 0], pnts_crack[:, 1], pnts_crack[:, 2]

#%%

print("\n")
while True:
    print(Fore.MAGENTA + Style.BRIGHT + "Set binsize for crack thickness calculation (start with 0.01 and adjust for higher or lower resolution)" + Fore.BLUE + Style.BRIGHT)
    binsize = float(input("-> "))
    
    print("\n")
    print(Fore.MAGENTA + Style.NORMAL + "Calculating crack thickness..")
    
    # Calculate crack thickness
    #minx, maxx = np.min(x_crack), np.max(x_crack)
    minx -= minx % binsize
    maxx -= maxx % binsize - binsize

    xrange = np.abs(maxx - minx) + binsize
    
    #miny, maxy = np.min(y_crack), np.max(y_crack)
    miny -= miny % binsize
    maxy -= maxy % binsize - binsize

    yrange = np.abs(maxy - miny) + binsize

    xsize, ysize = int(xrange / binsize), int(yrange / binsize)

    mean_h = np.zeros((ysize + 1, xsize + 1))
    thickness = np.zeros((ysize + 1, xsize + 1))

    cnti = 0
    for i in np.arange(minx, maxx + binsize, binsize):
        cntj = 0
        for j in np.arange(miny, maxy + binsize, binsize):
            ind_crack = np.where((x_crack >= i) & (x_crack < i + binsize) & (y_crack >= j) & (y_crack < j + binsize))[0]
        
            if ind_crack.size > 0:
                thickness[cntj, cnti] = np.max(z_crack[ind_crack]) - np.min(z_crack[ind_crack])
                mean_h[cntj, cnti] = np.mean(z_crack[ind_crack])
            else:
                thickness[cntj, cnti] = 0
                mean_h[cntj, cnti] = 0

            cntj += 1
        cnti += 1

    # Plotting
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    im1 = axes[0].imshow(mean_h, interpolation='none', extent=[minx, maxx, miny, maxy])
    #axes[0].invert_yaxis()
    axes[0].set_title('Mean relative height of crack (mm)')
    axes[0].set_xlabel("x (mm)", fontsize=15)
    axes[0].set_ylabel("y (mm)", fontsize=15)
    fig.colorbar(im1, ax=axes[0])

    im2 = axes[1].imshow(thickness, interpolation='none', extent=[minx, maxx, miny, maxy])
    axes[1].set_title('Thickness before removing \n misidentified points (mm)')
    axes[1].set_xlabel("x (mm)", fontsize=15)
    axes[1].set_ylabel("y (mm)", fontsize=15)
    fig.colorbar(im2, ax=axes[1])

    non_zero_elements = np.where(thickness != 0)
    mean_thickness_before = np.mean(thickness[non_zero_elements])
    bad_sections = np.where(thickness > 5 * mean_thickness_before)
    thickness[bad_sections] = 0

    non_zero_elements = np.where(thickness != 0)
    mean_thickness_after = np.mean(thickness[non_zero_elements])

    im3 = axes[2].imshow(thickness, interpolation='none', extent=[minx, maxx, miny, maxy])
    #im3 = axes[2].imshow(thickness, vmin=0, vmax=0.1) # to set lower and upper bounds for the colorbars
    axes[2].set_title('Thickness after removing \n misidentified points (mm)')
    axes[2].set_xlabel("x (mm)", fontsize=15)
    axes[2].set_ylabel("y (mm)", fontsize=15)
    fig.colorbar(im3, ax=axes[2])
        
    plt.show()
          
    print("\n")
    print(Fore.MAGENTA + Style.NORMAL + "Mean crack thickness before removing misidentified points = " + Fore.MAGENTA + Style.BRIGHT + f"{mean_thickness_before}")
    print(Fore.MAGENTA + Style.NORMAL + "Mean crack thickness after removing misidentified points = " + Fore.MAGENTA + Style.BRIGHT + f"{mean_thickness_after}")
    
    print("\n")
    print(Fore.MAGENTA + Style.BRIGHT + "Do you want to save the figure? (y/n)" + Fore.BLUE + Style.BRIGHT)
    save_fig = input(Fore.BLUE + Style.BRIGHT + "-> ")
        
    if save_fig == "y":
        print("\n")
        print(Fore.MAGENTA + Style.BRIGHT + "Enter save path:" + Fore.BLUE + Style.BRIGHT)
        save_path = input(Fore.BLUE + Style.BRIGHT + "-> ")
        
        fig.savefig(save_path + "\\thickness.pdf", dpi = 150)
    
    print("\n")
    print(Fore.MAGENTA + Style.BRIGHT + "Do you want to try another binsize? (y/n)" + Fore.BLUE + Style.BRIGHT)
    try_again = input(Fore.BLUE + Style.BRIGHT + "-> ")
    print("\n")
    
    if try_again == "n":
        print(Fore.MAGENTA + Style.NORMAL + "Analysis complete")
        break
    
