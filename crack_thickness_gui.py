# -*- coding: utf-8 -*-
"""
GUI for finding crack thickness from segmented images.

Choose between the binned max-min method and the continuous-column method
(longest unbroken run per column, corrected for crack tilt). See
crack_thickness.py for the calculations.

@author: bhejazi
"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import crack_thickness as ct

METHODS = {"maxmin": "Binned max-min", "continuous": "Continuous columns (tilt-corrected)"}


class CrackThicknessApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Crack thickness")
        self.geometry("1400x850")
        self.images = None
        self.result = None
        self._busy = False

        self.path = tk.StringVar()
        self.voxel = tk.StringVar()
        self.crack_val = tk.StringVar()
        self.remove_z = tk.BooleanVar(value=False)
        self.zthresh = tk.StringVar(value="0.1")
        self.method = tk.StringVar(value="continuous")
        self.binsize = tk.StringVar(value="0.01")
        self.measure = tk.StringVar(value="longest")
        self.tilt = tk.BooleanVar(value=True)
        self.sigma = tk.StringVar(value="15")
        self.max_incl = tk.StringVar(value="60")
        self.status = tk.StringVar(value="Select an image folder.")

        self._build_controls()
        self._build_plot()
        self._update_method_options()

    # ------------------------------------------------------------ layout
    def _build_controls(self):
        side = ttk.Frame(self, padding=8)
        side.pack(side=tk.LEFT, fill=tk.Y)
        pad = dict(padx=4, pady=2)

        f = ttk.LabelFrame(side, text="Input", padding=6)
        f.pack(fill=tk.X, **pad)
        ttk.Entry(f, textvariable=self.path, width=34).grid(row=0, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(f, text="Browse...", command=self.browse).grid(row=0, column=2, **pad)
        ttk.Label(f, text="Voxel size (μm)").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.voxel, width=10).grid(row=1, column=1, sticky="w", **pad)
        self.load_btn = ttk.Button(f, text="Load images", command=self.load)
        self.load_btn.grid(row=1, column=2, **pad)
        ttk.Label(f, text="Crack pixel value").grid(row=2, column=0, sticky="w", **pad)
        self.val_box = ttk.Combobox(f, textvariable=self.crack_val, width=8, state="readonly")
        self.val_box.grid(row=2, column=1, sticky="w", **pad)
        self.val_box.bind("<<ComboboxSelected>>", lambda e: self.show_preview())
        self.counts_lbl = ttk.Label(f, text="", foreground="gray", wraplength=300, justify="left")
        self.counts_lbl.grid(row=3, column=0, columnspan=3, sticky="w", **pad)

        f = ttk.LabelFrame(side, text="Z outlier removal", padding=6)
        f.pack(fill=tk.X, **pad)
        ttk.Checkbutton(f, text="Remove points with |z - median| > threshold", variable=self.remove_z,
                        command=self.show_preview).grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(f, text="Threshold (mm)").grid(row=1, column=0, sticky="w", **pad)
        e = ttk.Entry(f, textvariable=self.zthresh, width=10)
        e.grid(row=1, column=1, sticky="w", **pad)
        e.bind("<Return>", lambda ev: self.show_preview())

        f = ttk.LabelFrame(side, text="Thickness method", padding=6)
        f.pack(fill=tk.X, **pad)
        for i, (key, label) in enumerate(METHODS.items()):
            ttk.Radiobutton(f, text=label, value=key, variable=self.method,
                            command=self._update_method_options).grid(row=i, column=0, sticky="w", **pad)

        self.mm_frame = ttk.LabelFrame(side, text="Binned max-min options", padding=6)
        self.mm_frame.pack(fill=tk.X, **pad)
        ttk.Label(self.mm_frame, text="Bin size (mm)").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(self.mm_frame, textvariable=self.binsize, width=10).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(self.mm_frame, text="Thickness = max(z) - min(z) per bin;\nbins > 5x mean are discarded.",
                  foreground="gray").grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        self.cc_frame = ttk.LabelFrame(side, text="Continuous-column options", padding=6)
        self.cc_frame.pack(fill=tk.X, **pad)
        ttk.Radiobutton(self.cc_frame, text="Longest unbroken run per column", value="longest",
                        variable=self.measure).grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(self.cc_frame, text="Total crack voxels per column", value="count",
                        variable=self.measure).grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(self.cc_frame, text="Correct for crack tilt (t × cos φ)", variable=self.tilt,
                        command=self._update_method_options).grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(self.cc_frame, text="Surface smoothing σ (μm)").grid(row=3, column=0, sticky="w", **pad)
        self.sigma_entry = ttk.Entry(self.cc_frame, textvariable=self.sigma, width=10)
        self.sigma_entry.grid(row=3, column=1, sticky="w", **pad)
        ttk.Label(self.cc_frame, text="Max inclination (deg)").grid(row=4, column=0, sticky="w", **pad)
        self.incl_entry = ttk.Entry(self.cc_frame, textvariable=self.max_incl, width=10)
        self.incl_entry.grid(row=4, column=1, sticky="w", **pad)

        f = ttk.Frame(side)
        f.pack(fill=tk.X, pady=6)
        self.run_btn = ttk.Button(f, text="Calculate thickness", command=self.run)
        self.run_btn.pack(fill=tk.X, **pad)
        ttk.Button(f, text="Save figure...", command=self.save_figure).pack(fill=tk.X, **pad)
        ttk.Button(f, text="Export thickness map (CSV)...", command=self.export_map).pack(fill=tk.X, **pad)

        f = ttk.LabelFrame(side, text="Results", padding=6)
        f.pack(fill=tk.BOTH, expand=True, **pad)
        self.results = tk.Text(f, width=46, height=12, wrap="word", font=("Consolas", 9))
        self.results.pack(fill=tk.BOTH, expand=True)

        ttk.Label(side, textvariable=self.status, foreground="navy", wraplength=320).pack(fill=tk.X, **pad)

    def _build_plot(self):
        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        NavigationToolbar2Tk(self.canvas, right).update()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _update_method_options(self):
        def set_state(frame, enabled):
            for w in frame.winfo_children():
                try:
                    w.configure(state="normal" if enabled else "disabled")
                except tk.TclError:
                    pass
        maxmin = self.method.get() == "maxmin"
        set_state(self.mm_frame, maxmin)
        set_state(self.cc_frame, not maxmin)
        if not maxmin and not self.tilt.get():
            self.sigma_entry.configure(state="disabled")
            self.incl_entry.configure(state="disabled")

    # ------------------------------------------------------------ helpers
    def _float(self, var, name, positive=True):
        try:
            v = float(var.get())
        except ValueError:
            raise ValueError(f"{name} must be a number.")
        if positive and v <= 0:
            raise ValueError(f"{name} must be positive.")
        return v

    def _in_background(self, work, done, message):
        """Run work() in a thread, then done(result) in the GUI thread."""
        if self._busy:
            return
        self._busy = True
        self.status.set(message)
        self.config(cursor="watch")
        self.run_btn.configure(state="disabled")
        self.load_btn.configure(state="disabled")
        box = {}

        def target():
            try:
                box["result"] = work()
            except Exception as exc:  # reported in the GUI
                box["error"] = exc

        def poll():
            if thread.is_alive():
                self.after(100, poll)
                return
            self._busy = False
            self.config(cursor="")
            self.run_btn.configure(state="normal")
            self.load_btn.configure(state="normal")
            if "error" in box:
                self.status.set("Error.")
                messagebox.showerror("Error", str(box["error"]))
            else:
                done(box["result"])

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        poll()

    def _mask(self):
        vox = self._float(self.voxel, "Voxel size")
        if self.images is None:
            raise ValueError("Load images first.")
        if self.crack_val.get() == "":
            raise ValueError("Select the crack pixel value.")
        val = self.images.dtype.type(float(self.crack_val.get()))
        zt = self._float(self.zthresh, "Z threshold") if self.remove_z.get() else None
        return ct.crack_mask(self.images, val, zt, vox), vox

    # ------------------------------------------------------------ actions
    def browse(self):
        path = filedialog.askdirectory(title="Select folder with segmented .tif images")
        if path:
            self.path.set(path)
            vox = ct.voxel_size_from_tags(path)
            if vox is not None:
                self.voxel.set(f"{vox:.4g}")
                self.status.set(f"Voxel size {vox:.4g} μm read from TIFF tags (check before use).")

    def load(self):
        path = self.path.get()
        if not os.path.isdir(path):
            messagebox.showerror("Error", "Path does not exist, select a valid folder.")
            return
        if not self.voxel.get():
            vox = ct.voxel_size_from_tags(path)
            if vox is not None:
                self.voxel.set(f"{vox:.4g}")

        def work():
            images = ct.load_images(path)
            return images, ct.pixel_value_counts(images)

        def done(res):
            self.images, (vals, counts) = res
            self.result = None
            self.val_box["values"] = [str(v) for v in vals]
            nonzero = [i for i, v in enumerate(vals) if v != 0]
            default = max(nonzero, key=lambda i: counts[i]) if nonzero else 0
            self.crack_val.set(str(vals[default]))
            self.counts_lbl.configure(text="Pixel counts: " + ", ".join(
                f"{v}: {c}" for v, c in list(zip(vals, counts))[:12]) + (" ..." if len(vals) > 12 else ""))
            self.status.set(f"Loaded {self.images.shape[0]} slices of "
                            f"{self.images.shape[1]} x {self.images.shape[2]} px.")
            self.show_preview()

        self._in_background(work, done, "Loading images...")

    def show_preview(self):
        if self.images is None:
            return
        try:
            mask, vox = self._mask()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.fig.clf()
        ax1, ax2 = self.fig.subplots(1, 2, gridspec_kw=dict(width_ratios=[3, 1]))
        nz, ny, nx = self.images.shape
        ext = [0, nx * vox / ct.MM2UM, ny * vox / ct.MM2UM, 0]
        im = ax1.imshow(self.images[nz // 2], interpolation="none", extent=ext)
        vals = np.unique(self.images[nz // 2])
        cb = self.fig.colorbar(im, ax=ax1, shrink=0.8)
        if vals.size <= 10:
            cb.set_ticks(vals)
        ax1.set(title="Pixel values of mid slice", xlabel="x (mm)", ylabel="y (mm)")
        z_counts = mask.sum((1, 2))
        z_mm = np.arange(nz) * vox / ct.MM2UM
        ax2.barh(z_mm, z_counts, height=vox / ct.MM2UM, color="tab:blue")
        if z_counts.sum():
            z_med = np.median(np.repeat(z_mm, z_counts))
            ax2.axhline(z_med, color="k", lw=0.8, ls="--")
            ax2.set_title(f"z spread of crack\nmedian {z_med:.3f} mm", fontsize=10)
        ax2.set(xlabel="crack voxels", ylabel="z (mm)")
        self.fig.tight_layout()
        self.canvas.draw()

    def run(self):
        try:
            mask, vox = self._mask()
            method = self.method.get()
            if method == "maxmin":
                binsize = self._float(self.binsize, "Bin size")
                work = lambda: ct.binned_maxmin(mask, vox, binsize)
            else:
                measure, tilt = self.measure.get(), self.tilt.get()
                sigma = self._float(self.sigma, "Smoothing sigma") if tilt else 15.0
                max_incl = self._float(self.max_incl, "Max inclination") if tilt else 90.0
                work = lambda: ct.continuous_columns(mask, vox, measure, tilt, sigma, max_incl)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        if not mask.any():
            messagebox.showerror("Error", "No crack voxels with the selected pixel value.")
            return

        def done(res):
            self.result = res
            self.result["voxel_size"] = vox
            self.results.delete("1.0", tk.END)
            self.results.insert(tk.END, ct.summary_text(res, vox))
            self.show_result()
            self.status.set("Analysis complete.")

        self._in_background(work, done, "Calculating crack thickness...")

    def show_result(self):
        res = self.result
        px = res["pixel_mm"]
        ny, nx = res["thickness"].shape
        ext = [0, nx * px, ny * px, 0]
        self.fig.clf()
        ax = self.fig.subplots(2, 2).ravel()

        def show(a, data, title, label, **kw):
            im = a.imshow(data, interpolation="none", extent=ext, **kw)
            a.set(title=title, xlabel="x (mm)", ylabel="y (mm)")
            self.fig.colorbar(im, ax=a, label=label)

        show(ax[0], res["height"], "Mean relative height of crack", "z (mm)")
        t = res["thickness"]
        vmax = np.nanpercentile(t, 99) if np.isfinite(t).any() else None
        if res["method"] == "maxmin":
            show(ax[1], res["thickness_raw"], "Thickness before removing\nmisidentified bins", "μm")
            show(ax[2], t, "Thickness after removing\nmisidentified bins", "μm", vmin=0, vmax=vmax)
        else:
            show(ax[1], res["inclination_deg"], "Local crack inclination φ", "deg", vmin=0, vmax=90)
            title = "Thickness, " + ("longest run" if self.measure.get() == "longest" else "total count")
            title += ", tilt-corrected" if self.tilt.get() else ", along z"
            show(ax[2], t, title, "μm", vmin=0, vmax=vmax)
        # thickness values are (close to) voxel-quantised: centre histogram bins on voxels
        vox = res["voxel_size"]
        hi = np.nanmax(t) if np.isfinite(t).any() else vox
        bins = np.arange(-0.5, np.ceil(hi / vox) + 1.5) * vox
        v = t[np.isfinite(t)]
        ax[3].hist(v, bins=bins, color="tab:blue", alpha=0.8)
        ax[3].axvline(res["stats"]["mean"], color="k", ls="--", lw=1,
                      label=f"mean {res['stats']['mean']:.2f} μm")
        ax[3].set(title="Thickness distribution", xlabel="thickness (μm)", ylabel="count")
        if vmax is not None:
            ax[3].set_xlim(0, vmax * 1.2)
        ax[3].legend()
        self.fig.suptitle(METHODS[res["method"]])
        self.fig.tight_layout()
        self.canvas.draw()

    def save_figure(self):
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="thickness.pdf",
                                            filetypes=[("PDF", "*.pdf"), ("PNG", "*.png"), ("SVG", "*.svg")])
        if path:
            self.fig.savefig(path, dpi=150)
            self.status.set(f"Figure saved to {path}")

    def export_map(self):
        if self.result is None:
            messagebox.showinfo("Export", "Calculate the thickness first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="thickness_map.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        res = self.result
        header = (f"crack thickness map (um), {METHODS[res['method']]}, "
                  f"pixel size {res['pixel_mm']:g} mm, rows = y, columns = x, NaN = no crack/excluded")
        np.savetxt(path, res["thickness"], delimiter=",", fmt="%.4g", header=header)
        with open(os.path.splitext(path)[0] + "_summary.txt", "w", encoding="utf-8") as f:
            f.write(f"Image folder: {self.path.get()}\nVoxel size: {res['voxel_size']} um\n"
                    f"Crack pixel value: {self.crack_val.get()}\n"
                    f"Z outlier removal: {self.zthresh.get() + ' mm' if self.remove_z.get() else 'off'}\n")
            if res["method"] == "continuous":
                f.write(f"Measure: {self.measure.get()}\nTilt correction: {self.tilt.get()}\n")
                if self.tilt.get():
                    f.write(f"Smoothing sigma: {self.sigma.get()} um\n"
                            f"Max inclination: {self.max_incl.get()} deg\n")
            f.write("\n" + ct.summary_text(res, res["voxel_size"]) + "\n")
        self.status.set(f"Thickness map exported to {path}")


if __name__ == "__main__":
    CrackThicknessApp().mainloop()
