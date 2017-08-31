import os
import glob
import argparse
import time


def main(infiles, output_dir = os.getcwd(), verbose = False):
    '''
    1) Decompresses .zip files where necessary
    2) Processes each file to L2A with sen2cor
    '''
    
    # Where only one file input, it should still be a list for loops
    infiles = list(infiles)
    
    # Unzip all files (-n should prevent overwriting where decompressed .SAFE files already exist)
    for n,this_file in enumerate(infiles):
        if this_file.split('.')[-1] == 'zip':
	    if verbose: print 'Unzipping %s'%this_file
	    os.system('unzip -n %s'%this_file)
	infiles[n] = this_file.replace('.zip','.SAFE') # Infile names are converted to .SAFE files

    # Gets a list of unique infiles, for case where both .zip and .SAFE files included in input file list
    infiles = list(set(infiles))

    # Process each input file
    for this_file in infiles:
        if verbose: 'Running L2A_Process on %s'%this_file
        os.system('L2A_Process %s'%this_file)



if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser()

    # Required arguments
    parser.add_argument('infiles', metavar='N', type=str, nargs='+', help='Sentinel 2 input files (.zip or .SAFE). \
                         Specify a valid S2 input file, multiple files through wildcards, or a directory containing S2 files to be processed to L2A.')

    # Optional arguments
    parser.add_argument('-o', '--output', type=str, default = os.getcwd(), help="Optionally specify an output directory. If nothing specified, downloads will output to the present working directory.")
    parser.add_argument('-v', '--verbose', action='store_true', default = False, help='Do you want the script to speak? Use this flag if so.')

    # Get arguments
    args = parser.parse_args()


    # Keep track of time
    execution_time  = time.time()
    if args.verbose:
        print ' '
        print 'PROCESSING STARTED AT: %s'%time.ctime()

    # Run the script

    main(args.infiles, output_dir = args.output, verbose = args.verbose)

    if args.verbose:
        print ' '
        print 'PROCESSING ENDED AT: %s'%time.ctime()
        print 'TOTAL DURATION: %s minutes'% str(round((time.time() - execution_time)/60.,1))




