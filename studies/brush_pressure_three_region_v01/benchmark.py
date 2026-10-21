"""Human-reviewed test design and blank observations; deliberately not G-code."""
from .curves import load_catalog
from pathlib import Path


def plan():
    patterns=[]
    def add(name,length,pressures):
        step=length/(len(pressures)-1)
        patterns.append({'id':name,'length_mm':length,
                         'test_vertices':[{'x_mm':20+i*step,'y_mm':15+14*len(patterns),'pressure_intent':p}
                                          for i,p in enumerate(pressures)],
                         'feeds_require_separate_physical_approval':True})
    for p in (.2,.28,.35,.4,.5,.6,.75,.85,.93):add('constant20-p'+str(p),20,[p,p])
    for p in (.22,.5,.85):add('short5-p'+str(p),5,[p,p])
    for p in (.28,.5,.85):add('long100-p'+str(p),100,[p,p])
    ramp=[.2,.28,.35,.4,.5,.6,.75,.85,.93]
    add('continuous-rise80',80,ramp);add('continuous-fall80',80,list(reversed(ramp)))
    add('continuous-rise-fall120',120,[.28,.4,.5,.6,.75,.85,.75,.6,.5,.4,.28])
    curves={c['id']:c for c in load_catalog(Path(__file__).with_name('candidate_curves.json')) if c['model']=='three_region'}
    return {'schema':'datascape.brush_benchmark_design.v01','status':'NOT_AUTHORIZED_NOT_GCODE',
        'brush':'large Baegunmo; free bristle length about 20 mm or more, verify',
        'frame':'G54 first paper contact Z0; all depths are unapproved compression candidates',
        'physical_execution_authorized':False,
        'preconditions':['measured machine/G54/contact plane and collision envelope',
                        'air/park evidence and separately authorized small contact test',
                        'measure free bristle/ferrule/holder clearance in installed wet state',
                        'confirm fixture/paper flatness and no-contact approach/recovery boundary'],
        'stages':[
            {'id':'depth_ladder','candidate_compression_mm':[.25,.5,1.,2.,3.],
             'permission':'Proceed only after each smaller observed depth passes; none is assumed safe',
             'candidate_draw_feed_mm_min':500,'candidate_contact_feed_mm_min':100,
             'notes':'Direct constant-Z isolated tests, not pressure remapping; return/recover between tests'},
            {'id':'first_subset','curve':'three_region_10','pressures':[.2,.28,.35],
             'permission':'Only after 3-mm region and each next requested depth are cleared',
             'patterns':['constant20','short5','continuous-low-ramp'],
             'notes':'If +3-mm compression already makes an excessively broad mark, revise the p=.2 anchor'},
            {'id':'candidate_A','curve':'three_region_10','patterns':'full eighteen-pattern coupon',
             'permission':'Clear intermediate depths monotonically before each new maximum; p=.93 requests 8.95 mm'},
            {'id':'candidate_B','curve':'three_region_12','patterns':'same eighteen-pattern coupon on fresh paper',
             'permission':'Only if A leaves a measured reason for greater compression; p=.93 requests 10.65 mm'},
            {'id':'endpoint_confirmation','pressure':1.,'candidate_maximum_mm':[10.,12.],
             'permission':'Optional separate deepest-anchor test only after lower depths pass; not a Spring requirement'},
            {'id':'speed_progression','candidate_draw_feeds_mm_min':[500,1000,2500,5000],
             'candidate_contact_release_feeds_mm_min':[100,300,1000,1500,2000],
             'permission':'One variable at a time; faster contact/release/pressure Z only after quality/recovery and controller acceleration tests'}],
        'coupon_xy_extent_mm':[[20,15],[140,253]],'patterns':patterns,'candidate_curves':curves,
        'replication':'Repeat p=.28/.5/.85 at least twice; test ink and diluted gouache separately with reference loading',
        'loading_control':'Record brush, medium dilution/glue, loading, wash/absorption and reference liquid level; do not compare unequal loads',
        'manual_observation_stops_expected':True,
        'stop_or_reduce':['holder/ferrule clearance uncertain','paper scoring, fibers lifting or pooling',
                          'discontinuous/split mark or lost fine control','bristles fail to recover before next approach',
                          'unexpected axis behavior, missed steps or loss of registration'],
        'record_fields':['test_id','curve_id','medium','pressure_or_direct_depth','commanded_and_measured_Z_mm',
                         'free_bristle_length_mm','mounting','paper_and_mounting','liquid_loading_and_dilution',
                         'draw_contact_release_feeds','installed_acceleration_and_junction',
                         'width_start_mid_end_mm','width_after_drying_mm','continuity',
                         'pigment_distribution','paper_response','recovery_time_and_clearance',
                         'photo_scale_and_id','operator','date','pass_reduce_stop','notes']}


if __name__=='__main__':
    import json
    print(json.dumps(plan(),indent=2))
