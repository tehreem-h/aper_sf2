"""
Updated by TNH 06/2026 to be used in Finalmake for file clean up.

Usage:
python3 compress_cleanup.py DATA FIELD CUBE
e.g., python3 compress_cleanup.py /project/apdw/Data S1044+5815 3
"""

from glob import glob
import os, sys

def compress_clean(DATA, FIELD, CUBE):
    #files to remove
    field_pb = glob(DATA+"/"+FIELD+"/HI_B0*_cube"+CUBE+"_pb.fits")
    field_spline = glob(DATA+"/"+FIELD+"/HI_B0*_cube"+CUBE+"_spline.fits")
    field_spline_clpb = glob(DATA+"/"+FIELD+"/HI_B0*_cube"+CUBE+"_spline_clean_pb.fits")
    field_spline_clsmpb = glob(DATA+"/"+FIELD+"/HI_B0*_cube"+CUBE+"_spline_clean_smooth_pb.fits")
    mos_filt = glob(DATA+"/mos_"+FIELD+"/*cube"+CUBE+"*filtered.fits")
    mos_filtspline = glob(DATA+"/mos_"+FIELD+"/*cube"+CUBE+"*filtered_spline.fits")
    mos_bin = glob(DATA+"/mos_"+FIELD+"/*cube"+CUBE+"*bin*")

    for group in [field_pb, field_spline, field_spline_clpb,field_spline_clsmpb, mos_filt, mos_filtspline, mos_bin]:
        for a in group:
            if os.path.isfile(a):
                os.system('rm -r {}'.format(a))
                print('rm -r {}'.format(a))


    weights_cubes = glob(DATA+'/mos_'+FIELD+'/*cube'+CUBE+'*weights.fits')
    noise_cubes = glob(DATA+'/mos_'+FIELD+'/*cube'+CUBE+'*noise.fits')
    mask_cubes = glob(DATA+'/mos_'+FIELD+'/*cube'+CUBE+'*mask.fits')

    for w in weights_cubes:
        if not os.path.isfile(w + '.fz') & os.path.isfile(w):
            os.system('fpack {}'.format(w))
            print('fpack {}'.format(w))
        if os.path.isfile(w + '.fz') & os.path.isfile(w):
            os.system('rm -r {}'.format(w))
            print('rm -r {}'.format(w))

    for n in noise_cubes:
        if not os.path.isfile(n + '.fz') & os.path.isfile(n):
            os.system('fpack {}'.format(n))
            print('fpack {}'.format(n))
        if os.path.isfile(n + '.fz') & os.path.isfile(n):
            os.system('rm -r {}'.format(n))
            print('rm -r {}'.format(n))

    for m in mask_cubes:
        if not os.path.isfile(m + '.fz') & os.path.isfile(m):
            os.system('fpack {}'.format(m))
            print('fpack {}'.format(m))
        if os.path.isfile(m + '.fz') & os.path.isfile(m):
            os.system('rm -r {}'.format(m))
            print('rm -r {}'.format(m))

if __name__ == "__main__":
    DATA = str(sys.argv[1])
    FIELD = str(sys.argv[2])
    CUBE = str(sys.argv[3])

    compress_clean(DATA, FIELD, CUBE)

    print("Compression and clean up done!")
