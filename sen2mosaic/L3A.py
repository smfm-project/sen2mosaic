#!/usr/bin/env python

import argparse
import glob
import os
import re
import shutil
import subprocess

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def processToL3A(input_dir):
    """
    Processes Sentinel-2 level 2A files to level 3A with sen2three.
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
    command = ['L3_Process', '--clean', input_dir]
    
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
    Function to remove all Sentinel-2 level 2A files from a directory.
    Input is a directory containing level 2A .SAFE files.
    """

    # Remove trailing / from input directory if present
    input_dir = input_dir.rstrip('/')
        
    # Test that input location contains appropriate files in .SAFE format
    infiles = glob.glob('%s/*_MSIL2A_*T%s_*.SAFE'%input_dir)
    assert len(infiles) > 0, "Input directory must contain level 2A files in .SAFE format."

    # Test whether directory contains files from only one tile. Sen2three will process everything in a directory, so this is important
    tiles = [i.split('_')[-2] for i in infiles]

    assert len(list(set(tiles)))==1, "The input directory contains level 2A files from multiple tiles. L3A.py is hesitant to delete files indiscriminately, so please ensure files from only one tile are present in the directory."
    
    # Delete L2A files
    for this_file in infiles:
        shutil.rmtree(this_file)


def main(input_dir = os.getcwd(), remove = False):
    """
    Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script initiates sen2three from within Python.
    """

    # Do the processing    
    processToL3A(input_dir)
    
    # Remove level 2A files
    remove2A(input_dir)


if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script initiates sen2three from Python. It also tidies up the large database files left behind by sen2three. Level 3A files will be output to the same directory as input files.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    required.add_argument('input_dir', metavar = 'L2A_DIR', nargs = 1, type = str, help = 'Directory where the Level-2A input files are located (e.g. PATH/TO/L2A_DIRECTORY/) By default this will be the current working directory.')

    # Optional arguments
    optional.add_argument('-r', '--remove', action='store_true', default = False, help = "Optionally remove all matching Sentinel-2 level 2A files from input directory. Be careful.")
    
    # Get arguments
    args = parser.parse_args()
    
    input_dir = args.input_dir[0]
        
    # Run the script
    main(input_dir = input_dir, remove = args.remove)
