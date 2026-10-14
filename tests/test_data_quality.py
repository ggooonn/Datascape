"""Checks for real masking and grid pitfalls in the Seoul North exports."""
import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from datascape.data.quality import average_on_grid, grid_alignment, paired_metrics, read_valid_band


def raster(values, transform):
    memory=MemoryFile()
    ds=memory.open(driver="GTiff",height=values.shape[0],width=values.shape[1],count=1,
                   dtype="float32",crs="EPSG:32652",transform=transform,nodata=-9999)
    ds.write(values.astype("float32"),1)
    return memory,ds


def test_mask_includes_nan_inf_and_nodata_but_keeps_negative_values():
    memory,ds=raster(np.array([[-32,-0.4,np.nan,np.inf,-9999,0]]),from_origin(0,30,10,10))
    with memory,ds:
        values=read_valid_band(ds,1)
        assert values.compressed().tolist()==pytest.approx([-32,-0.4,0])
        assert np.ma.getmaskarray(values).tolist()==[[False,False,True,True,True,False]]


@pytest.mark.parametrize("offset,expected",[(20,True),(15,False)])
def test_nested_grid_allows_cropped_bounds_but_rejects_half_pixel_offset(offset,expected):
    am,a=raster(np.ones((3,3)),from_origin(0,90,30,30))
    bm,b=raster(np.ones((7,9)),from_origin(0,90-offset,10,10))
    with am,a,bm,b:
        result=grid_alignment(a,b)
        assert result["nested_grid_boundaries"] is expected
        assert not result["same_bounds"]


def test_area_average_ignores_unmasked_nan_instead_of_poisoning_result():
    values=np.array([[np.nan,2,3],[4,5,6],[7,8,9]],dtype=np.float32)
    sm,s=raster(values,from_origin(0,30,10,10))
    tm,t=raster(np.ones((1,1)),from_origin(0,30,30,30))
    with sm,s,tm,t:
        result=average_on_grid(s,1,t)
        assert not result.mask.any()
        assert result[0,0]==pytest.approx(5.5)


def test_paired_metrics_use_joint_valid_pixels():
    a=np.ma.array([1,2,500],mask=[False,False,True])
    b=np.ma.array([0,100,0],mask=[False,True,False])
    result=paired_metrics(a,b)
    assert result["count"]==1
    assert result["mean"]==1
    assert result["rmse"]==1


def test_empty_comparison_is_explicit():
    values=np.ma.masked_all(4)
    assert paired_metrics(values,values)=={"count":0}
