"""Incomplete work-coordinate review sink; no fake measured machine/profile."""
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import vector,number
from datascape.gcode.production.trajectory import Builder,Command
from datascape.gcode.production.calibration_jobs import validate_request,render_calibration
from datascape.gcode.production.benchmark import air_plan


class ReviewBuilder(Builder):
    def __init__(self,profile):
        self.profile=profile;self.v=profile.data['motion'];self.m=profile.data['machine']
        self.position=tuple(self.m['start_work_xyz']);self.commands=[];self.counts=Counter()
    def move(self,target,feed,action,state='ordinary_travel',**lineage):
        if vector(target) and number(feed,True):
            self.commands.append(Command('move',action,tuple(target),feed,state,**lineage))
        else:
            self.commands.append(Command('unresolved',action,message=json.dumps({'target_work_xyz':target,'feed_candidate_mm_min':feed},sort_keys=True),**lineage))
        self.position=tuple(target)
    def lift(self,height):
        if self.position[2] is None or self.position[2]<height:self.move((*self.position[:2],height),self.v['z_travel_mm_min'],'lift')
    def xy(self,xy,height,state='ordinary_travel'):
        self.lift(height)
        if state=='wet_loaded' and (not number(self.v.get('wet_departure_mm'),True) or not number(self.v.get('wet_arrival_mm'),True)):
            target=(*xy,self.position[2])
            self.commands.append(Command('unresolved','wet_travel',travel_state=state,message=json.dumps({
                'from_work_xyz':self.position,'target_work_xyz':target,'departure_mm':self.v.get('wet_departure_mm'),
                'arrival_mm':self.v.get('wet_arrival_mm'),'candidate_feeds_mm_min':[self.v['wet_departure_mm_min'],self.v['wet_loaded_mm_min'],self.v['wet_arrival_mm_min']]},sort_keys=True)))
            self.position=target
        else:Builder.xy(self,xy,height,state)
    def park(self,state='ordinary_travel'):
        self.lift(max(self.v['station_clearance_mm'],self.v['park_xyz'][2]));self.xy(self.v['park_xyz'][:2],self.position[2],state)
        self.move(self.v['park_xyz'],self.v['z_travel_mm_min'],'park')
    def dwell(self,seconds,action):
        if not number(seconds):self.commands.append(Command('unresolved',action,message='unmeasured dwell'))
        else:self.commands.append(Command('dwell',action,seconds=seconds))
    def marker(self,action,message='',**lineage):self.commands.append(Command('marker',action,message=message,**lineage))


def calibration_review(request,profile):
    validate_request(request,profile,physical=False)
    b=ReviewBuilder(profile)
    def station(role):
        st=profile.data['stations'][role]
        b.commands.append(Command('unresolved','station_'+role,message=json.dumps(st,sort_keys=True)))
    render_calibration(request,profile,b,station)
    return b.commands


def air_review(request,profile):
    _,jobs,manifest=air_plan(request);b=ReviewBuilder(profile);v=b.v
    for role in request.get('station_air_roles',[]):
        st=profile.data['stations'][role]
        if vector(st.get('center_xy'),2):b.xy(st['center_xy'],v['station_clearance_mm'])
        else:b.commands.append(Command('unresolved','air_station_center',message=role+' G54 center and clearance unmeasured'))
    for units in jobs.values():
        for rank,u in enumerate(units):
            f=u[0];b.marker('source_begin',str(rank),source_id=f.stroke.origin_id)
            b.xy(f.work_xy[0],v['station_clearance_mm'] if rank==0 else v['paper_hover_mm'])
            b.move((*f.work_xy[0],v['paper_hover_mm']),v['z_travel_mm_min'],'paper_hover')
            for i,xy in enumerate(f.work_xy):b.move((*xy,v['paper_hover_mm']),v['draw_mm_min'],'air_path',source_id=f.stroke.origin_id,source_vertex=i)
            b.marker('source_complete',str(rank),source_id=f.stroke.origin_id)
    b.park();return b.commands


def write_review(path,commands,profile,request):
    path=Path(path)
    if not path.name.endswith('.preview.txt'):raise ValueError('review path must end in .preview.txt; .nc is prohibited')
    lines=['; OFFLINE COMMISSIONING REVIEW ONLY; NOT AUTHORIZED; NO HARDWARE VALIDATION',
           '; No synthetic G54 offset, machine bounds or free-space box is supplied',
           '; PROFILE '+profile.sha256,'; REQUEST '+digest(request),'; G21 G90 G94 G54']
    for c in commands:
        lines.append('; RECORD '+json.dumps(asdict(c),sort_keys=True,separators=(',',':')))
        if c.kind=='move':lines.append('; G1 '+' '.join(k+f'{v:.9f}' for k,v in zip('XYZ',c.xyz))+f' F{c.feed_mm_min:.9f}')
        elif c.kind=='pause':lines.append('; M0 ; '+c.message)
        elif c.kind=='dwell':lines.append('; G4 P'+str(c.seconds))
        elif c.kind=='unresolved':lines.append('; UNRESOLVED '+c.action+' '+c.message)
    lines.append('; M2');path.write_text('\n'.join(lines)+'\n')
    return verify_review(path,commands,profile,request)


def verify_review(path,commands,profile,request):
    rows=Path(path).read_text().splitlines()
    if any(not r.startswith(';') for r in rows) or rows[-1]!='; M2':raise ValueError('executable review line or missing termination')
    if '; PROFILE '+profile.sha256 not in rows or '; REQUEST '+digest(request) not in rows:raise ValueError('review binding differs')
    if digest([json.loads(r[9:]) for r in rows if r.startswith('; RECORD ')])!=digest([asdict(c) for c in commands]):raise ValueError('review IR mismatch')
    actual=[r for r in rows if r.startswith('; G1 ')];expected=[c for c in commands if c.kind=='move']
    if len(actual)!=len(expected):raise ValueError('review move coverage')
    for r,c in zip(actual,expected):
        if any(abs(a-b)>5.1e-10 for a,b in zip([float(x[1:]) for x in r[5:].split()],[*c.xyz,c.feed_mm_min])):raise ValueError('review G54/feed mismatch')
    if [r for r in rows if r.startswith('; M0 ; ')]!=['; M0 ; '+c.message for c in commands if c.kind=='pause']:raise ValueError('review pause/reason mismatch')
    if [r for r in rows if r.startswith('; UNRESOLVED ')]!=['; UNRESOLVED '+c.action+' '+c.message for c in commands if c.kind=='unresolved']:raise ValueError('review unresolved operation mismatch')
    return {'all_lines_commented':True,'physical_readback_performed':False,'authorized':False,
            'numeric_moves_checked':len(expected),'unresolved_operations':sum(c.kind=='unresolved' for c in commands),
            'M0_count':sum(c.kind=='pause' for c in commands),'M0_reasons':[c.message for c in commands if c.kind=='pause'],
            'final_park_candidate':profile.data['motion']['park_xyz'],'commented_M2':True}
