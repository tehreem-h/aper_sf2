import os

from argparse import ArgumentParser, RawTextHelpFormatter
import astropy.io.fits as pyfits
import numpy as np

from contextlib import closing
from multiprocessing import Pool, cpu_count
from tqdm.auto import trange
import time

from apercal.libs import lib
from apercal.subs import managefiles
import apercal


def run(i):
    global new_smoothcube_data

    try:
        imsub.in_ = 'map_{:02}_00'.format(b)
        imsub.out =  'map_{:02}_00_'.format(b) + str(chan[i]).zfill(4)
        imsub.region = '"images({})"'.format(chan[i] + 1)
        imsub.go()
    except RuntimeError:
        print("\tProblems reading in map data for channel {}.".format(chan[i]))
        return 'OK'

    # Add the header parameters to the file before convolution...
    try:
        puthd.in_ = 'map_{:02}_00_{:04}/bmaj'.format(b, chan[i])
        puthd.value = '{},degrees'.format(float(bmaj[i]))
        puthd.go()
        puthd.in_ = 'map_{:02}_00_{:04}/bmin'.format(b, chan[i])
        puthd.value = '{},degrees'.format(float(bmin[i]))
        puthd.go()
        puthd.in_ = 'map_{:02}_00_{:04}/bpa'.format(b, chan[i])
        puthd.value = '{},degrees'.format(float(bpa[i]))
        puthd.go()
    except:
        print("\tProblems writing beam information to header for channel {}.".format(chan[i]))
        return

    try:
        # print("[SMOOTH_WA2] Convolving to target resolution of {} arcseconds".format(new_beam)
        convol.map = 'map_{:02}_00_'.format(b) + str(chan[i]).zfill(4)
        convol.fwhm = 40.
        convol.pa = 0.
        convol.out = 'smooth_{:02}_00_'.format(b) + str(chan[i]).zfill(4)
        convol.options = 'final'
        convol.go()
        bmaj[i] = 40./3600.
        bmin[i] =40./3600.
        bpa[i] = 0.0
    except RuntimeError:
        print("\tProblems CONVOLVEing data for channel {}.".format(chan[i]))
        os.system('cp -r map_{:02}_00_{:04} smooth_{:02}_00_{:04}'.format(b,chan[i],b,chan[i]))

    try:
        fits.op = 'xyout'
        fits.in_ = 'smooth_{:02}_00_{:04}'.format(b, chan[i])
        fits.out = 'smooth_{:02}_00_{:04}.fits'.format(b, chan[i])
        fits.go()
    except RuntimeError:
        print("Problems writing data to FITS for channel {}. Check miriad files instead.".format(chan[i]))

    try:
        smooth_im = pyfits.getdata('smooth_{:02}_00_{:04}.fits'.format(b, chan[i]))
    except IOError:
        print("Miraid image file doesn't exist (all nan's?), but map does, so make a dummy nan channel.")
        smooth_im = np.nan
    except RuntimeError:
        print("Couldn't add some channel to new cube because of above errors. Continue to next.".format(chan[i]))

    return smooth_im


###################################################################

parser = ArgumentParser(description="Do source finding in the HI spectral line cubes for a given taskid,"
                                    " beam, cubes", formatter_class=RawTextHelpFormatter)

parser.add_argument('-t', '--taskid', default='190915041',
                    help='Specify the input taskid or field (default: %(default)s).')

parser.add_argument('-b', '--beams', default='0-39',
                    help='Specify a range (0-39) or list (3,5,7,11) of beams on which to do source finding'
                         ' (default: %(default)s).')

parser.add_argument('-c', '--cubes', default='1,2,3',
                    help='Specify the cubes on which to do source finding (default: %(default)s).')

parser.add_argument('-o', "--overwrite",
                    help="If option is included, overwrite old clean, model, and residual FITS files.",
                    action='store_true')

parser.add_argument('-j', "--njobs",
                    help="Number of jobs to run in parallel (default: %(default)s) tested on happili-05.",
                    default=18)

parser.add_argument('-d', '--directory', default='', required=False,
                    help='Specify the directory where taskid/field folders live containing the data (default: %(default)s).')

# Parse the arguments above
args = parser.parse_args()
njobs = int(args.njobs)

###################################################################

# Range of cubes/beams to work on:
taskid = args.taskid
cubes = [int(c) for c in args.cubes.split(',')]

if '-' in args.beams:
    b_range = args.beams.split('-')
    beams = np.array(range(int(b_range[1])-int(b_range[0])+1)) + int(b_range[0])
