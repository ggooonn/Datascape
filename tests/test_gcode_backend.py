import unittest
from datascape.gcode import Point,Stroke,Panel,PANELS,clip_stroke,plan,preview_gcode,schedule


def S(sid,xy,**kw):
    return Stroke(stroke_id=sid,points=tuple(Point(*p) for p in xy),layer='A',color_slot='INK',medium='ink',**kw)


class PlotterBackendTests(unittest.TestCase):
    def test_crossing_without_internal_vertices(self):
        s=S('s1',[(-50,100,.2),(650,100,.8)])
        for panel in PANELS:
            out=clip_stroke(s,panel)
            self.assertEqual(len(out),1)
            self.assertEqual(out[0].origin_id,'s1')
            self.assertAlmostEqual(out[0].points[0].x,panel.x_min)
            self.assertAlmostEqual(out[0].points[-1].x,panel.x_max)
        self.assertAlmostEqual(clip_stroke(s,PANELS[0])[0].points[-1].pressure,.5)
        self.assertAlmostEqual(clip_stroke(s,PANELS[1])[0].points[0].pressure,.5)

    def test_polyline_crosses_and_returns(self):
        s=S('s2',[(-10,10,.5),(20,10,.5),(40,10,.5),(120,10,.5)])
        out=clip_stroke(s,Panel('small',0,30,0,20))
        self.assertEqual(len(out),1)
        self.assertEqual([p.x for p in out[0].points],[0,20,30])

    def test_crossing_reenter_disconnected(self):
        s=S('s2',[(-5,5,.5),(15,5,.5),(-5,25,.5),(15,25,.5)])
        out=clip_stroke(s,Panel('small',0,10,0,30))
        self.assertEqual(len(out),3)

    def test_determinism_and_preservation(self):
        s1=S('s1',[(100,10,.2),(330,30,.7)],order_group=2,sequence=3)
        s2=S('s2',[(10,40,.5),(20,50,.5)],order_group=0,sequence=0)
        a,b=plan((s1,s2),PANELS[0],medium='ink')
        self.assertEqual((a,b),plan((s1,s2),PANELS[0],medium='ink'))
        self.assertEqual(b[0].origin_id,'s2')
        self.assertTrue(a[0].z>0)
        self.assertTrue(any(m.z<0 for m in a))

    def test_preview_is_comment_only(self):
        s=S('s1',[(50,50,.5),(100,50,1.)])
        motions,_=plan((s,),PANELS[0])
        lines=preview_gcode(motions,PANELS[0]).splitlines()
        self.assertFalse(any(l.startswith(('G0','G1','G21','G90')) for l in lines))
        self.assertTrue(any('Z-12.000' in l for l in lines))

    def test_reorder_preserves_locked_strokes(self):
        a=S('a',[(0,0,.5),(10,0,.5)],sequence=1)
        b=S('b',[(20,0,.5),(30,0,.5)],sequence=2,reorderable=True)
        c=S('c',[(40,0,.5),(50,0,.5)],sequence=3)
        self.assertEqual([s.stroke_id for s in schedule((c,b,a))],['a','b','c'])

    def test_reject_dot(self):
        with self.assertRaises(ValueError):S('dot',[(1,1,.5)])


if __name__=='__main__':
    unittest.main()
