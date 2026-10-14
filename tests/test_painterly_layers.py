"""Georeferencing, deterministic placement and ink omission contracts."""
import numpy as np
from rasterio.transform import from_origin
from datascape.composition.fields import mapped_source_coordinates,sample_finite
from datascape.vegetation.painterly import place_plants,combine_ink


def test_barycentric_source_recovery_uses_pixel_centers():
    terrain={'owners':np.array([[0,-1]]),'faces':np.array([[0,1,2]]),
             'pixel':np.array([[0,0],[2,0],[0,2]]),
             'xyz':np.array([[100,200,10],[120,200,30],[100,220,50]])}
    xyz,valid=mapped_source_coordinates(terrain)
    np.testing.assert_allclose(xyz[0,0],[105,205,25]);assert np.isnan(xyz[0,1]).all()
    assert valid.tolist()==[[True,False]]


def test_geographic_sampling_respects_20m_vertical_offset():
    # The same geographic point is row 1 in MASTER and row 1 in VEG only
    # accidentally here; arbitrary world coordinates must drive the sample.
    master=from_origin(0,100,30,30);veg=from_origin(0,80,10,10)
    values=np.arange(100).reshape(10,10).astype(float)
    x=np.array([[15.]]);y=np.array([[65.]])
    sampled,_=sample_finite(values,veg,x,y)
    assert sampled[0,0]==11
    assert ((100-65)/30-.5)!=((80-65)/10-.5)


def test_missing_finite_neighbors_are_rejected_not_zero_filled():
    values=np.array([[.4,np.nan],[.6,.8]])
    sampled,support=sample_finite(values,from_origin(0,2,1,1),np.array([[1.]]),np.array([[1.]]))
    assert np.isnan(sampled[0,0]);assert support[0,0]==.75


def test_whitespace_removes_ink_and_does_not_add_white_paint():
    shade=np.full((2,2),.4);plants=np.full((2,2),.8)
    f={'terrain_retention':np.array([[0,.5],[1,1]]),'vegetation_retention':np.array([[0,.2],[1,1]]),
       'reserve':np.array([[True,False],[False,False]])}
    images=combine_ink(shade,plants,plants,f)
    assert images['C'][0,0]==1
    assert images['terrain_ink_C'][0,0]==images['plant_ink_C'][0,0]==0
    np.testing.assert_array_equal(images['A'],shade)
    assert images['C'][0,1]>images['B'][0,1]


def test_seeded_B_C_keep_common_roots_and_geometry():
    h,w=90,60;yy,xx=np.mgrid[:h,:w]
    f={'vegetation_before':np.ones((h,w))*.1,'vegetation_retention':np.ones((h,w))*.5,
       'xyz':np.stack([xx+300000,yy+4000000,np.ones((h,w))*40],axis=2),
       'depth_m':np.ones((h,w))*400,'current_ndvi':np.ones((h,w))*.3,
       'current_observations':np.ones((h,w))*12,'slope_deg':np.ones((h,w))*3,'aspect_deg':np.zeros((h,w))}
    cfg={'seed':13,'plants':{'maximum_count':8,'maximum_proposals':100,'minimum_spacing_mm':22,'minimum_field':.003,'height_mm':[27,65]}}
    first=place_plants(f,cfg);second=place_plants(f,cfg)
    assert first==second;assert len(first)==8
    assert all(p['keep_C']==(p['thinning_uniform']<p['retention_at_root']) for p in first)
    assert len({p['id'] for p in first})==8


def test_circular_aspect_sampling_handles_north_wrap():
    values=np.array([[359.,1.],[359.,1.]])
    transform=from_origin(0,2,1,1);x=np.array([[1.]]);y=np.array([[1.]])
    ss,_=sample_finite(np.sin(np.deg2rad(values)),transform,x,y)
    cc,_=sample_finite(np.cos(np.deg2rad(values)),transform,x,y)
    result=float(np.rad2deg(np.arctan2(ss[0,0],cc[0,0]))%360)
    assert min(abs(result),abs(result-360))<1e-9


def test_fields_require_evidence_and_protect_high_distant_peaks():
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from datascape.composition.fields import build_fields
    cfg=json.loads((Path(__file__).parents[1]/'configs/scenes/seoul_f2_painterly_layers_v01.json').read_text())
    h,w=9,6;yy,xx=np.mgrid[:h,:w]
    # A linear mapped plane at 600 m. Geometry is untouched by layer fields.
    terrain={'owners':np.zeros((h,w),dtype=int),'faces':np.array([[0,1,2]]),
        'pixel':np.array([[0,0],[12,0],[0,18]]),
        'xyz':np.array([[0,600,40],[120,600,40],[0,600,40]])}
    shape=(h,w);ones=np.ones(shape)
    ndvi={s:ones*.4 for s in ['SPRING','SUMMER','AUTUMN','WINTER']}
    counts={s:ones*20 for s in ndvi};counts['SPRING'][8,0]=0;ndvi['SPRING'][8,1]=np.nan
    camera=SimpleNamespace(horizontal_coordinates=lambda xyz:(xyz[:,0],xyz[:,1]))
    original=terrain['xyz'].copy()
    f=build_fields(terrain,None,ones*4,ones*135,ones*100,ndvi,counts,camera,cfg)
    assert f['vegetation_before'][8,0]==f['vegetation_before'][8,1]==0
    assert f['vegetation_before'][8,4]>0
    assert np.all(f['vegetation_after']<=f['vegetation_before'])
    np.testing.assert_array_equal(original,terrain['xyz'])
    terrain['xyz'][:,2]=600
    peaks=build_fields(terrain,None,ones*4,ones*135,ones*900,ndvi,counts,camera,cfg)
    assert np.all(peaks['mist']==0)
