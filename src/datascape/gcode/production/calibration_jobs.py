"""Small explicit contact tests; production artwork and evidence are never edited."""
from math import dist
from .profiles import number,vector
from .trajectory import Builder,Materials,Command

EXTRA_EVIDENCE = ('paper_contact','station_ink_trial','station_water_trial','cloth_purge_trial')


def validate_request(request,profile,physical=True):
    if request.get('schema')!='datascape.calibration_plan.v0.3':raise ValueError('unknown calibration plan')
    allowed={'schema','station_roles','brush_lines','pressure_lines','hover_groups','requires_evidence','paper_region_xy','notes'}
    if set(request)-allowed:raise ValueError('unknown calibration request fields')
    for key in ('station_roles','brush_lines','pressure_lines','hover_groups','requires_evidence'):
        if not isinstance(request.get(key,[]),list):raise ValueError('calibration '+key+' must be a list')
    roles=request.get('station_roles',[])
    if any(not isinstance(r,str) or r not in profile.data['stations'] for r in roles) or len(roles)!=len(set(roles)):
        raise ValueError('invalid or duplicate station role')
    required=request.get('requires_evidence',[])
    if any(c not in EXTRA_EVIDENCE for c in required) or len(required)!=len(set(required)):raise ValueError('unknown calibration prerequisite')
    if (request.get('pressure_lines') or request.get('hover_groups')) and 'paper_contact' not in required:
        raise ValueError('variable-pressure and local-hover tests require prior paper_contact observations')
    if physical:
        profile.require('calibration',roles)
        for check in required:
            if not profile.evidence_passed(check):raise ValueError('missing current-profile calibration prerequisite: '+check)
    if not any(request.get(k) for k in ('station_roles','brush_lines','pressure_lines','hover_groups')):raise ValueError('empty calibration plan')
    v=profile.data['motion'];envelope=v.get('paper_contact_z_range')
    region=request.get('paper_region_xy')
    if region is not None and (not isinstance(region,list) or len(region)!=2 or not all(vector(p,2) for p in region) or any(a>=b for a,b in zip(*region))):raise ValueError('invalid benchmark paper region')
    def paper_point(xy):
        if not vector(xy,2):raise ValueError('invalid paper point')
        if region is not None and any(not a<=x<=b for x,a,b in zip(xy,*region)):raise ValueError('paper contact outside benchmark region')
    def depth(z):
        if not number(z) or z>0:raise ValueError('invalid calibration depth')
        if physical and (not vector(envelope,2) or not envelope[0]<=z<=envelope[1]):raise ValueError('calibration depth outside measured test envelope')
    def line(item):
        if set(item)!={'start_xy','end_xy','z_mm','feed_mm_min'}:raise ValueError('invalid brush calibration line')
        if not vector(item['start_xy'],2) or not vector(item['end_xy'],2) or not number(item['feed_mm_min'],True):raise ValueError('invalid test XY/feed')
        paper_point(item['start_xy']);paper_point(item['end_xy'])
        if dist(item['start_xy'],item['end_xy'])<=0:raise ValueError('brush calibration line must have length')
        depth(item['z_mm'])
    for item in request.get('brush_lines',[]):line(item)
    for item in request.get('pressure_lines',[]):
        if set(item)!={'samples','feed_mm_min','medium','slot'} or item['medium']!='ink' or item['slot']!='INK':raise ValueError('pressure calibration currently supports explicit ink samples only')
        if not isinstance(item['samples'],list) or len(item['samples'])<2 or not number(item['feed_mm_min'],True):raise ValueError('invalid pressure test samples/feed')
        curve=profile.brush_for('ink','INK')
        for s in item['samples']:
            if set(s)!={'xy','pressure'} or not vector(s['xy'],2):raise ValueError('invalid pressure test sample')
            paper_point(s['xy'])
            depth(curve.z_for(s['pressure']))
        if any(dist(a['xy'],b['xy'])<=0 for a,b in zip(item['samples'],item['samples'][1:])):raise ValueError('pressure test samples need distinct consecutive XY')
    for group in request.get('hover_groups',[]):
        if set(group)!={'strokes','hover_mm','max_transition_mm'} or not isinstance(group['strokes'],list) or len(group['strokes'])<2:raise ValueError('invalid explicit hover test group')
        h=group['hover_mm'];limit=group['max_transition_mm']
        if not number(h,True) or not h<=v['paper_hover_mm'] or not number(limit,True) or limit>10:raise ValueError('hover test exceeds explicit height/distance policy')
        if physical and h<v['paper_approach_mm']:raise ValueError('hover test below measured approach boundary')
        for item in group['strokes']:line(item)
        if any(dist(a['end_xy'],b['start_xy'])>limit+1e-12 for a,b in zip(group['strokes'],group['strokes'][1:])):raise ValueError('hover transition exceeds requested distance')
    return request


