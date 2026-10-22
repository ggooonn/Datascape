"""Deterministic independent benchmark candidates; no physical approvals."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
from datascape.gcode.production.profiles import Profile

BACKEND='12b28bd5b7ad575b1438ed5af61618746c7effe9'
LOCAL_HOVER='0eeff5d0d874b9b869c3f274d06bf524ac18282a'
KNOTS=[[0,0],[.2,-2],[.4,-2.64],[.6,-3.92],[.93,-8.8],[1,-10]]


def profile(root):
    d=json.loads((Path(root)/'config/plotter_v03/profile.unmeasured.json').read_text())
    d['profile_id']='COMMISSIONING-330-REPORTED-NOT-AUTHORIZED'
    d['machine'].update(start_work_xyz=[0,898,35],mounted_brush_id='baegunmo-commissioning-01',
        hardware_version='DLC32v22-assembly-commissioning-01',substrate_id='paper-330-test-01',paper_surface_above_bed_mm=None)
    d['motion'].update(park_xyz=[800,800,32],paper_hover_mm=10,station_clearance_mm=32,
        local_hover={'enabled':False,'height_mm':5,'max_distance_mm':10},air_station_roles=[],
        draw_mm_min=600,ordinary_travel_mm_min=1200,partially_depleted_mm_min=600,wet_loaded_mm_min=600,
        wet_departure_mm_min=300,wet_arrival_mm_min=300,
        z_travel_mm_min=300,paper_approach_mm_min=300,paper_contact_mm_min=60,paper_release_mm_min=60,
        pressure_z_mm_min=120,contact_mm_min=60,station_approach_mm_min=None)
    for medium,b in d['brush_profiles'].items():
        b.update(brush_id=d['machine']['mounted_brush_id'],hardware_version=d['machine']['hardware_version'],
                 substrate=d['machine']['substrate_id'],substrate_surface_height_mm=None,knots=deepcopy(KNOTS),status='unverified',
                 observations=[],notes='Unmeasured design candidate only. No assumption that p=.93 reaches -10 mm.')
    d['stations']={r:s for r,s in d['stations'].items() if r in ('ink','water','sponge')}
    for role in ('ink','water'):
        s=d['stations'][role];s.update(center_xy=None,coordinate_frame='G54',liquid_reference_z=None,immersion_mm=2,
           deep_surface_xyz=None,shallow_surface_xyz=None,stone_gap_mm=None,exit_above_liquid_mm=None)
        if role=='water':s['rewet_immersion_mm']=2
    d['stations']['sponge'].update(surface_z=None,compression_mm=.5,notes='Cloth/rag candidate, not sponge mechanics; remeasure after folding or securing changes; one vertical dab, no XY rubbing.')
    d['notes']='User-reported WPos after homing retained. No MPos/G54 transform inferred. Base profile unverified; evidence empty; cloth and colors inactive. Feed/depth/clearance/park values are test candidates. Assigned IDs are record labels, not physical certification.'
    return Profile.from_dict(d)


def line(y,z,start=30,end=90):return {'start_xy':[start,y],'end_xy':[end,y],'z_mm':z,'feed_mm_min':600}


def designs():
    rectangle=[[15,15],[315,15],[315,315],[15,315],[15,15]]
    def air(name,repeats,stream=False,roles=None):
        paths=[{'id':f'{name}-rectangle-{i}','work_xy':deepcopy(rectangle)} for i in range(repeats)]
        if stream:
            # Two 301-vertex sweeps expose streaming/short-segment behavior, not hours of reliability.
            paths += [{'id':f'{name}-stream-{y}','work_xy':[[15+i,y+(i%2)] for i in range(301)]} for y in (100,200)]
        return {'schema':'datascape.benchmark_air_plan.v0.3','benchmark_id':name,'substrate_mm':[330,330],
                'margin_mm':10,'paths':paths,'station_air_roles':roles or [],'notes':'Independent G54 work XY; no contact or evidence auto-pass. Rehome/re-register after loss; never resume an arbitrary line.'}
    plans={'A_SHORT':air('A_SHORT',1),'A_STABILITY':air('A_STABILITY',4,True),
           'A_STATION_OPTIONAL':air('A_STATION_OPTIONAL',1,roles=['water','ink'])}
    def contact(**kw):return {'schema':'datascape.calibration_plan.v0.3','paper_region_xy':[[10,10],[320,320]],**kw}
    for i in (1,2,3):plans[f'B_DEPTH_{i}']=contact(brush_lines=[line(10+30*i,-i)],notes='Manually loaded ink; advance only after shallower depth observations and explicit safe envelope approval.')
    def pressure(y,values):return {'medium':'ink','slot':'INK','feed_mm_min':600,'samples':[{'xy':[30+30*i,y],'pressure':v} for i,v in enumerate(values)]}
    plans['C_LOW']=contact(pressure_lines=[pressure(140,[.2,.35,.45,.35,.2])],requires_evidence=['paper_contact'],notes='Initial variable-pressure candidate; maximum compression about 2.96 mm, not a measured curve.')
    plans['C_EXTENDED_LATER']=contact(pressure_lines=[pressure(170,[.2,.4,.6,.8,.93,.6,.2])],requires_evidence=['paper_contact'],notes='Later isolated depth expansion only; reaches -8.8 mm, cannot execute under an initial -3 mm envelope.')
    plans['D_HOVER']=contact(hover_groups=[{'hover_mm':h,'max_transition_mm':10,
          'strokes':[line(y,-2,30,50),line(y,-2,55,75),line(y,-2,85,105)]} for h,y in [(10,220),(5,250)]],
          requires_evidence=['paper_contact'],notes='Manual ink; compare 5-mm and 10-mm endpoint gaps. Local-hover trial creates observations; production local hover stays disabled.')
    plans['E_INK']=contact(station_roles=['ink'],requires_evidence=['paper_contact'],notes='WELL_2 only; inspect dip and diagonal withdrawal; no washing or PURGE.')
    plans['E_WATER']=contact(station_roles=['water'],requires_evidence=['paper_contact'],notes='WELL_1 one isolated water operation; no automatic repeated washing cycles or PURGE.')
    plans['E_CLOTH_OPTIONAL']=contact(station_roles=['sponge'],requires_evidence=['paper_contact'],notes='PURGE label retained by backend; secured cloth surface must be measured. One 0.5-mm candidate vertical dab; no XY rubbing.')
    plans['E_INK_REAPPLY']=contact(station_roles=['ink'],brush_lines=[line(290,-2)],requires_evidence=['paper_contact','station_ink_trial','station_water_trial'],notes='Only after separate water and ink tests passed; inspect loading, then reapply a short line. No automatic all-station workflow.')
    return plans


def yaml_audit(path):
    # Optional research dependency; controller bytes are never modified or published.
    import yaml
    raw=Path(path).read_bytes();d=yaml.safe_load(raw)
    axes={}
    for name in ('x','y','z'):
        a=d['axes'][name];axes[name]={k:a[k] for k in ('steps_per_mm','max_rate_mm_per_min','acceleration_mm_per_sec2','max_travel_mm')}
        axes[name]['homing_mpos_mm']=a['homing']['mpos_mm'];axes[name]['pull_off_mm']=a['motor0']['pulloff_mm']
    return {'source_name':Path(path).name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
            'installed_identity_verified':False,'name':d['name'],'board_label':d['board'],'axes':axes,
            'conflicts':['Stored X pull-off is 2 mm; current user report is approximately 5 mm.',
                        '900/960/50 nominal travel is not reported usable travel 850-860/898/~46 mm.',
                        'Stored homing MPos 0/960/50 cannot determine G54 offset from WPos 0/898/35.',
                        'DEV rates and accelerations have not been approved for the mounted wet brush.']}


def measurements(audit):
    return {'schema':'datascape.commissioning_measurements.v01','backend_pin':BACKEND,'study_pin':LOCAL_HOVER,
      'evidence_automatically_passed':False,'authorization_supplied':False,'controller_file_audit':audit,
      'reported':{'controller':'MKS DLC32 V2.2 / FluidNC','directions':'all XYZ corrected per user',
        'limits':'all respond in $Limits per user','homing':'repeated success per user; full estop record missing',
        'home_WPos':[0,898,35],'first_paper_contact_work_z':0,'Z_envelope':'verified by user; approximate downward travel 46 mm',
        'well_regions_XY':{'water':[840,220,285],'ink':[840,370,435]},
        'well_geometry_bed_mm':{'rim':18,'shallow_floor':10,'deep_floor':6,'interior_length':105,'shallow_flat':60,'slope_length':45},
        'well_region_registration':'user checked mapped regions/deep loading areas; precise deep/shallow XYZ still missing',
        'USB':'stable after port change; no duration/reliability certification'},
      'approximate':{'usable_X_mm':[850,860],'Y_span_mm':898,'Z_downward_mm':46,'paper_above_bed_nominal_mm':1,
        'well_liquid_bed_z_mm':[10,11],'cloth_bed_surface_z_mm':[3,5],
        'palette_bed_rim_z_mm':29,'palette_bed_floor_z_mm':2,'palette_center_X_mm':847,'palette_XY_clearance_radius_mm':7,
        'holder_lower_structure_above_bed_mm':'>40, user observation'},
      'candidates':{'park_work_xyz':[800,800,32],'normal_hover_z':10,'local_hover_z':5,'local_distance_mm':10,
        'paper_max_compression_z':-10,'initial_brush_depths_mm':[-1,-2,-3],'manual_ink_draw_feed_mm_min':600,
        'initial_immersion_mm':2,'later_immersion_mm':3,'cloth_compression_mm':[.5,1],
        'first_contact_candidates_are_not_approved':True},
      'derived_nominal_only':{'well_liquid_work_z_mm':[9,10],'deep_floor_work_z':5,'shallow_floor_work_z':9,
        'initial_dip_work_z_mm':[7,8],'floor_gap_at_2mm_immersion_mm':[2,3],'floor_gap_at_3mm_immersion_mm':[1,2],
        'cloth_work_surface_z_mm':[2,4],'well_rim_work_z':17,'palette_rim_work_z':28,
        'station_clearance_above_nominal_well_rim_mm':15,'station_clearance_above_nominal_palette_rim_mm':4,
        'reported_minimum_work_Z_approx':-11,'margin_at_max_candidate_Z_approx_mm':1,
        'palette_radius7_reaches_X':854,'max_radius_at_Xmax850_without_tool_margin':3},
      'unknown':['installed YAML and firmware identity','G54/MPos/WCO/G92/tool-offset state',
        'actual machine bounds, tool margins, swept free/keepout volumes, full park approach',
        'paper registration/flatness/no-contact approach boundary and safe first-test contact range',
        'approved initial axis/feed/brush acceleration limits and wet edge distances',
        'exact liquid level, deep/shallow XYZ, stone gap, exit height, station contact volume/feed/dwell',
        'secured cloth surface/contact volume and behavior','explicit operator stage/profile/plan/job authorization']}
