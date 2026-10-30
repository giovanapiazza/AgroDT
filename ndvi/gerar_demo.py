#!/usr/bin/env python3
"""Somente para teste: cria par RED/NIR SINTETICO."""
from pathlib import Path
import numpy as np
from PIL import Image
import argparse
p=argparse.ArgumentParser();p.add_argument('--saida',default='data/demo');a=p.parse_args()
h,w=240,320;y,x=np.indices((h,w))
red=np.full((h,w),9000,dtype=np.uint16);nir=np.full((h,w),51000,dtype=np.uint16)
area=(x-w//2)**2+(y-h//2)**2<55**2
red[area]=22000;nir[area]=41000
out=Path(a.saida);out.mkdir(parents=True,exist_ok=True)
Image.fromarray(red).save(out/'red.png');Image.fromarray(nir).save(out/'nir.png')
print('Arquivos:',out/'red.png',out/'nir.png')
