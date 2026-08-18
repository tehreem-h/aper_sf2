#script to make empty mask_bin_dil for fields with no sources
from astropy.io import fits
import sys
import numpy as np

incube = sys.argv[1]
in_img = fits.open(incube)
in_data = in_img[0].data

hdr = in_img[0].header
data = np.zeros(in_data.shape)
data[:,0,0] = 1.0

hdu = fits.PrimaryHDU(data=data, header=hdr)

DATA = '/'.join(incube.split('/')[:-2])
FIELD = incube.split('/')[-2]
CUBE = incube.split('/')[-1].split('_')[-2][-1]
bm = incube.split('/')[-1].split('_')[1][2:]

out_name = DATA+"/mos_"+FIELD+"/"+FIELD+"_HIcube"+CUBE+"_image_sofiaFS_mask_bin_dil"+bm+"_regrid.fits"

hdu.writeto(out_name, overwrite=True)
