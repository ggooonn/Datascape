"""Package the focused hybrid revision without changing PR43 artifacts."""
from pathlib import Path
import argparse, json, shutil, zipfile
from . import spring_color_execution as c
from . import spring_color_hybrid as h


def projection(review,audit):
    review=Path(review);dest=h.DOC/'review'
    c.require(not dest.exists(),'Use a fresh repository projection');dest.mkdir(parents=True)
    names=['policy.json','profile.color.UNMEASURED.json','summary.json','reload_comparison.json','reload_comparison.csv',
        'PR43_preservation.json','reload_comparison.png','contact_budget.png','overlap_and_mixing_intent.hybrid15.json.gz']
    names += [p.name for p in review.glob('*.gcode.gz')]+[p.name for p in review.glob('*.readback.json')]
    names += [p.name for p in review.glob('*.material.json.gz')]
    for name in names:shutil.copyfile(review/name,dest/name)
    shutil.copyfile(review/'MANIFEST_SHA256.json',dest/'FULL_GENERATED_MANIFEST_SHA256.json')
    shutil.copyfile(audit,dest/'delivered_audit.json')
    c.save(dest/'MANIFEST_SHA256.json',{p.name:c.sha(p) for p in sorted(dest.iterdir()) if p.name!='MANIFEST_SHA256.json'})
    return dict(files=len(list(dest.iterdir())),bytes=sum(p.stat().st_size for p in dest.iterdir()))


def package(review,output,audit,publication):
    review=Path(review);output=Path(output);c.require(not output.exists(),'Use a fresh ZIP path')
    contents={Path('review')/p.name:p for p in sorted(review.iterdir()) if p.is_file()}
    contents[Path('README.md')]=h.DOC/'README.md';contents[Path('delivered_audit.json')]=Path(audit)
    for pattern in ['benchmarks/integrated_330_v01/spring_color*.py','tests/test_gcode_spring_color_hybrid.py',
                    'tests/test_gcode_spring_color_execution.py','config/spring_color_hybrid_v02/policy.json']:
        for p in c.ROOT.glob(pattern):contents[Path('implementation')/p.relative_to(c.ROOT)]=p
    manifests={str(name):c.sha(p) for name,p in contents.items()}
    start="""# Spring P2 Hybrid Reload v02

Primary: review/SPRING_P2_COLOR_PR35_HYBRID15_COMPLETE_REVIEW.gcode
Matching no-contact AIR: replace COLOR with AIR in the same filename.
Open review/Review.html for the exact 15/20/30 comparison and operational notes.

600mm OR15 actual paper contacts; reset both counters after every pigment load.
Service only at complete-source boundaries. Same pigment: no full wash.
Actual pigment changes: existing wash/PURGE/rewet. Terminal cleanup unchanged.

PR43 composition, six slots/order, every numerical paper-pressure/XY/feed block,
source selection and layered sequence are frozen. The distance-only control
is byte-identical to PR43. Its separate color-response coupon and station-only
COLOR/AIR traces remain byte-identical and are included.

Use COMPLETE or the four numbered HYBRID15 stages, never both on the same sheet.
The existing provisional color curve is unchanged and needs physical observation.
No controller operation, YAML/feed/station-reference change, routine M0 or merge.
See README.md, delivered_audit.json, PUBLICATION.json and PACKAGE_SHA256.json.

The implementation folder supplies focused changes for the pinned repository.
The full repository provides the inherited backend and original frozen vectors.
"""
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in contents.items():z.write(p,str(name))
        z.writestr('START_HERE.md',start)
        z.writestr('PUBLICATION.json',json.dumps(c.read(publication),sort_keys=True,indent=2)+'\n')
        z.writestr('PACKAGE_SHA256.json',json.dumps(manifests,sort_keys=True,indent=2)+'\n')
    return dict(file=str(output),bytes=output.stat().st_size,items=len(contents)+3)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--projection',action='store_true');ap.add_argument('--output',type=Path);ap.add_argument('--publication',type=Path)
    a=ap.parse_args()
    print(json.dumps(projection(a.review,a.audit) if a.projection else package(a.review,a.output,a.audit,a.publication),indent=2))
