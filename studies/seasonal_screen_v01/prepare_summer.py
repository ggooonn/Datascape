"""Prepare immutable-reference Summer fields for the new foreground study."""
from common import *
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--master',required=True);p.add_argument('--vegetation',required=True);p.add_argument('--cache',required=True);a=p.parse_args()
    c=read(ROOT/'studies/summer_scene_v01/config.json');scene=read(BASE/'C_east_scene.json')
    f=cache_fields(a.master,a.vegetation,scene,'summer',c['seed'],a.cache)
    print('Read-only Summer fields ready; occupied',int(f['base']['occupied'].sum()))
