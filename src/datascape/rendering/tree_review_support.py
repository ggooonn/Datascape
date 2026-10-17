"""Shared plotting helpers retained for the accepted tree review only."""
import html
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from datascape.vegetation import tree_catalog as tc
matplotlib.rcParams['svg.hashsalt']='datascape-tree-catalog-v02'

def metrics(marks):
    ll=np.array([tc.length(m.xy) for m in marks])
    return {'paths':len(marks),'total_centerline_mm':float(ll.sum()),
            'length_mm_min_p10_median_max':np.quantile(ll,[0,.1,.5,1]).tolist() if len(ll) else [],
            'under_1_2_mm':int((ll<1.2).sum()),
            'under_2_mm':int((ll<2).sum()),
            'parts':{k:sum(m.part==k for m in marks) for k in sorted({m.part for m in marks})},
            'nominal_width_mm_min_max':[min(m.width for m in marks),max(m.width for m in marks)] if marks else []}

def footprint_sheet(out,key,title,subtitle,cells,rows,cols,size=(180,185),page_mm=None):
    """Exact physical-mm constant-width drawing, not nominal pressure profiles."""
    w,h=page_mm if page_mm else (cols*size[0]+20,rows*size[1]+43)
    fig=plt.figure(figsize=(w/25.4,h/25.4),dpi=100,facecolor='white')
    fig.text(10/w,1-10/h,title,fontsize=14,fontweight='bold',color='#253c34',va='top')
    fig.text(10/w,1-22/h,subtitle,fontsize=7.7,color='#68786f',va='top')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">',
         '<rect width="100%" height="100%" fill="white"/>',
         f'<text x="10" y="15" font-family="sans-serif" font-size="5" fill="#253c34">{html.escape(title)}</text>',
         f'<text x="10" y="26" font-family="sans-serif" font-size="2.4" fill="#68786f">{html.escape(subtitle)}</text>']
    for i,c in enumerate(cells):
        row,col=divmod(i,cols);x=10+col*size[0];y=35+row*size[1]
        ax=fig.add_axes([x/w,(h-y-size[1])/h,size[0]/w,size[1]/h]);ax.set(xlim=(0,size[0]),ylim=(size[1],0),aspect='equal');ax.axis('off')
        width=c.get('footprint_mm',.8)
        ax.add_collection(LineCollection([m.xy for m in c['marks']],linewidths=width*72/25.4,colors='#242c28',capstyle='round',joinstyle='round'))
        ax.text(.025,.98,c['title'],transform=ax.transAxes,fontsize=9,fontweight='bold',va='top',color='#253c34')
        ax.text(.025,.925,c.get('note',''),transform=ax.transAxes,fontsize=6.4,va='top',color='#68786f')
        ax.plot([10,20],[size[1]-8]*2,color='#65766e',lw=.5);ax.text(10,size[1]-11,'10 mm',fontsize=6,color='#65766e')
        svg.append(f'<g transform="translate({x} {y})"><g id="ink-cell-{i}" fill="none" stroke="#242c28" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">')
        for m in c['marks']:
            points=' '.join(f'{a:.4f},{b:.4f}' for a,b in m.xy)
            svg.append(f'<polyline points="{points}"/>')
        svg.append('</g>')
        svg.append(f'<text x="4.5" y="7" font-family="sans-serif" font-size="3" fill="#253c34">{html.escape(c["title"])}</text>')
        svg.append(f'<text x="4.5" y="17" font-family="sans-serif" font-size="2.1" fill="#68786f">{html.escape(c.get("note",""))}</text>')
        svg.append(f'<path d="M10,{size[1]-8}h10" fill="none" stroke="#65766e" stroke-width=".15"/><text x="10" y="{size[1]-11}" font-family="sans-serif" font-size="2">10 mm</text></g>')
    fig.savefig(out/f'{key}.png',dpi=100);plt.close(fig)
    svg.append('</svg>');(out/f'{key}.svg').write_text('\n'.join(svg)+'\n')
