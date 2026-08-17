import os

from argparse import ArgumentParser, RawTextHelpFormatter
import time as testtime

from astropy.io import ascii, fits
import numpy as np

from multiprocessing import Queue, Process, cpu_count
from tqdm.auto import trange


def worker(inQueue, outQueue):

    """
    Defines the worker process of the parallelisation with multiprocessing.Queue
    and multiprocessing.Process.
    """
    for i in iter(inQueue.get, 'STOP'):

        status = run(i)

        outQueue.put(( status ))

def run(i):
    global mask2d, mask

    try:
        mask_lin = mask[:, y[i], x[i]]
        bin_mask_lin = np.array([1 if m in sources else 0 for m in mask_lin])
        mask2d[y[i], x[i]] = np.nanmax(bin_mask_lin)
        mask[:, y[i], x[i]] = bin_mask_lin
        return 'OK'

    except Exception:
        print("[ERROR] Something went wrong with the binary masking [" + str(i) + "]")
        return np.nan

###################################################################

# def parse_args():
parser = ArgumentParser(description="Make a 2d binary mask including just the objects to be cleaned."
                                    " Useful to detect which cubes should be regridded & cleaned.",
                        formatter_class=RawTextHelpFormatter)

parser.add_argument('-l', '--loc', default='output/',
                    help='Specify the input working directory relative to where you\'re running.'
                         ' Important for mosaic. (default: %(default)s).')

parser.add_argument('-t', '--taskid', default='190915041',
                    help='Specify the input taskid or field (default: %(default)s).')

parser.add_argument('-c', '--cubes', default='1,2,3', required=True,
                    help='Specify the cubes on which to do source finding (default: %(default)s).')

parser.add_argument('-s', '--sources', default='all',
                    help='Specify the sources included in the binary mask.'
                         ' (default: %(default)s).')

parser.add_argument('-j', "--njobs", type=int,
                    help="Number of jobs to run in parallel (default: %(default)s) tested on happili-05.",
                    default=18)

parser.add_argument('-d', '--directory', default='', required=False,
                    help='Specify the directory where taskid/field folders live containing the data (default: %(default)s).')

# Parse the arguments above
args = parser.parse_args()
    # return args

###################################################################


# def binary_mask(taskid, cubes, sources, njobs):

taskid = args.taskid
cubes = args.cubes
sources = args.sources
njobs = np.max([args.njobs-1, 1])  # If only one core, force serial mode (also for 2 cores, oh well)
d = args.directory

loc = d + '/mos_' + taskid + '/'

for c in cubes:
    cube_name = taskid + '_HIcube' + str(c) + '_image'
    # Take modified catalogs based on first inspection of source quality
    catalog_file = loc + cube_name + '_sofiaFS_cat_edit.txt'
    try:#added by TNH 02/16/2026 to generalize to file format without full header
        catalog = ascii.read(catalog_file)
        catalog['id']
    except KeyError:
        catalog = ascii.read(catalog_file, header_start=18)
        catalog['id']

    # Change behavior so 'all' refers to all in catalog, rather than all in image (unedited catalog)
    if sources == 'all':
        sources = np.array(catalog['id'])
    elif '-' in sources:
        mask_range = sources.split('-')
        sources = [int(s + int(mask_range[0])) for s in range(int(mask_range[1]) - int(mask_range[0]) + 1)]
    else:
        sources = [int(s) for s in sources.split(',')]

    mask_file = loc + cube_name + '_sofiaFS_mask.fits'
    bin_mask_file = loc + cube_name + '_sofiaFS_mask_bin.fits'
    mask2d_file = loc + cube_name + '_sofiaFS_mask-2d.fits'
    bin_mask2d_file = loc + cube_name + '_sofiaFS_mask-2d_bin.fits'
    print("[BINARY_MASK] Making {} binary mask including requested sources: {}".format(taskid, sources))

    os.system('cp {} {}'.format(mask2d_file, bin_mask2d_file))
    mask2d_hdu = fits.open(bin_mask2d_file, mode='update')
    mask2d = mask2d_hdu[0].data

    os.system('cp {} {}'.format(mask_file, bin_mask_file))
    mask_hdu = fits.open(bin_mask_file, mode='update')
    mask = mask_hdu[0].data

    # Define what lines of sight need to be kept based on input sources numbers
    print(" - Defining the cases to analyse")
    xx, yy = range(mask2d.shape[1]), range(mask2d.shape[0])
    x, y = np.meshgrid(xx, yy)
    x, y = x.ravel(), y.ravel()
    mask2d_lin = mask2d.ravel()
    # Generalize to allow for overlapping sources by keeping all lines of sight with any object
    # src2d = np.array([True if m in sources else False for m in mask2d_lin])
    src2d = np.array([True if m > 0 else False for m in mask2d_lin])
    x, y, mask2d_lin = x[src2d], y[src2d], mask2d_lin[src2d]
    ncases = len(x)
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

    # Create Queues
    print("    - Creating Queues")
    inQueue = Queue()
    outQueue = Queue()

    # Create worker processes
    print("    - Creating worker processes")
    ps = [Process(target=worker, args=(inQueue, outQueue)) for _ in range(njobs)]

    # Start worker processes
    print("    - Starting worker processes")
    for p in ps: p.start()

    # Fill the queue
    print("    - Filling up the queue")
    for i in trange(ncases):
        inQueue.put((i))

    # Now running the processes
    print("    - Running the processes")
    output = [outQueue.get() for _ in trange(ncases)]

    # Send stop signal to stop iteration
    for _ in range(njobs): inQueue.put('STOP')

    # Stop processes
    print("    - Stopping processes")
    for p in ps: p.join()

    # Updating the Splinecube file with the new data
    print(" - Updating the Mask file")
    # bin_hdu = fits.PrimaryHDU(data=bin_mask2d, header=mask2d_hdu[0].header)
    # bin_hdu.writeto(bin_mask2d_file, overwrite=True)
    mask2d_hdu.data = mask2d
    mask_hdu.data = mask
    mask2d_hdu.flush()
    mask_hdu.flush()

    mask2d_hdu.close()
    mask_hdu.close()

# if __name__ == '__main__':
#     arguments = parse_args()
#     taskid = arguments.taskid
#     cubes = arguments.cubes
#     njobs = arguments.njobs
#
#     loc = 'mos_' + taskid + '/'                               # Enable while using snakemake
#     binary_mask(taskid, cubes, sources=arguments.sources, njobs=njobs)
