"""Selective terrain support must not override predecessors or duplicate sources."""
import unittest
from benchmarks.integrated_330_v01 import spring_fine_terrain as t
from benchmarks.integrated_330_v01 import spring_physical_ink as s

class FineTerrainTests(unittest.TestCase):
    def row(self,i,**kw):
        d=dict(index=i,source_id=str(i),classification='main',family='Soil',role='integration-contact-support',depth_band='near',length_mm=8,owner=str(i),xy_mm=[[400+i*20,750],[405+i*20,750]])
        d.update(kw);return d
    def test_blocked_main_predecessor_is_not_reassigned(self):
        r=[self.row(0),self.row(1)]
        chosen,review=t.choose(r,[(0,1)],s.read(t.POLICY))
        self.assertNotIn(0,chosen);self.assertIn(1,chosen)
        self.assertIn('successor',review[0]['reason'])
    def test_far_and_principal_rock_remain_main(self):
        rows=[self.row(0,depth_band='far'),self.row(1,family='rock',role='ink-contour')]
        chosen,_=t.choose(rows,[],s.read(t.POLICY));self.assertFalse(chosen)
    def test_caps_spacing_and_owner_are_enforced(self):
        rows=[self.row(i,owner='same') for i in range(5)]
        chosen,_=t.choose(rows,[],s.read(t.POLICY));self.assertLessEqual(len(chosen),2)
    def test_chain_projection_through_deferred_source(self):
        records=[self.row(0),self.row(1,classification='color'),self.row(2)]
        chosen,_=t.choose(records,[(0,1),(1,2)],s.read(t.POLICY));self.assertNotIn(0,chosen)
    def test_terrain_A_preserved_as_main(self):
        chosen,review=t.choose([self.row(0,family='A')],[],s.read(t.POLICY));self.assertFalse(chosen)
        self.assertIn('principal',review[0]['reason'])

if __name__=='__main__':unittest.main()
