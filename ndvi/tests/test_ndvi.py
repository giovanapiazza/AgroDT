import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class NDVITest(unittest.TestCase):
 def test_math(self):
  ndvi=app.calculate_ndvi(np.array([[100.,0.]]),np.array([[300.,0.]]))
  self.assertAlmostEqual(float(ndvi[0,0]),0.5)
  self.assertTrue(np.isnan(ndvi[0,1]))
 def test_shape(self):
  with self.assertRaises(ValueError):app.calculate_ndvi(np.zeros((1,2)),np.zeros((2,1)))
 def test_region(self):
  x=np.full((30,30),0.7,dtype=np.float32);x[5:15,5:15]=0.3
  r,_,_,_=app.detect_regions(x)
  self.assertEqual(len(r),1);self.assertEqual(r[0]['pixels'],100)
 def test_path(self):
  with self.assertRaises(ValueError):app.safe_id('../x','id')
if __name__=='__main__':unittest.main()
