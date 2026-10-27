"""Compact Git review projection and self-contained downloadable experiment."""
from pathlib import Path
import argparse, shutil, zipfile
from .spring_color_execution import read, save, sha, ROOT, REFERENCE_PATHS

PROGRAM_BASE='SPRING_P2_COLOR_PR35_COMPLETE_REVIEW'
REVIEW_PREFIX=Path('docs/spring_color_execution_v01/review')


def repository_projection(review, audit=None):
    review=Path(review);dest=ROOT/REVIEW_PREFIX
    dest.mkdir(parents=True,exist_ok=True)
    names=['profile.color.UNMEASURED.json','policy.json','schedule.json','PR35_overlap_audit.json.gz',
        'future_dual_brush_compatibility.json.gz','layering_constraints.json.gz','S3a_comparison.json',
        'pigment_slots.json','pigment_slots.csv','source_to_slot_replacements.json','source_to_slot_replacements.csv',
        'fine_color_OFFLINE_ONLY.json','D4_restrained_comparison.json','COLOR_RESPONSE_COUPON_LAYOUT.json',
        'calibration_source_units.json.gz','verification.json','overlap_and_mixing_intent.json.gz']
    names += [p.name for p in review.glob('*.gcode.gz')]+[p.name for p in review.glob('*.readback.json')]
    names += ['P2_comparison.png','P2_PR35_color_primary.png','P2_color_only.png','P2_sequence.png','P2_roles.png',
        'P2_pigment_slots.png','P2_D4_comparison.png','P2_overlap_map.png','foreground_comparison.png',
        'middle_comparison.png','far_comparison.png','runtime_comparison.png']
    for name in names:shutil.copyfile(review/name,dest/name)
    shutil.copyfile(review/'MANIFEST_SHA256.json',dest/'FULL_GENERATED_MANIFEST_SHA256.json')
    rows=read(review/'source_selection.json.gz')
    save(dest/'source_selection.index.json.gz',[{k:v for k,v in r.items() if k!='clipped_fragments'} for r in rows])
    summary=read(review/'summary.json')
    summary['primary']={k:v for k,v in summary['primary'].items() if k not in ['events','loads','station_operations','runtime_assumptions']}
    summary['stages']={k:{a:v for a,v in m.items() if a not in ['events','loads','station_operations','runtime_assumptions']} for k,m in summary['stages'].items()}
    summary['repository_projection']='Full IR, source-selection geometry, HTML/SVG, original vectors and all117 generated files are in the Work package and reproduced by generator'
    save(dest/'summary.compact.json',summary)
    for p in review.glob('*.material.json.gz'):shutil.copyfile(p,dest/p.name)
    if audit:shutil.copyfile(audit,dest/'delivered_audit.json')
    save(dest/'MANIFEST_SHA256.json',{p.name:sha(p) for p in sorted(dest.iterdir()) if p.name!='MANIFEST_SHA256.json'})
    return dict(directory=str(dest),files=len(list(dest.iterdir())),bytes=sum(p.stat().st_size for p in dest.iterdir()))


def package(review,context,output,audit,publication=None):
    review=Path(review);context=Path(context);output=Path(output)
    if output.exists():raise ValueError('Use a fresh ZIP output path')
    policy=read(review/'policy.json')
    contents={Path('review')/p.name:p for p in sorted(review.iterdir()) if p.is_file()}
    contents[Path('README.md')]=ROOT/'docs/spring_color_execution_v01/README.md'
    contents[Path('delivered_audit.json')]=Path(audit)
    for path in REFERENCE_PATHS:
        contents[Path('original_references')/path]=context/path
    for pattern in ['benchmarks/integrated_330_v01/spring_color*.py','tests/test_gcode_spring_color_execution.py','config/spring_color_execution_v01/policy.json']:
        for p in ROOT.glob(pattern):contents[Path('implementation')/p.relative_to(ROOT)]=p
    manifest={str(path):sha(p) for path,p in contents.items()}
    if publication:manifest['publication']='See PUBLICATION.json; exact Draft PR reference, not merged'
    import json
    publication_text=json.dumps(publication or {},sort_keys=True,indent=2)+'\n'
    start="""# Spring P2 Color Execution v01

Open review/Review.html for the complete visual and operational review.
Ordinary full COLOR and AIR G-code, four separated stage pairs, station-only
and spare-hanji response-coupon pairs are in review/. Every file is complete.

The first sheet already has PR35 ink. No PR39/41/42 ink-deferred detail is added.
The future compatibility reference is the exact published PR42 recommended B.

Choose COMPLETE or the four numbered stages, never both on the same artwork.
Inspect current registration/stations and observe the separate unmeasured color
curve on spare backed hanji before contact on the artwork. No routine M0.

Source-width images are display proxies. No physical dilution, measured pigment
mixing ratio, drying guarantee or machine-clearance certificate is supplied.

See README.md, delivered_audit.json and PUBLICATION.json. The implementation
folder contains additive source/config/tests for the referenced repository;
the full repository with its pinned Git objects supplies the inherited backend.
Original unmodified vectors and PR40 sidecars are under original_references/.
"""
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in contents.items():z.write(p,str(name))
        z.writestr('START_HERE.md',start)
        z.writestr('PUBLICATION.json',publication_text)
        z.writestr('PACKAGE_SHA256.json',json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return dict(file=str(output),bytes=output.stat().st_size,archive_items=len(contents)+3)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review',type=Path,required=True);ap.add_argument('--audit',type=Path)
    ap.add_argument('--projection',action='store_true')
    ap.add_argument('--context',type=Path);ap.add_argument('--zip-output',type=Path)
    ap.add_argument('--publication',type=Path)
    a=ap.parse_args()
    result=repository_projection(a.review,a.audit) if a.projection else package(a.review,a.context,a.zip_output,a.audit,read(a.publication) if a.publication else None)
    import json
    print(json.dumps(result,indent=2))
