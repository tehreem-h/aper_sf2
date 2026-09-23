# Written by Paolo Serra
# Edited for Apertif by Kelley Hess

import subprocess
import sys
from astropy.io import fits
import os
import numpy as np


def Run(command, verb1=1, verb2=0, getout=0):
    if verb1:
        print('    '+command)
    result = subprocess.check_output(command.split())
    if verb2:
        for jj in result:
            print(jj)
    if getout:
        return result


incube = sys.argv[1]
preGridMask = sys.argv[2]

print('  Reprojecting mask {} to the WCS grid of cube {}.'.format(preGridMask, incube))

with fits.open(incube) as cube:
    cubehead = cube[0].header

beam = incube.split('_')[1][-2:]
beam = incube.split('/')[-1].split('_')[1][-2:]
postGridMask = preGridMask.replace('.fits', '{}_regrid.fits'.format(beam))
field_dir = '/'.join(incube.split('/')[:-1])+'/'

'''
MAKE HDR FILE FOR REGRIDDING THE USER SUPPLIED MASK AND REPROJECT
'''
with open(field_dir + 'tmp' + str(beam) + '.hdr', 'w') as file:
    file.write('SIMPLE  =   T\n')
    file.write('BITPIX  =   -64\n')
    file.write('NAXIS   =   2\n')
    file.write('NAXIS1  =   {}\n'.format(cubehead['naxis1']))
    file.write('CTYPE1  =   \'RA---SIN\'\n')
    file.write('CRVAL1  =   {}\n'.format(cubehead['crval1']))
    file.write('CRPIX1  =   {}\n'.format(cubehead['crpix1']))
    file.write('CDELT1  =   {}\n'.format(cubehead['cdelt1']))
    file.write('NAXIS2  =   {}\n'.format(cubehead['naxis2']))
    file.write('CTYPE2  =   \'DEC--SIN\'\n')
    file.write('CRVAL2  =   {}\n'.format(cubehead['crval2']))
    file.write('CRPIX2  =   {}\n'.format(cubehead['crpix2']))
    file.write('CDELT2  =   {}\n'.format(cubehead['cdelt2']))
    file.write('EXTEND  =   T\n')
    file.write('EQUINOX =   2000.0\n')
    file.write('END\n')

if os.path.exists('{}'.format(postGridMask)):
    os.remove('{}'.format(postGridMask))


with fits.open('{}'.format(preGridMask)) as hdul:

    ax3param = []
    for key in ['NAXIS3', 'CTYPE3', 'CRPIX3', 'CRVAL3', 'CDELT3']:
        ax3param.append(hdul[0].header[key])

    if np.amax(hdul[0].data) > 1:
        mask = np.where(hdul[0].data > 0)
        hdul[0].data[mask] = 1
        preGridMaskNew = preGridMask.replace('.fits', '_01.fits')
        hdul.writeto('{}'.format(preGridMaskNew), overwrite=True)
        preGridMask = preGridMaskNew

Run('mProjectCube {} {} {}tmp{}.hdr'.format(preGridMask, postGridMask, field_dir, beam))

if not os.path.exists('{}'.format(postGridMask)):
    raise IOError(
        "The regridded mask {0:s} does not exist. The original mask likely has no overlap with the cube.".format(postGridMask))

with fits.open('{}'.format(postGridMask), mode='update') as hdul:
    for i, key in enumerate(['NAXIS3', 'CTYPE3', 'CRPIX3', 'CRVAL3', 'CDELT3']):
        hdul[0].header[key] = ax3param[i]
    axDict = {'1': [2, cubehead['naxis1']],
              '2': [1, cubehead['naxis2']]}

    for i in ['1', '2']:
        cent, nax = hdul[0].header['CRPIX'+i], hdul[0].header['NAXIS'+i]
        if cent < axDict[i][1]/2+1:
            delt = int(axDict[i][1]/2+1 - cent)
            if i == '1':
                toAdd = np.zeros([hdul[0].header['NAXIS3'], hdul[0].data.shape[1], delt])
            else:
                toAdd = np.zeros([hdul[0].header['NAXIS3'], delt, hdul[0].data.shape[2]])
            hdul[0].data = np.concatenate([toAdd, hdul[0].data], axis=axDict[i][0])
            hdul[0].header['CRPIX'+i] = cent + delt
        if hdul[0].data.shape[axDict[i][0]] < axDict[i][1]:
            delt = int(axDict[i][1] - hdul[0].data.shape[axDict[i][0]])
            if i == '1':
                toAdd = np.zeros([hdul[0].header['NAXIS3'], hdul[0].data.shape[1], delt])
            else:
                toAdd = np.zeros([hdul[0].header['NAXIS3'], delt, hdul[0].data.shape[2]])
            hdul[0].data = np.concatenate([hdul[0].data, toAdd], axis=axDict[i][0])
        if hdul[0].data.shape[axDict[i][0]] > axDict[i][1]:
            delt = int(hdul[0].data.shape[axDict[i][0]] - axDict[i][1])
            hdul[0].data = hdul[0].data[:, :, -delt] if i == '1' else hdul[0].data[:, -delt, :]
            if cent > axDict[i][1]/2+1:
                hdul[0].header['CRPIX'+i] = hdul[0].data.shape[axDict[i][0]]/2+1

    # Add a single pixel to every channel so every channel is cleaned (matched edits in ../clean2.py)
    hdul[0].data[:,0,0] = 1.0
    hdul[0].data = np.around(hdul[0].data.astype(np.float32)).astype(np.int16)
    try:
        del hdul[0].header['EN']
    except KeyError:
        pass
    hdul.flush()

print('  Reprojected mask {} written to disc'.format(postGridMask))
print('  Cleaning up temporary files')
try:
    os.remove(preGridMaskNew)
except:
    pass
os.remove(postGridMask.replace('_regrid.fits', '_regrid_area.fits'))
os.remove(field_dir + 'tmp' + str(beam) + '.hdr')
