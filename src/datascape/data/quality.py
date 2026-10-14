"""Measured GeoTIFF quality checks and previews; no stroke or machine output."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from scipy.ndimage import binary_erosion, binary_fill_holes

SEASONS = ("SPRING", "SUMMER", "AUTUMN", "WINTER")
MASTER_BANDS = ("DEM", "SLOPE", "ASPECT", "HILLSHADE", "DEM_NASA") + tuple(
    f"NDVI_{s}" for s in SEASONS
) + tuple(f"N_{s}" for s in SEASONS)
VEG_BANDS = tuple(f"NDVI_{s}" for s in SEASONS) + tuple(f"N_{s}" for s in SEASONS)


def sha256_file(path: str | Path) -> str:
    """Hash a file without loading it all into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_valid_band(dataset, index: int) -> np.ma.MaskedArray:
    """Mask declared NoData, GDAL mask values, NaN, and infinity together.

    Valid negative elevations/NDVI are retained. A metadata NoData value alone
    is insufficient for exports that contain unmasked NaN pixels.
    """
    values = dataset.read(index, masked=True)
    return np.ma.masked_invalid(values, copy=False)


def summary(values: np.ndarray) -> dict:
    """Return exact full-array statistics for finite, valid observations."""
    data = np.asarray(values, dtype=np.float64).ravel()
    data = data[np.isfinite(data)]
    if not data.size:
        return {"count": 0}
    percentiles = np.percentile(data, [1, 2, 5, 50, 95, 98, 99])
    return {
        "count": int(data.size), "min": float(data.min()), "max": float(data.max()),
        "mean": float(data.mean()), "std": float(data.std()),
        **{f"p{p}": float(v) for p, v in zip([1, 2, 5, 50, 95, 98, 99], percentiles)},
    }


def inspect_raster(path: str | Path, expected_bands: tuple, resolution: int) -> dict:
    """Inspect every band at native resolution; report rather than hide errors."""
    path = Path(path)
    with rasterio.open(path) as ds:
        checks = {
            "crs": ds.crs == rasterio.crs.CRS.from_epsg(32652),
            "resolution": bool(np.allclose(ds.res, [resolution, resolution])),
            "north_up": ds.transform.b == 0 and ds.transform.d == 0 and ds.transform.e < 0,
            "band_names_and_order": ds.descriptions == expected_bands,
            "band_count": ds.count == len(expected_bands),
            "dtype": all(d == "float32" for d in ds.dtypes),
            "nodata_metadata": ds.nodata == -9999,
            "global_grid_anchor": bool(np.isclose(ds.transform.c / resolution, round(ds.transform.c / resolution), rtol=0, atol=1e-8)
                                       and np.isclose((5000000 - ds.transform.f) / resolution,
                                                      round((5000000 - ds.transform.f) / resolution), rtol=0, atol=1e-8)),
        }
        first_mask = None
        bands = []
        for index in ds.indexes:
            raw = ds.read(index)
            gdal_valid = ds.read_masks(index) > 0
            finite = np.isfinite(raw)
            data = read_valid_band(ds, index)
            valid = ~np.ma.getmaskarray(data)
            if first_mask is None:
                first_mask = valid.copy()
            name = ds.descriptions[index - 1] or f"band_{index}"
            vals = raw[valid]
            ranges = None
            if name.startswith("NDVI_"): ranges = (-1, 1)
            elif name == "SLOPE": ranges = (0, 90)
            elif name == "ASPECT": ranges = (0, 360)
            elif name == "HILLSHADE": ranges = (0, 255)
            elif name.startswith("N_"): ranges = (0, float("inf"))
            entry = {
                "index": index, "name": name, "statistics": summary(vals),
                "valid_percent": float(valid.mean() * 100),
                "invalid_percent": float((~valid).mean() * 100),
                "declared_nodata_pixels": int((raw == ds.nodata).sum()) if ds.nodata is not None else 0,
                "gdal_masked_pixels": int((~gdal_valid).sum()),
                "nan_pixels": int(np.isnan(raw).sum()), "infinity_pixels": int(np.isinf(raw).sum()),
                "unmasked_nonfinite_pixels": int((~finite & gdal_valid).sum()),
                "interior_invalid_pixels": int((binary_fill_holes(valid) & ~valid).sum()),
                "mask_disagreement_with_first_band": int((valid != first_mask).sum()),
                "range_violation_pixels": int(((vals < ranges[0]) | (vals > ranges[1])).sum()) if ranges else None,
            }
            if name.startswith("N_"):
                entry["fractional_count_pixels"] = int((np.abs(vals - np.rint(vals)) > 1e-5).sum())
                entry["zero_count_pixels"] = int((vals == 0).sum())
                entry["count_below_10_pixels"] = int((vals < 10).sum())
            bands.append(entry)
        return {
            "filename": path.name, "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path), "crs": str(ds.crs),
            "resolution_m": list(ds.res), "bounds": list(ds.bounds),
            "width": ds.width, "height": ds.height, "band_count": ds.count,
            "transform": list(ds.transform)[:6], "dtype": list(ds.dtypes),
            "nodata_metadata": ds.nodata, "band_descriptions": list(ds.descriptions),
            "checks": checks, "bands": bands,
        }


