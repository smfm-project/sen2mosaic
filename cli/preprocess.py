#!/usr/bin/env python

import argparse
import functools
import numpy as np
import os

import sen2mosaic.core
import sen2mosaic.multiprocess
import sen2mosaic.preprocess

import pdb

####################################################################
### Command line interface for preprocessing Sentinel-2 L1C data ###
####################################################################

def main(infile, gipp = None, output_dir = os.getcwd(), resolution = 0, sen2cor = 'L2A_Process', sen2cor_255 = None, verbose = False):
    """
    Function to initiate sen2cor on level 1C Sentinel-2 files and perform improvements to cloud masking. This is the function that is initiated from the command line.
    
    Args:
        infile: A Level 1C Sentinel-2 .SAFE file.
        gipp: Optionally specify a copy of the L2A_GIPP.xml file in order to tweak options.
        output_dir: Optionally specify an output directory. The option gipp must also be specified if you use this option.
    """
    
    assert resolution in [0, 10, 20, 60], "Resolution must be set to 0, 10, 20 or 60 m."
    
    resolutions = [resolution] if resolution != 0 else [10, 20, 60]
    
    if verbose: print('Processing %s'%infile.split('/')[-1])
    
    try:
        
        # Loop through all resolutions if set to 0
        for resolution in resolutions:
            
            S2_scene = sen2mosaic.core.LoadScene(infile, resolution = resolution)
            
            L2A_file = S2_scene.processToL2A(gipp = gipp, output_dir = output_dir, resolution = resolution, sen2cor = sen2cor, sen2cor_255 = sen2cor_255, verbose = verbose)
    
    except Exception as e:
        raise
                
    # Test for completion, and report back
    if sen2mosaic.preprocess.testCompletion(infile, output_dir = output_dir, resolution = resolution) == False:   
        
        print('WARNING: %s did not complete processing at %s m resolution.'%(infile, str(resolution)))
    

if __name__ == '__main__':
    '''
    '''
        
    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to level 2A. This script initiates sen2cor, which performs atmospheric correction and generate a cloud mask. This script also performs simple improvements to the cloud mask.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    positional = parser.add_argument_group('Positional arguments')
    optional = parser.add_argument_group('Optional arguments')
    
    # Required arguments
    
    # Optional arguments
    positional.add_argument('infiles', metavar = 'L1C_FILES', type = str, default = [os.getcwd()], nargs = '*', help = 'Sentinel 2 input files (level 1C) in .SAFE format. Specify one or more valid Sentinel-2 .SAFE, a directory containing .SAFE files, a Sentinel-2 tile or multiple granules through wildcards (e.g. *.SAFE/GRANULE/*), or a file containing a list of input files. Leave blank to process files in current working directoy. All granules that match input conditions will be atmospherically corrected.')
    optional.add_argument('-t', '--tile', type = str, default = '', help = 'Specify a specific Sentinel-2 tile to process. If omitted, all tiles in L1C_FILES will be processed.')
    optional.add_argument('-g', '--gipp', type = str, default = None, help = 'optionally specify a custom L2A_Process settings file.')
    optional.add_argument('-o', '--output_dir', type = str, metavar = 'DIR', default = os.getcwd(), help = "Specify a directory to output level 2A files. If not specified, atmospherically corrected images will be written to the same directory as input files.")
    optional.add_argument('-res', '--resolution', type = int, metavar = '10/20/60', default = 0, help = "Process only one of the Sentinel-2 resolutions, with options of 10, 20, or 60 m. Defaults to processing all three. N.B It is not currently possible to only the 10 m resolution, an input of 10 m will instead process all resolutions.")
    optional.add_argument('-s', '--sen2cor', type = str, metavar = 'PATH', default = 'L2A_Process', help = "Path to sen2cor (v2.8), if not callable with the default 'L2A_Process'.")
    optional.add_argument('-s255', '--sen2cor255', type = str, metavar = 'PATH', default = None, help = "Path to sen2cor (v2.5.5), required if processing Sentinel-2 data with the old file format.")
    optional.add_argument('-p', '--n_processes', type = int, metavar = 'N', default = 1, help = "Specify a maximum number of tiles to process in paralell. Bear in mind that more processes will require more memory. Defaults to 1.")
    optional.add_argument('-v', '--verbose', action='store_true', default = False, help = "Make script verbose.")
    
    # Get arguments
    args = parser.parse_args()
        
    # Get all infiles that match tile and file pattern
    infiles = sen2mosaic.IO.prepInfiles(args.infiles, '1C', tile = args.tile)
     
    # Get absolute path for output directory
    args.output_dir = os.path.abspath(args.output_dir)
    
    # Strip the output files already exist.
    for infile in infiles[:]:
        outpath = sen2mosaic.preprocess.getL2AFilename(infile, output_dir = args.output_dir)
        
        if os.path.exists(outpath):
            print('WARNING: The output file %s already exists! Skipping file.'%outpath)
    
    if len(infiles) == 0: raise ValueError('No level 1C Sentinel-2 files detected in input directory that match specification.')
        
    if args.n_processes == 1:
        
        # Keep things simple when using one processor
        for infile in infiles:
            
            main(infile, gipp = args.gipp, output_dir = args.output_dir, resolution = args.resolution, sen2cor = args.sen2cor, sen2cor_255 = args.sen2cor255, verbose = args.verbose) 
    
    else:

        # Set up function with multiple arguments, and run in parallel
        main_partial = functools.partial(main, gipp = args.gipp, output_dir = args.output_dir, resolution = args.resolution, sen2cor = args.sen2cor, sen2cor_255 = args.sen2cor255, verbose = args.verbose)
    
        sen2mosaic.multiprocess.runWorkers(main_partial, args.n_processes, infiles)
    
    # Test for completion
    completion = np.array([sen2mosaic.preprocess.testCompletion(infile, output_dir = args.output_dir, resolution = args.resolution) for infile in infiles])
    
    # Report back
    if completion.sum() > 0: print('Successfully processed files:')
    for infile in np.array(infiles)[completion == True]:
        print(infile)
    if (completion == False).sum() > 0: print('Files that failed:')
    for infile in np.array(infiles)[completion == False]:
        print(infile)

    
    

