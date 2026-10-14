"""DEM-based ROI screening; no rock exposure or urban land-use inference."""
from dataclasses import dataclass
import numpy as np
import rasterio
from rasterio.windows import from_bounds, bounds as window_bounds
from scipy.ndimage import gaussian_filter
from datascape.data.quality import read_valid_band


@dataclass
class TerrainGrid:
    elevation_m: np.ndarray
    valid: np.ndarray
    x_m: np.ndarray
    y_m: np.ndarray
    bounds_m: tuple
    native_resolution_m: tuple


def load_grid(dataset, bounds_m):
    """Read a grid-aligned ROI with the existing finite-value mask helper."""
    window=from_bounds(*bounds_m,transform=dataset.transform).round_offsets().round_lengths()
    if window.col_off<0 or window.row_off<0 or window.col_off+window.width>dataset.width or window.row_off+window.height>dataset.height:
        raise ValueError("ROI lies outside the input raster.")
    row,col=window.toslices()
    z=read_valid_band(dataset,1)[row,col].copy()
    transform=dataset.window_transform(window)
    yy,xx=np.mgrid[:z.shape[0],:z.shape[1]]
    x=transform.c+(xx+0.5)*transform.a
    y=transform.f+(yy+0.5)*transform.e
    return TerrainGrid(z.data.copy(),~np.ma.getmaskarray(z),x,y,
                       window_bounds(window,dataset.transform),dataset.res)


def roi_metrics(z,slope,tpi):
    """Describe relief and steep/low/high fractions, not pictorial quality."""
    valid=np.isfinite(z)&np.isfinite(slope)&np.isfinite(tpi)
    a=z[valid];s=slope[valid];t=tpi[valid]
    if not a.size:raise ValueError("ROI has no finite terrain.")
    return {"valid_fraction":float(valid.mean()),"elevation_min_m":float(a.min()),
            "elevation_max_m":float(a.max()),"elevation_median_m":float(np.median(a)),
            "p95_p05_relief_m":float(np.percentile(a,95)-np.percentile(a,5)),
            "slope_ge_25_fraction":float((s>=25).mean()),
            "elevation_lt_100_fraction":float((a<100).mean()),
            "elevation_gt_300_fraction":float((a>300).mean()),
            "local_residual_std_m":float(t.std())}


def scan_rois(dataset, spans_m=(4800,7200,6000), step_pixels=30, keep_per_type=5):
    """Screen square windows with transparent, deterministic heuristics.

    A: steep fraction * relief. B: local residual roughness * relief / 100.
    C: sqrt(low fraction * high fraction) * relief. TPI-like residual uses a
    mask-aware 360 m Gaussian scale for ranking only, never for rendering.
    Scores are not comparable between types or proof of overlapping ridges.
    """
    z=read_valid_band(dataset,1).filled(np.nan)
    slope=read_valid_band(dataset,2).filled(np.nan)
    valid=np.isfinite(z)
    smooth=gaussian_filter(np.where(valid,z,0),12)/np.maximum(gaussian_filter(valid.astype(float),12),1e-6)
    tpi=z-smooth;result={}
    for kind,span in zip("ABC",spans_m):
        n=int(round(span/dataset.res[0]));half=n//2;rows=[]
        for y in range(half+1,dataset.height-half-1,step_pixels):
            for x in range(half+1,dataset.width-half-1,step_pixels):
                ys=slice(y-half,y+half);xs=slice(x-half,x+half)
                metrics=roi_metrics(z[ys,xs],slope[ys,xs],tpi[ys,xs])
                if metrics["valid_fraction"]<.995:continue
                relief=metrics["p95_p05_relief_m"]
                if kind=="A":score=metrics["slope_ge_25_fraction"]*relief
                elif kind=="B":score=metrics["local_residual_std_m"]*relief/100
                else:score=np.sqrt(metrics["elevation_lt_100_fraction"]*metrics["elevation_gt_300_fraction"])*relief
                # Window centroid is a pixel corner, not the center of pixel (y,x).
                e,north=dataset.transform*(x,y)
                bounds=[e-span/2,north-span/2,e+span/2,north+span/2]
                rows.append({"type":kind,"center_utm_m":[e,north],"bounds_utm_m":bounds,"score":float(score),"metrics":metrics})
        rows.sort(key=lambda r:r["score"],reverse=True)
        chosen=[]
        for row in rows:
            if all(np.linalg.norm(np.array(row["center_utm_m"])-np.array(c["center_utm_m"]))>2500 for c in chosen):chosen.append(row)
            if len(chosen)==keep_per_type:break
        result[kind]=chosen
    return result