def grid_alignment(master, vegetation) -> dict:
    """Check nested north-up grids, not equality of raster array extents."""
    mt, vt = master.transform, vegetation.transform
    north_up = all(t.b == 0 and t.d == 0 and t.a > 0 and t.e < 0 for t in [mt, vt])
    ratios = np.asarray(master.res) / np.asarray(vegetation.res)
    offsets = np.array([(mt.c - vt.c) / vt.a, (mt.f - vt.f) / abs(vt.e)])
    crs_match = master.crs == vegetation.crs
    nested = north_up and crs_match and np.allclose(ratios, np.rint(ratios), rtol=0, atol=1e-8) and np.allclose(offsets, np.rint(offsets), rtol=0, atol=1e-8)
    intersection = [max(master.bounds.left, vegetation.bounds.left),
                    max(master.bounds.bottom, vegetation.bounds.bottom),
                    min(master.bounds.right, vegetation.bounds.right),
                    min(master.bounds.top, vegetation.bounds.top)]
    return {
        "same_crs": crs_match, "north_up": north_up,
        "pixel_size_ratio": ratios.tolist(), "origin_offset_in_10m_pixels": offsets.tolist(),
        "nested_grid_boundaries": bool(nested), "same_bounds": master.bounds == vegetation.bounds,
        "intersection_bounds": intersection,
        "note": "Use georeferenced aggregation; differently cropped bounds prevent direct 3x3 array grouping.",
    }


def average_on_grid(source, index: int, target) -> np.ma.MaskedArray:
    """Area-average valid source pixels onto a target grid, ignoring NaN."""
    source_data = read_valid_band(source, index).filled(-9999)
    result = np.full(target.shape, -9999, dtype=np.float32)
    reproject(source_data, result, src_transform=source.transform, src_crs=source.crs,
              src_nodata=-9999, dst_transform=target.transform, dst_crs=target.crs,
              dst_nodata=-9999, resampling=Resampling.average)
    return np.ma.masked_invalid(np.ma.masked_equal(result, -9999), copy=False)


def paired_metrics(left, right) -> dict:
    """Compare jointly valid finite pixels; never substitute zero for missing data."""
    mask = np.ma.getmaskarray(left) | np.ma.getmaskarray(right)
    a, b = left.data[~mask].astype(np.float64), right.data[~mask].astype(np.float64)
    if not a.size:
        return {"count": 0}
    delta = a - b
    return {
        **summary(delta), "mae": float(np.abs(delta).mean()),
        "rmse": float(np.sqrt(np.mean(delta ** 2))),
        "correlation": float(np.corrcoef(a, b)[0, 1]) if a.size > 1 and a.std() and b.std() else None,
        "absolute_difference_above_20_percent": float((np.abs(delta) > 20).mean() * 100),
        "absolute_difference_above_50_percent": float((np.abs(delta) > 50).mean() * 100),
    }


def _map(ax, data, bounds, title, cmap, vmin, vmax):
    ax.set_facecolor("#ebe9e3")
    extent = [bounds.left / 1000, bounds.right / 1000, bounds.bottom / 1000, bounds.top / 1000]
    artist = ax.imshow(data, extent=extent, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax,
                       interpolation="nearest", rasterized=True)
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_xlabel("Easting (km)", fontsize=9)
    ax.set_ylabel("Northing (km)", fontsize=9)
    ax.tick_params(labelsize=8)
    return artist


