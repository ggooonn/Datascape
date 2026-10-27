"""Provisional compositions; native catalog controls, no physical palette."""
from shared import *

def group(name,center,members):return dict(id=name,center_mm=center,members=members)
def rock(name,group_id,width,height,count,dx=0,dy=24):
    return dict(id=name,group=group_id,target_mm=[300,780],width_mm=width,height_mm=height,major_count=count,support_dx_mm=dx,support_dy_mm=dy)

def config(season):
    c=read(ROOT/'docs/experiments/summer_foreground_v02/config.json')
    c.update(case='summer-v03' if season=='summer' else season+'-provisional-v01',season=season,
        panels={'summer':[3,4],'autumn':[5,6],'winter':[7,8]}[season],
        seed={'summer':2026102601,'autumn':2026102705,'winter':2026102707}[season],
        selected_view={'summer':'C_east','autumn':'A_south','winter':'B_northwest'}[season],
        baseline=PIN,artistic_status='provisional-review',ground=dict(support_radius_m=[185,145]))
    if season=='summer':
        c['near_groups']=[
            group('v03-left-promontory',[126,790],[[-58,7,106,'U'],[-36,-4,175,'B'],[-11,-10,236,'P'],[17,-3,204,'B'],[45,8,151,'B'],[66,15,76,'U']]),
            group('v03-inner-relay',[258,716],[[-23,2,73,'U'],[0,-5,121,'P'],[26,8,89,'B']]),
            group('v03-right-bank',[468,814],[[-43,9,115,'B'],[-18,-6,181,'B'],[11,0,163,'P'],[38,12,93,'U']]),
            group('v03-upper-relay',[524,685],[[-15,3,72,'U'],[7,-3,108,'P']])]
        c['rocks']=[rock('v03-left-foundation','v03-left-promontory',232,91,4,dy=29),rock('v03-inner-ledge','v03-inner-relay',116,47,3),rock('v03-right-foundation','v03-right-bank',174,69,3,dy=27),rock('v03-upper-ledge','v03-upper-relay',86,34,2,dy=16)]
        c['summer_progression'].update(foliage_vigor=[1.12,1.30],foliage_unit_count_scale=[1.08,1.18],stem_ratio=[.89,.91])
        c['flow_candidates']=[
            dict(id='oblique-receiver',anchors_mm=[[210,280],[180,415],[205,540],[350,685],[345,795]],width_mm=43,retained_floor=.89,release_strength=.97),
            dict(id='right-valley',anchors_mm=[[360,280],[425,415],[410,540],[355,685],[280,795]],width_mm=42,retained_floor=.87,release_strength=.97),
            dict(id='central-weave',anchors_mm=[[255,280],[295,415],[330,540],[265,685],[310,795]],width_mm=39,retained_floor=.86,release_strength=.96)]
        c['selected_flow']='oblique-receiver'
        c['composition_rationale']='Left foreground promontory, right middle relay and retained high right ridge; an oblique left-middle opening avoids repeating a fixed left-right-left alternation.'
        c['mid_far_groups']=[dict(id='middle-left',center_mm=[118,515],q_range_m=[1600,3300],radius_mm=[93,61],count=20,height_mm=[19,38]),dict(id='middle-right',center_mm=[442,558],q_range_m=[1600,3400],radius_mm=[106,72],count=33,height_mm=[23,44]),dict(id='middle-bridge',center_mm=[322,447],q_range_m=[1800,3600],radius_mm=[65,45],count=14,height_mm=[13,27])]
    elif season=='autumn':
        c['near_groups']=[group('autumn-left-bank',[111,774],[[-38,9,77,'U'],[-13,-4,153,'B'],[17,-6,178,'P'],[39,12,109,'B']]),group('autumn-saddle',[300,727],[[-22,7,74,'U'],[0,-3,128,'P'],[25,9,97,'B']]),group('autumn-right-mass',[469,802],[[-48,12,124,'B'],[-22,-3,188,'P'],[6,-9,210,'B'],[34,6,146,'B'],[54,18,83,'U']])]
        c['rocks']=[rock('autumn-left-ledge','autumn-left-bank',147,62,3),rock('autumn-saddle-ledge','autumn-saddle',110,48,2),rock('autumn-right-foundation','autumn-right-mass',222,93,4,dy=28)]
        c['summer_progression'].update(foliage_vigor=[1.02,.58],foliage_unit_count_scale=[1.,1.],stem_ratio=[.98,1.07])
        c['flow_candidates']=[dict(id='opening-right-saddle',anchors_mm=[[320,280],[333,415],[395,540],[425,685],[325,795]],width_mm=47,retained_floor=.84,release_strength=.97)]
        c['selected_flow']='opening-right-saddle';c['composition_rationale']='Unequal side masses and a saddle; the larger right foreground carries exposed rock structure while crowns retreat unevenly across P5–P6.'
        c['mid_far_groups']=[dict(id='middle-left',center_mm=[125,523],q_range_m=[1500,3400],radius_mm=[96,72],count=25,height_mm=[18,37]),dict(id='middle-right',center_mm=[445,551],q_range_m=[1500,3500],radius_mm=[106,75],count=22,height_mm=[17,34]),dict(id='far-left',center_mm=[154,320],q_range_m=[3000,11000],radius_mm=[130,85],count=21,height_mm=[6,13]),dict(id='far-right',center_mm=[438,314],q_range_m=[3000,11000],radius_mm=[125,92],count=17,height_mm=[5,12])]
        c['virtual_color_groups']['canopy_core']['preview_hex']='#85794e';c['virtual_color_groups']['canopy_edge']['preview_hex']='#b39565'
    else:
        c['near_groups']=[group('winter-left-shelter',[125,796],[[-45,7,89,'U'],[-19,-7,209,'P'],[9,-3,191,'B'],[37,12,129,'B']]),group('winter-middle-remnant',[320,748],[[-21,6,94,'B'],[0,-5,152,'P'],[27,9,67,'U']]),group('winter-right-remnant',[514,810],[[-14,4,91,'B'],[15,11,62,'U']])]
        c['rocks']=[rock('winter-left-bedrock','winter-left-shelter',244,106,4,dy=30),rock('winter-middle-bedrock','winter-middle-remnant',165,74,3,dy=27),rock('winter-right-stone','winter-right-remnant',91,39,2)]
        c['summer_progression'].update(foliage_vigor=[.38,.18],foliage_unit_count_scale=[1.,1.],stem_ratio=[1.08,1.18])
        c['flow_candidates']=[dict(id='long-right-rest',anchors_mm=[[244,280],[315,415],[353,540],[439,685],[471,795]],width_mm=64,retained_floor=.77,release_strength=.995)]
        c['selected_flow']='long-right-rest';c['composition_rationale']='A left shelter with residual pine foliage, exposed middle bedrock and a long right/P8 rest. Incomplete broadleaf and understory crowns preserve branch priority.'
        c['mid_far_groups']=[dict(id='middle-left',center_mm=[134,548],q_range_m=[1500,3400],radius_mm=[110,80],count=22,height_mm=[18,34]),dict(id='middle-right',center_mm=[417,551],q_range_m=[1500,3500],radius_mm=[110,76],count=12,height_mm=[14,29]),dict(id='far-left',center_mm=[145,319],q_range_m=[3000,11000],radius_mm=[130,92],count=17,height_mm=[5,12]),dict(id='far-right',center_mm=[445,321],q_range_m=[3000,11000],radius_mm=[126,94],count=11,height_mm=[5,10])]
        c['virtual_color_groups']['canopy_core']['preview_hex']='#627774';c['virtual_color_groups']['canopy_edge']['preview_hex']='#9a9b89';c['virtual_color_groups']['distance']['preview_hex']='#89999e'
    c['physical_note']='Middle/far contour drawing appears relatively stable; foreground is less physically verified. Separate brush strategies may be required. No canonical geometry change or G-code follows from that consideration.'
    return c
