import os

from argparse import ArgumentParser, RawTextHelpFormatter

from astropy.io import fits
import numpy as np
from scipy import ndimage

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
    global dilmask

    # try:

    tmpmask = data[i, :, :] > threshold * np.nanstd(data[i, :, :])
    dilmask[i, :, :] = ndimage.binary_dilation(mask[i, :, :], mask=tmpmask, iterations=iters).astype(data.dtype)

    #     return 'OK'
    #
    # except Exception:
    #     print("[ERROR] Something went wrong with the Spline fitting [" + str(i) + "]")
    #     return np.nan

###################################################################

# def parse_args():
parser = ArgumentParser(description="Dilate a 2d binary mask including just the objects to be cleaned.",
                        formatter_class=RawTextHelpFormatter)

# parser.add_argument('-l', '--loc', default='output/',
#                     help='Specify the input working directory relative to where you\'re running.'
#                          ' Important for mosaic. (default: %(default)s).')

parser.add_argument('-t', '--taskid', default='190915041', required=True,
                    help='Specify the input taskid or field (default: %(default)s).')

parser.add_argument('-c', '--cubes', default='1,2,3', required=True,
                    help='Specify the cubes on which to do source finding (default: %(default)s).')

parser.add_argument('-r', '--threshold', default='1.0', type=float,
                    help='Specify the sigma threshold for mask dilation (default: %(default)s).')

parser.add_argument('-i', '--iterations', default='3', type=int,
                    help='Specify the number of iterations for mask dilation (default: %(default)s).')

parser.add_argument('-j', "--njobs", default=18, type=int,
                    help="Number of jobs to run in parallel (default: %(default)s) tested on happili-05.")

parser.add_argument('-f', "--filename", default=None,
                    help="If provided, override default naming scheme for taskid/beam/cube.")

parser.add_argument('-s', "--suffix", default='new',
                    help="Only relevant when filename is provided. Optional suffix for new file.")

parser.add_argument('-d', '--directory', default='', required=False,
                    help='Specify the directory where taskid/field folders live containing the data (default: %(default)s).')


# Parse the arguments above
args = parser.parse_args()
    # return args

###################################################################


# def binary_mask(taskid, cubes, sources, njobs):

taskid = args.taskid
cubes = args.cubes
njobs = np.max([args.njobs-1, 1])  # If only one core, force serial mode (also for 2 cores, oh well)
filename = args.filename
suffix = '_' + args.suffix
threshold = args.threshold
iters = int(args.iterations)
d = args.directory

loc = d + '/mos_' + taskid + '/'

for c in cubes:
    cube_name = taskid + '_HIcube' + str(c) + '_image'

    if not filename:
        bin_mask_file = loc + cube_name + '_sofiaFS_mask_bin.fits'
        dilat_mask_file = loc + cube_name + '_sofiaFS_mask_bin_dil.fits'
        print("[DILATE_BINMASK] Dilating {} binary mask.".format(taskid))
    else:
        bin_mask_file = filename
        dilat_mask_file = loc + filename[:-5].split("/")[-1] + '{}.fits'.format(suffix)
        print("[DILATE_BINMASK] Dilating {} binary mask.".format(filename))

    mask_hdu = fits.open(bin_mask_file, mode='update')
    mask = mask_hdu[0].data

    os.system('cp {} {}'.format(bin_mask_file, dilat_mask_file))
    dilmask_hdu = fits.open(dilat_mask_file, mode='update')
    dilmask = dilmask_hdu[0].data

    if not filename:
        # Normal operations, dilation is done before cleaning
        data_hdu = fits.open(loc + cube_name + '.fits')
        data = data_hdu[0].data
    else:
        # For smoothed data; it's already been cleaned
        data_hdu = fits.open(loc + cube_name[:-6] + '_clean_smooth_image.fits')
        data = data_hdu[0].data

    # Define number of cases
    ncases = data.shape[0]
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

    dilmask_hdu.data = dilmask

    dilmask_hdu.flush()
    dilmask_hdu.close()

    data_hdu.close()

# if __name__ == '__main__':
#     arguments = parse_args()
#     taskid = arguments.taskid
#     cubes = arguments.cubes
#     njobs = arguments.njobs
#
#     loc = 'mos_' + taskid + '/'                               # Enable while using snakemake
#     binary_mask(taskid, cubes, sources=arguments.sources, njobs=njobs)
