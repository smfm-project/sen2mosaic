#!/usr/bin/env python

import argparse
import glob
import os
import re
import shutil
import subprocess

import xml.etree.ElementTree as ET



def getL3AFile(L2A_file, output_dir = os.getcwd(), SAFE = False):
    """
    Determine the level 3A tile path name from an input file (level 2A) tile.
    
    Args:
        L2A_file: Input level 1C .SAFE file tile (e.g. '/PATH/TO/*.SAFE/GRANULE/*').
        output_dir: Directory of processed file.
        SAFE: Return path of base .SAFE file
    Returns:
        The name and directory of the output file
    """
    
    ## PLACEHOLDER, not yet functional.
    
    # Determine output file name, replacing two instances only of substring L1C_ with L2A_
    outfile = '/'.join(L1C_file.split('/')[-3:])[::-1].replace('L1C_'[::-1],'L2A_'[::-1],2)[::-1]
    
    # Replace _OPER_ with _USER_ for case of old file format (in final 2 cases)
    outfile = outfile[::-1].replace('_OPER_'[::-1],'_USER_'[::-1],2)[::-1]
    
    outpath = os.path.join(output_dir, outfile)
    
    # Get outpath of base .SAFE file
    if SAFE: outpath = '/'.join(outpath.split('.SAFE')[:-1]) + '.SAFE'# '/'.join(outpath.split('/')[:-2])
    
    return outpath.rstrip('/')




def processToL3A(input_dir):
    """
    Processes Sentinel-2 level 2A files to level 3A with sen2three.
    
    Args:
        input_dir: Directory containing level 2A Sentinel-2 .SAFE files. Directory must contain files from only one single tile.
    """
    
    # Remove trailing / from input directory if present
    input_dir = input_dir.rstrip('/')   

    # Test that input location contains appropriate files in .SAFE format
    infiles = glob.glob('%s/*_MSIL2A_*.SAFE'%input_dir)
    assert len(infiles) > 0, "Input directory must contain Sentinel-2 level 2A files in .SAFE format."
        
    # Test whether directory contains files from only one tile. Sen2three will process everything in a directory, so this is important
    tiles = [i.split('_')[-2] for i in infiles]
    assert len(list(set(tiles)))==1, "The input directory contains level 2A files from multiple tiles. As sen2Three will process everything in a directory, each tile needs to be placed in its own directory."
    
    # Set up sen2three command
    command = ['L3_Process', input_dir]
    
    # Run sen2three (L3_Process)
    subprocess.call(command)
    
    # Determine output file path
    outpath = glob.glob('%s/*_MSIL03_*.SAFE'%input_dir)[0]
    
    # Tidy up huge .database.h5 files. These files are very large, and aren't subsequently required.
    h5_files = glob.glob('%s/GRANULE/*/IMG_DATA/R*m/.database.h5'%outpath)
    
    for h5_file in h5_files:
        os.remove(h5_file)



def remove2A(input_dir):
    """
    Function to remove all Sentinel-2 level 2A files from a directory. Directory must contain files from only one single tile.
    
    Args:
        input_dir: Directory containing level 2A Sentinel-2 .SAFE files.
    """

    # Remove trailing / from input directory if present
    input_dir = input_dir.rstrip('/')
        
    # Test that input location contains appropriate files in .SAFE format
    infiles = glob.glob('%s/*_MSIL2A_*.SAFE'%input_dir)
    assert len(infiles) > 0, "Input directory must contain level 2A files in .SAFE format."

    # Test whether directory contains files from only one tile. Sen2three will process everything in a directory, so this is important
    tiles = [i.split('_')[-2] for i in infiles]

    assert len(list(set(tiles)))==1, "The input directory contains level 2A files from multiple tiles. L3A.py is hesitant to delete files indiscriminately, so please ensure files from only one tile are present in the directory."
    
    # Delete L2A files
    for this_file in infiles:
        shutil.rmtree(this_file)




def testCompletion(input_dir, output_dir = os.getcwd(), resolution = 0):
    """
    Test for successful completion of sen2three processing.
    
    Args:
        L1C_file: Path to level 1C granule file (e.g. /PATH/TO/*_L1C_*.SAFE/GRANULE/*)
    Returns:
        A boolean describing whether processing completed sucessfully.
    """
    
    ## PLACEHOLDER, not yet functional.
        
    L2A_file = getL2AFile(L1C_file, output_dir = output_dir, SAFE = False)
    
    band_creation_failure = False
    mask_enhancement_failure = False
    
    # Test all expected 10 m files are present
    if resolution == 0 or resolution == 10:
        
        for band in ['B02', 'B03', 'B04', 'B08', 'AOT', 'TCI', 'WVP']:
            
            if not len(glob.glob('%s/IMG_DATA/R10m/*_%s_10m.jp2'%(L2A_file,band))) == 1:
                band_creation_failure = True
    
    # Test all expected 20 m files are present
    if resolution == 0 or resolution == 20:
        
        for band in ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12', 'AOT', 'TCI', 'WVP', 'VIS', 'SCL', 'SCL_old']:
            
            if not len(glob.glob('%s/IMG_DATA/R20m/*_%s_20m.jp2'%(L2A_file,band))) == 1:
                if band == 'SCL' or band == 'SCL_old':
                    mask_enhancement_failure = True
                else:
                    band_creation_failure = True

    # Test all expected 60 m files are present
    if resolution == 0 or resolution == 60:
        
        for band in ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12', 'AOT', 'TCI', 'WVP', 'SCL', 'SCL_old']:
            
            if not len(glob.glob('%s/IMG_DATA/R60m/*_%s_60m.jp2'%(L2A_file,band))) == 1:
                if band == 'SCL' or band == 'SCL_old':
                    mask_enhancement_failure = True
                else:
                    band_creation_failure = True
    
    # At present we only report failure/success. More work requried to get the type of failure.
    return np.logical_and(band_creation_failure, mask_enhancement_failure) == False




def main(input_dir = os.getcwd(), remove = False):
    """main(input_dir = os.getcwd(), remove = False)
    Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script calls sen2three from within Python. This is the function that is initiated from the command line.
    
    Args:
        input_dir: Directory containing level 2A Sentinel-2 .SAFE files. Defaults to current working directory.
        remove: Boolean value, which when set to True deletes level 2A files after processing is complete. Defaults to False.
    """

    # Do the processing    
    processToL3A(input_dir)
       
    # Remove level 2A files
    if remove: remove2A(input_dir)




if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script initiates sen2three from Python. It also tidies up the large database files left behind by sen2three. Level 3A files will be output to the same directory as input files.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    # NA.
    
    # Optional arguments
    optional.add_argument('input_dir', metavar = 'L2A_DIR', nargs = 1, type = str, default = os.getcwd(), help = 'Directory where the Level-2A input files are located (e.g. PATH/TO/L2A_DIRECTORY/). By default this will be the current working directory.')
    optional.add_argument('-r', '--remove', action='store_true', default = False, help = "Optionally remove all matching Sentinel-2 level 2A files from input directory. Be careful.")
    
    # Get arguments
    args = parser.parse_args()
    
    input_dir = args.input_dir[0]
        
    # Run the script
    main(input_dir = input_dir, remove = args.remove)
