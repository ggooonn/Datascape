"""Reproduce retained grammar vectors, without Spring integration or motion."""
from pathlib import Path
import argparse, gzip, json
import yaml
from datascape.vegetation.mid_far import load_evidence, digest
from datascape.vegetation.scale_fields_v05 import Ground, macro_field, micro_field, medium_grove, assemble
from datascape.rendering.mid_far_catalog_support import make_case, preview_svg
from datascape.rendering.spring_checkpoint import verify

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'docs/catalogs/mid_far_vegetation_v05'


def load_config(root=ROOT):
    old = json.loads((root/'configs/experiments/mid_far_vegetation_v02.json').read_text())
    v4 = json.loads((root/'configs/experiments/mid_far_vegetation_v04.json').read_text())
    return {**old, **v4}


def primary_cases(evidence, config, supports):
    return {f'{cid}/clustered/{family}': make_case(supports[cid]['clustered'],
            config['regions'][cid]['mode'], family, config, evidence)
            for cid in ['A','C'] for family in ['R','S','U']}


def historical_v05(evidence, config, supports, *, include_deferred=False):
    """Color-only micro evidence is not the future linked ink/color candidate."""
    cfg = json.loads((ROOT/'configs/experiments/mid_far_vegetation_v05.json').read_text())
    config = {**config, **cfg}
    if not include_deferred:
        ground = Ground(evidence, cfg['regions']['F'])
        raw, visible, ledger = micro_field('F', ground, evidence, config)
        return dict(far_micro_color_evidence=visible, raw=raw, ledger=ledger,
                    linked_ink_color_implemented=False, integration_enabled=False)
    macro=[];micro=[];medium=[]
    for cid,region in cfg['regions'].items():
        ground=Ground(evidence,region)
        _,v,_,_=macro_field(cid,ground,evidence,config);macro+=v
        _,v,_=micro_field(cid,ground,evidence,config);micro+=v
        _,_,_,i,c,_=medium_grove(cid,supports[region['v04_region']]['clustered'],evidence,config);medium+=i+c
    return dict(cases={k:assemble(macro,micro,medium,k) for k in ['A','B','C']},
                status='Historical comparison only; A/C deferred and B far-only candidate',integration_enabled=False)


def write_json(path, value, compressed=False):
    data=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    tmp=path.with_name(path.name+'.pending')
    tmp.write_bytes(gzip.compress(data,mtime=0) if compressed else data)
    json.loads(gzip.decompress(tmp.read_bytes()) if compressed else tmp.read_bytes());tmp.replace(path)


def build(output, include_deferred=False):
    out=Path(output).resolve()
    if ROOT/'outputs' not in out.parents:raise ValueError('Use a fresh directory under repository outputs/')
    if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty new output directory')
    if out==CATALOG or CATALOG in out.parents:raise ValueError('Preserve retained evidence')
    out.mkdir(parents=True,exist_ok=True)
    checkpoint=ROOT/'docs/checkpoints/spring_integration_v04';verify(checkpoint)
    config=load_config();evidence=load_evidence(ROOT,config,checkpoint)
    supports=json.loads((CATALOG/'fixtures/v04_supports.json').read_text())
    cases=primary_cases(evidence,config,supports)
    palette=yaml.safe_load((ROOT/'configs/palettes/palette_20.yaml').read_text())
    for key,case in cases.items():
        cid=key[0];target=out/(key.replace('/','_')+'.svg');tmp=target.with_name(target.name+'.pending')
        tmp.write_text(preview_svg(case['ink'],case['color'],palette,config['regions'][cid]['bounds_mm']))
        import xml.etree.ElementTree as ET
        ET.parse(tmp);tmp.replace(target)
    records={key:{part:case[part] for part in ['raw_ink','raw_color','ink','color']} for key,case in cases.items()}
    write_json(out/'primary_vectors.json.gz',records,True)
    micro=historical_v05(evidence,config,supports)
    write_json(out/'far_micro_color_evidence.json.gz',micro,True)
    if include_deferred:
        write_json(out/'historical_v05_comparison.json.gz',historical_v05(evidence,config,supports,include_deferred=True),True)
    record=dict(status='Grammar replay only; no scene integration or motion',
                primary_vector_digest=digest(records),case_digests={k:digest(v) for k,v in records.items()},
                far_micro_digest=digest(micro['far_micro_color_evidence']),evidence=evidence.provenance)
    write_json(out/'replay_record.json',record);verify(checkpoint)
    print(json.dumps(record,indent=2));return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--include-deferred-v05',action='store_true',help='Historical A/B/C reproduction only; not a recommendation')
    args=parser.parse_args();build(args.output,args.include_deferred_v05)


if __name__=='__main__':main()