def make_previews(master, vegetation, output: Path) -> list[str]:
    """Save north-up measured data maps with shared seasonal color scales."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "#faf9f5"})
    cop, nasa, hill = (read_valid_band(master, i) for i in [1, 5, 4])
    difference = cop - nasa
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), layout="constrained")
    fig.suptitle("Seoul North | Terrain quality overview", fontsize=18, fontweight="bold")
    for ax, data, title, cmap, lo, hi, unit in [
        (axes[0,0],cop,"Copernicus surface elevation","terrain",0,820,"m (EGM2008)"),
        (axes[0,1],nasa,"NASADEM elevation","terrain",0,820,"m (EGM96)"),
        (axes[1,0],hill,"Exported hillshade","gray",0,255,"shade value"),
        (axes[1,1],difference,"Copernicus minus NASADEM","RdBu_r",-30,30,"m; display clipped at +/-30"),
    ]:
        artist = _map(ax,data,master.bounds,title,cmap,lo,hi)
        fig.colorbar(artist,ax=ax,shrink=0.8,label=unit)
    fig.savefig(output/"terrain_overview.png",dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(2, 4, figsize=(18, 9), layout="constrained")
    fig.suptitle("Seoul North | Seasonal vegetation and valid observations",fontsize=19,fontweight="bold")
    for i,season in enumerate(SEASONS):
        # Read only display-sized bands. Full-resolution statistics are separate.
        shape=(vegetation.height//3,vegetation.width//3)
        ndvi=np.ma.masked_invalid(vegetation.read(i+1,out_shape=shape,masked=True,resampling=Resampling.nearest))
        counts=np.ma.masked_invalid(vegetation.read(i+5,out_shape=shape,masked=True,resampling=Resampling.nearest))
        n=_map(axes[0,i],ndvi,vegetation.bounds,season.title(),"RdYlGn",-0.4,0.9)
        c=_map(axes[1,i],counts,vegetation.bounds,season.title()+" observations","viridis",0,90)
    fig.colorbar(n,ax=axes[0,:].tolist(),shrink=0.7,label="NDVI (shared scale)")
    fig.colorbar(c,ax=axes[1,:].tolist(),shrink=0.7,label="Valid scenes per 10 m pixel (2022-2025)")
    fig.savefig(output/"seasonal_vegetation.png",dpi=135)
    plt.close(fig)

    fig,axes=plt.subplots(1,3,figsize=(17,5),layout="constrained")
    fig.suptitle("Seoul North | Masks and aggregation checks",fontsize=18,fontweight="bold")
    raw=master.read(1);gd=master.read_masks(1)>0
    classes=np.zeros(master.shape,dtype=np.uint8)
    classes[~gd]=1;classes[gd&~np.isfinite(raw)]=2
    cm=ListedColormap(["#496850","#bac1c6","#e49b40"])
    ar=_map(axes[0],classes,master.bounds,"MASTER: valid / declared missing / NaN",cm,0,2)
    bar=fig.colorbar(ar,ax=axes[0],ticks=[0,1,2],shrink=0.8)
    bar.ax.set_yticklabels(["valid","NoData/mask","unmasked NaN"])
    vals=difference.compressed()
    axes[1].hist(vals,bins=120,range=(-40,40),color="#456c91")
    axes[1].axvline(0,color="#222",lw=0.8)
    axes[1].set(title="DEM differences (histogram: +/-40 m)",xlabel="Copernicus minus NASADEM (m)",ylabel="Valid pixels")
    ndvi_delta=read_valid_band(master,7)-average_on_grid(vegetation,2,master)
    ar=_map(axes[2],ndvi_delta,master.bounds,"Summer: MASTER minus 10 m area mean","RdBu_r",-0.03,0.03)
    fig.colorbar(ar,ax=axes[2],shrink=0.8,label="NDVI difference (display +/-0.03)")
    fig.savefig(output/"grid_diagnostics.png",dpi=150)
    plt.close(fig)
    return ["terrain_overview.png","seasonal_vegetation.png","grid_diagnostics.png"]


def validate_pair(master_path, vegetation_path, output_dir, base_revision=None) -> dict:
    """Write a deterministic analysis and figures without modifying input rasters.

    Pixel statistics use full native arrays, one band at a time. Preview maps
    may use nearest-neighbor display samples. No randomness is used.
    """
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    master_path,vegetation_path=Path(master_path),Path(vegetation_path)
    if output.resolve() in {master_path.resolve(),vegetation_path.resolve()}:
        raise ValueError("Output must be a directory separate from the inputs.")
    m=inspect_raster(master_path,MASTER_BANDS,30)
    v=inspect_raster(vegetation_path,VEG_BANDS,10)
    if not all(m["checks"].values()) or not all(v["checks"].values()):
        raise ValueError("Input metadata does not match the Seoul North v0.2 specification.")
    with rasterio.open(master_path) as master,rasterio.open(vegetation_path) as vegetation:
        alignment=grid_alignment(master,vegetation)
        if not alignment["nested_grid_boundaries"]:
            raise ValueError("Input grids are not aligned north-up nested grids.")
        aggregation={}
        for i,season in enumerate(SEASONS):
            ndvi_master=read_valid_band(master,i+6)
            ndvi_average=average_on_grid(vegetation,i+1,master)
            count_master=read_valid_band(master,i+10)
            count_average=average_on_grid(vegetation,i+5,master)
            joint_valid=~(np.ma.getmaskarray(ndvi_master)|np.ma.getmaskarray(ndvi_average))
            # GEE aggregates before ROI clipping; exported 10 m edge pixels
            # cannot reconstruct contributions from outside the clipped ROI.
            interior=binary_erosion(joint_valid,iterations=1)
            aggregation[season.lower()]={
                "ndvi":paired_metrics(ndvi_master,ndvi_average),
                "count":paired_metrics(count_master,count_average),
                "ndvi_interior":paired_metrics(np.ma.array(ndvi_master,mask=~interior),np.ma.array(ndvi_average,mask=~interior)),
                "count_interior":paired_metrics(np.ma.array(count_master,mask=~interior),np.ma.array(count_average,mask=~interior)),
                "interior_definition":"One 30 m pixel eroded from the jointly valid footprint",
            }
        dem=paired_metrics(read_valid_band(master,1),read_valid_band(master,5))
        dem["definition"]="Copernicus minus NASADEM; raw source vertical datums, not an accuracy estimate"
        images=make_previews(master,vegetation,output)
    warnings=[]
    for r in [m,v]:
        if any(b["unmasked_nonfinite_pixels"] for b in r["bands"]):
            warnings.append(r["filename"]+": unmasked NaN/Inf requires an explicit finite-value mask.")
        if any(b["range_violation_pixels"] for b in r["bands"]):
            warnings.append(r["filename"]+": band range violations found.")
        if any(b["interior_invalid_pixels"] for b in r["bands"]):
            warnings.append(r["filename"]+": enclosed internal data gaps found.")
    needs_review=any(b["range_violation_pixels"] or b["interior_invalid_pixels"]
                     for raster in [m,v] for b in raster["bands"])
    report={
        "schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),
        "status":"needs_review" if needs_review else "usable_for_exploration_with_explicit_finite_mask",
        "repository_base_revision":base_revision,"module_sha256":sha256_file(__file__),
        "environment":{"python":platform.python_version(),"numpy":np.__version__,"rasterio":rasterio.__version__,"gdal":rasterio.__gdal_version__},
        "settings":{"statistics":"full native resolution","random_seed":None,"randomness":"none","aggregation":"rasterio area-weighted average","dem_difference_correction":"none","difference_preview_limits_m":[-30,30]},
        "master":m,"vegetation":v,"alignment":alignment,
        "dem_difference":dem,"aggregation_checks":aggregation,"warnings":warnings,
        "images":images,
    }
    # A second hash catches accidental input rewrites during this run.
    report["input_hashes_unchanged"]=sha256_file(master_path)==m["sha256"] and sha256_file(vegetation_path)==v["sha256"]
    if not report["input_hashes_unchanged"]:
        raise RuntimeError("Input raster bytes changed during validation.")
    (output/"quality_report.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master",required=True,type=Path)
    parser.add_argument("--vegetation",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--base-revision",default=None)
    args=parser.parse_args()
    report=validate_pair(args.master,args.vegetation,args.output,args.base_revision)
    print(json.dumps({"status":report["status"],"warnings":report["warnings"],"output":str(args.output)},indent=2))


if __name__ == "__main__":
    main()
