"""Independent work-coordinate Air Run plans through the existing gated exporter."""
from datascape.gcode.models import Point,Stroke
from datascape.gcode.layout import Layout
from datascape.gcode.binding import digest
from .profiles import number,vector
from .sequence import make_plan,verify_plan
from .exporter import _atomic_output,save_json


def air_plan(request):
    allowed={'schema','benchmark_id','substrate_mm','margin_mm','paths','station_air_roles','notes'}
    if request.get('schema')!='datascape.benchmark_air_plan.v0.3' or set(request)-allowed:raise ValueError('unknown benchmark Air Run plan')
    if request.get('substrate_mm')!=[330,330]:raise ValueError('this independent benchmark requires 330x330 mm')
    margin=request.get('margin_mm')
    if not number(margin,True) or margin>=165:raise ValueError('invalid benchmark margin')
    if not isinstance(request.get('benchmark_id'),str) or not request['benchmark_id'].strip():raise ValueError('benchmark ID required')
    paths=request.get('paths');roles=request.get('station_air_roles',[])
    if not isinstance(roles,list) or any(r not in ('ink','water','sponge') for r in roles) or len(roles)!=len(set(roles)):raise ValueError('invalid station Air Run roles')
    if not isinstance(paths,list) or not paths:raise ValueError('Air Run paths required')
    layout=Layout('D');top=layout.panels[0].y_max;strokes=[];ids=set()
    for i,path in enumerate(paths):
        if set(path)!={'id','work_xy'} or not isinstance(path['id'],str) or not path['id'].strip() or path['id'] in ids:raise ValueError('invalid/duplicate Air Run source ID')
        ids.add(path['id']);xy=path['work_xy']
        if not isinstance(xy,list) or len(xy)<2 or any(not vector(p,2) or any(not margin<=q<=330-margin for q in p) for p in xy):raise ValueError('Air Run point outside registered benchmark margin')
        # Existing Layout's Y inversion is an explicit adapter, not a new 900-mm benchmark.
        strokes.append(Stroke(path['id'],tuple(Point(x,top-y,0) for x,y in xy),'COMMISSIONING_AIR','INK','ink',sequence=i))
    jobs,manifest=make_plan(strokes,layout,tuple(range(len(strokes))))
    name='BENCHMARK_A_AIR';old=jobs.pop('SHARED_INK');jobs[name]=old
    manifest['jobs'][name]=manifest['jobs'].pop('SHARED_INK')
    manifest['policy']='independent_commissioning_no_artwork'
    manifest['benchmark']={'request':request,'work_region_mm':[[0,0],[330,330]],
                           'coordinate_adapter':'input G54 XY -> existing Layout artwork (x, full_panel.y_max-y) -> exact same G54 XY',
                           'not_a_Spring_job':True}
    return tuple(strokes),jobs,manifest


def require_air_profile(request,profile):
    if profile.data['motion'].get('air_station_roles',[])!=request.get('station_air_roles',[]):
        raise ValueError('profile Air Run station tour differs from explicitly requested benchmark')
    for role in request.get('station_air_roles',[]):
        st=profile.data['stations'][role]
        if st.get('coordinate_frame')!='G54' or not vector(st.get('center_xy'),2):raise ValueError('measure G54 station-center XY before station Air Run')


def prepare_air(request,profile,output):
    strokes,jobs,manifest=air_plan(request)
    def write(root):
        import gzip,json
        save_json(root/'plan.json.gz',manifest)
        written=json.loads(gzip.decompress((root/'plan.json.gz').read_bytes()))
        checked=verify_plan(written,strokes,Layout('D'))
        checked={k:v for k,v in checked.items() if not k.startswith('D_')}
        checked['independent_unfragmented_work_paths']=len(strokes)
        result={'benchmark_only':True,'substrate_mm':[330,330],
                'plan_sha256':digest(manifest),
                'readback':checked,
                'readiness':None if profile is None else profile.issues('air',media=('ink',)),
                'hardware_executed':False,'executable_written':False}
        save_json(root/'report.json',result);return result
    return _atomic_output(output,write)