else:
    beams = [int(b) for b in args.beams.split(',')]

overwrite = args.overwrite

prepare = apercal.prepare()
managefiles.director(prepare, 'ch', args.directory+'/'+taskid)

for b in beams:

    for c in cubes:
        clean_name = 'HI_B0{:02}_cube{}_spline_clean_image'.format(b, c)
        smooth_name = 'HI_B0{:02}_cube{}_spline_clean_smooth_image'.format(b, c)

        clean_fits = clean_name + '.fits'
        smooth_fits = smooth_name + '.fits'

        if not os.path.isfile(smooth_fits):

            print("[SMOOTH_WA2] Smooth cleaned channels to common psf for Beam {:02}, Cube {}.".format(b, c))
            os.system('cp {} {}'.format(clean_fits, smooth_fits))
            print("\t{}".format(smooth_fits))
            
            if len(pyfits.open(smooth_fits)) == 2:

                new_smoothcube = pyfits.open(smooth_fits, mode='update')
                new_smoothcube_data = new_smoothcube[0].data
                
                chan = new_smoothcube[1].data['CHAN']
                bmaj = new_smoothcube[1].data['BMAJ']
                bmin = new_smoothcube[1].data['BMIN']
                bpa = new_smoothcube[1].data['BPA']
                new_smoothcube.close()

                imsub = lib.miriad('imsub')
                puthd = lib.miriad('puthd')
                convol = lib.miriad('convol')

                fits = lib.miriad('fits')
                fits.in_ = clean_fits
                fits.op = 'xyin'
                fits.out = 'map_{:02}_00'.format(b)
                fits.go()

                ################################################
                # Parallelization of cleaning/restoring
                ncases = len(chan)
                print(" - " + str(ncases) + " cases found")

                if njobs > 1:
                    print(" - Running in parallel mode (" + str(njobs) + " jobs simultaneously)")
                elif njobs == 1:
                    print(" - Running in serial mode")
                else:
                    print("[ERROR] invalid number of NJOBS. Please use a positive number.")
                    exit()

                # Managing the work PARALLEL or SERIAL accordingly
                if njobs > cpu_count():
                    print(
                        "  [WARNING] The chosen number of NJOBS seems to be larger than the number of CPUs in the system!")

                tic1 = time.time()
                with closing(Pool(processes=njobs)) as pool:
                    smooth_out = np.array(list(pool.imap(run, trange(ncases), chunksize=1)))
                    pool.terminate()
                toc1 = time.time()
                print("[SMOOTH_WA3] Time to actually do smoothing: {:0.4f} seconds".format(toc1 - tic1))
		
                # Write the cleaned data to file
                for i in range(ncases):
                    new_smoothcube_data[chan[i],:,:] = smooth_out[i]
                
                # Updating the clean file with the new data
                print(" - Updating the clean file")
                new_smoothcube = pyfits.open(smooth_fits, mode='update')
                new_smoothcube[0].data = new_smoothcube_data

                ################################################

                new_smoothcube[0].header['HISTORY'] = 'Individual images reassembled using aper_sf2/smooth_wa.py by KMHess'

                print("[SMOOTH_WA2] Updating median clean beam properties to primary header.")
                med_bmaj, med_bmin, med_bpa = np.median(bmaj), np.median(bmin), np.median(bpa)
                if len(chan) > 0:
                    new_smoothcube[0].header.set('BMAJ', med_bmaj, 'median clean beam bmaj')
                    new_smoothcube[0].header.set('BMIN', med_bmin, 'median clean beam bmin')
                    new_smoothcube[0].header.set('BPA', med_bpa, 'median clean beam pa')

                    print("[SMOOTH_WA2] Updating channel clean beam properties to BEAMS extension table.")
                    new_smoothcube[1].data['BMAJ'][:] = bmaj
                    new_smoothcube[1].data['BMIN'][:] = bmin
                    new_smoothcube[1].data['BPA'][:] = bpa
                else:
                    print("[SMOOTH_WA2] No channels cleaned; no beam info being written to header.")

                print(" - Saving the new clean file")
                new_smoothcube.flush()

                # Closing files
                print(" - Closing files")
                new_smoothcube.close()

                # Clean up extra Miriad files
                os.system('rm -rf map_'+str(b).zfill(2) + '* smooth_'+str(b).zfill(2) + '*')

            else:
                print("No beam extension for this file: no sources in cube or not cleaned?")
        
        else:
            print("No clean cube? or already smoothed.")

    
print("[SMOOTH_WA2] Done.\n")
