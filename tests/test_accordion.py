"""Local phase order, locked-field isolation and geometry-only controls."""
from copy import deepcopy
import numpy as np
from scipy.ndimage import binary_erosion
from datascape.strokes.accordion import local_monotone_projection, foreground_target
from datascape.strokes.generators import continuity_mask


def scene():
    y,x=np.mgrid[:44,:60];q=300+y*25.
    xyz=np.stack([x*10.,y*10.,300-y*3.],axis=2)
    occupied=np.ones(q.shape,bool)
    f={'base':{'depth_m':q,'occupied':occupied,'xyz':xyz,'slope_deg':np.full(q.shape,8.)},
       'retention':np.full(q.shape,.7),'features':{'mound':np.exp(-((x-18)/9)**2-((y-24)/12)**2),
       'ridge':np.zeros(q.shape),'valley_small':np.exp(-((x-43)/8)**2),
       'valley_medium':np.zeros(q.shape)}}
    return f,q/20.,occupied


def test_local_solver_preserves_positive_order_on_requested_fold():
    f,phi,domain=scene();y,x=np.indices(phi.shape)
    target=phi+6*np.sin(y/3)*np.exp(-((x-30)/14)**2)
    result,record=local_monotone_projection(f,phi,target,phi,domain,smoothness=2,time_limit=30)
    gy,gx=np.gradient(result);qy,qx=np.gradient(f['base']['depth_m']);py,px=np.gradient(phi)
    ratio=(gx*qx+gy*qy)/(px*qx+py*qy)
    safe=binary_erosion(continuity_mask(f['base']),iterations=2)
    assert record['solver_status']=='solved'
    assert np.min(ratio[safe])>.049
    assert np.max(abs(result-phi))>1
    assert np.all(result[0]==phi[0])


def test_zero_request_cannot_increase_density():
    f,phi,domain=scene()
    result,record=local_monotone_projection(f,phi,phi,phi,domain,time_limit=30)
    assert np.max(abs(result-phi))<1e-9
    assert record['maximum_phase_change']<1e-9


def test_local_projection_never_mutates_retention_or_source_values():
    f,phi,domain=scene();original=deepcopy(f)
    local_monotone_projection(f,phi,phi+.5,phi,domain,time_limit=30)
    for k in ['xyz','depth_m','slope_deg']:
        assert np.array_equal(f['base'][k],original['base'][k])
    assert np.array_equal(f['retention'],original['retention'])


def test_foreground_density_uses_measured_islands_and_channels():
    f,phi,domain=scene();r=f['retention'].copy()
    target,fields=foreground_target(f,phi,cutoff=1600)
    density=fields['requested_density']
    assert density[24,18]>density[24,43]*1.8
    assert np.array_equal(f['retention'],r)
    assert np.max(abs(target-phi))>0
