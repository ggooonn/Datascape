"""Verify frozen inputs, deterministic sidecars and exact-source review guides."""
from model import *
import platform,subprocess,sys
from shapely.geometry import LineString
from shapely.ops import substring
from collections import Counter

def verify():
    c=read(CONFIG);scenes=[load_scene(s) for s in ORDER];checks=[];sources={};counts={}
    def check(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    paths=set()
    for scene in scenes:
        s=scene['season'];folder=ROOT/SCENES[s]
        paths.update(scene['source_files'])
        if s!='spring':paths.update(str((folder/n).relative_to(ROOT)) for n in ['config.json','scene.json','fields.npz','placement.json'])
    paths.update(['artworks/spring_v13/palette.json','docs/experiments/seasonal_composition_v03/skyline.json','docs/experiments/seasonal_composition_v03/P1_P8_full.png'])
    for path in sorted(paths):
        data=(ROOT/path).read_bytes()
        original=subprocess.check_output(['git','show',c['baseline_commit']+':'+path],cwd=ROOT)
        check('pinned input: '+path,hashlib.sha256(data).digest()==hashlib.sha256(original).digest())
        sources[path]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    changed=subprocess.check_output(['git','diff','--name-only',c['baseline_commit'],'--'],cwd=ROOT,text=True).splitlines()
    allowed=('configs/experiments/seasonal_color_tone_v01.json','docs/experiments/seasonal_color_tone_v01/','studies/seasonal_color_tone_v01/','tests/test_seasonal_color_tone_v01.py')
    check('all tracked changes confined to additive study paths',all(p.startswith(allowed) for p in changed))
    max_arc_error=0.
    for scene in scenes:
        s=scene['season'];out=OUT/s;before={k:geometry_signature(scene[k]) for k in ['ink','color']}
        side=styles(scene,c);guide=guides(scene,c)
        check(s+' deterministic style sidecar',digest(side)==digest(styles(scene,c))==digest(read(out/'style_intent.json.gz')))
        check(s+' deterministic guide sidecar',digest(guide)==digest(guides(scene,c))==digest(read(out/'color_territory_guides.json.gz')['guides']))
        check(s+' unchanged source expression and geometry',before=={k:geometry_signature(scene[k]) for k in before}==side['geometry_signatures'])
        check(s+' no physical schedule',side['physical_pigment_schedule'] is None and not side['production_Gcode'] and not side['pressure_profiles_modified'])
        for kind in ['ink','color']:
            ids=[r['id'] for r in scene[kind]];style_ids=[r['source_id'] for r in side[kind]]
            check(s+' '+kind+' exact source-ID coverage',ids==style_ids and len(set(ids))==len(ids))
            check(s+' '+kind+' styles contain no coordinates',all('xy_mm' not in r for r in side[kind]))
        parents={r['id']:r for r in scene['ink']}
        for g in guide:
            line=LineString(parents[g['source_id']]['xy_mm']);a,b=g['source_arc_mm'];expected=substring(line,a,b);actual=LineString(g['xy_mm'])
            err=max(expected.hausdorff_distance(actual),abs((b-a)-actual.length));max_arc_error=max(max_arc_error,err)
            check(s+' guide arc '+g['id'],err<1e-7 and g['physical_station'] is None and not g['production_color_path'] and not g['canonical_geometry'])
        counts[s]=dict(source_ink=len(scene['ink']),source_color=len(scene['color']),guides=len(guide))
        if s=='spring':check('Spring creates no supplemental paths',len(guide)==0)
        if s in ['spring','summer']:
            check(s+' strong D4 excluded',all(r['D4_strong_use_excluded'] and r['physical_station'] is None for r in side['color']))
        stats=read(out/'statistics.json')['panels']
        check(s+' clipped per-panel length conserves source ink',abs(sum(p['ink_length_mm'] for p in stats.values())-sum(map(length,scene['ink'])))<1e-5)
    check('Spring D4 canonical path count remains 352',sum(r.get('palette_slot')=='D4' for r in scenes[0]['color'])==352)
    for role in ['base','structural','mineral','accent']:
        for j in range(1,8):check(role+f' continuity P{j}/P{j+1}',np.max(abs(palette_at(c,j*300-1e-7,role)-palette_at(c,j*300+1e-7,role)))<1e-6)
        values=palette_at(c,np.linspace(0,2400,2401),role);check(role+' finite display gamut',np.isfinite(values).all() and values.min()>=0 and values.max()<=1)
    p2=read(OUT/'spring/P2_style_handoff.json.gz')
    check('P2 handoff is references only and not execution ready',not p2['geometry_included'] and not p2['execution_ready'] and p2['physical_palette_map'] is None)
    props=read(OUT/'foreground_identity_proposals.json');check('foreground recommendations not applied',not props['geometry_changes_applied'])
    for i in range(1,9):
        with Image.open(OUT/f'P{i}.png') as im:im.load();check(f'P{i} dimensions',im.size==(600,1800))
    image_count=0
    for p in OUT.rglob('*.png'):
        with Image.open(p) as im:im.load();image_count+=1
    check('horizontal dimensions',Image.open(OUT/'P1_P8_theme.png').size==(5360,1880))
    check('all review PNGs decode',image_count>=45)
    check('no G-code in additive outputs',not any(p.suffix.lower() in ['.gcode','.nc','.tap'] for p in OUT.rglob('*')))
    save(OUT/'reproducibility_manifest.json',dict(baseline_commit=c['baseline_commit'],source_inputs=sources,
        config_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),python=platform.python_version(),
        renderer_scope='Matched line/profile display approximation; not a wet pigment simulation or canonical path export'))
    result=dict(status='passed',checks_passed=len(checks),checks=checks,images_decoded=image_count,max_guide_arc_error_mm=max_arc_error,
        scenes=counts,baseline_commit=c['baseline_commit'],artistic_acceptance=False,physical_color_execution_verified=False,
        scope='Reproducibility of additive color/tone study only. Earlier geometry tests are not rerun because no geometry/generator is modified.')
    save(OUT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
    return result

if __name__=='__main__':verify()