def render_calibration(request,profile,b,station_contact=None):
    """Shared geometry for a checked physical builder or a comment-only review sink."""
    v=profile.data['motion']
    b.commands.append(Command('pause','startup_verification',message='CALIBRATION ONLY: verify G54/MPos/start; manual load; explicit contact test limits; abort on mismatch'))
    station_contact=station_contact or (lambda role:Materials(b).station(role,'calibration_contact'))
    for role in request.get('station_roles',[]):
        b.pause('INSPECT '+role+' and measured reference/geometry before this explicit station test','wet_loaded')
        station_contact(role)
        b.pause('INSPECT station test result; abort before next test if uncertain','wet_loaded')
    def begin(xy):
        b.xy(xy,v['station_clearance_mm'],'wet_loaded')
        b.move((*xy,v['paper_hover_mm']),v['z_travel_mm_min'],'paper_hover')
    def contact(xy):
        b.move((*xy,v['paper_approach_mm']),v['paper_approach_mm_min'],'approach')
        b.move((*xy,0),v['paper_contact_mm_min'],'initial_contact')
    def release(xy,h):
        b.move((*xy,0),v['paper_release_mm_min'],'release')
        b.move((*xy,v['paper_approach_mm']),v['paper_release_mm_min'],'paper_release_clearance')
        b.move((*xy,h),v['z_travel_mm_min'],'retract')
    def constant(item):
        start,end=item['start_xy'],item['end_xy']
        begin(start)
        contact(start)
        b.move((*start,item['z_mm']),v['paper_contact_mm_min'],'calibration_compression')
        b.move((*end,item['z_mm']),min(item['feed_mm_min'],v['draw_mm_min']),'draw')
        release(end,v['paper_hover_mm'])
    for i,line in enumerate(request.get('brush_lines',[])):
        b.pause('BRUSH TEST '+str(i)+': record loading; manually load if needed; inspect width, continuity and recovery','wet_loaded')
        constant(line)
    for i,line in enumerate(request.get('pressure_lines',[])):
        b.pause('PRESSURE TEST '+str(i)+': verify approved depth envelope and recorded manual ink loading','wet_loaded')
        samples=line['samples'];begin(samples[0]['xy']);contact(samples[0]['xy'])
        curve=profile.brush_for('ink','INK');source='calibration-pressure-'+str(i)
        for n,s in enumerate(samples):
            b.move((*s['xy'],curve.z_for(s['pressure'])),v['paper_contact_mm_min'] if n==0 else min(line['feed_mm_min'],v['draw_mm_min']),
                   'pressure_variation' if n==0 else 'draw',source_id=source,fragment_id=source,source_vertex=n,artistic_pressure=s['pressure'])
        release(samples[-1]['xy'],v['paper_hover_mm'])
    for i,group in enumerate(request.get('hover_groups',[])):
        b.pause('LOCAL HOVER TEST '+str(i)+': isolated calibration trial, not production clearance evidence; inspect after this group','wet_loaded')
        for n,line in enumerate(group['strokes']):
            # Final stroke retracts to normal hover; only the measured test links use local height.
            h=group['hover_mm'] if n<len(group['strokes'])-1 else v['paper_hover_mm']
            if n==0:begin(line['start_xy'])
            else:b.xy(line['start_xy'],group['hover_mm'],'wet_loaded')
            contact(line['start_xy']);b.move((*line['start_xy'],line['z_mm']),v['paper_contact_mm_min'],'calibration_compression')
            b.move((*line['end_xy'],line['z_mm']),min(line['feed_mm_min'],v['draw_mm_min']),'draw');release(line['end_xy'],h)
    b.pause('CALIBRATION COMPLETE: record observations; do not automatically mark evidence passed','wet_loaded')
    return b.commands


def build_calibration(request,profile):
    validate_request(request,profile,physical=True)
    b=Builder(profile);render_calibration(request,profile,b)
    return b.commands,b.result()
