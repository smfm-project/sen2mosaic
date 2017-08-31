import argparse
import os
import shutil
import subprocess

import L1C.validateTile as validateTile
import L2A.cd as cd


def processToL3A(tile, input_dir = os.getcwd(), output_dir = os.getcwd()):
    """
    Processes Sentinel-2 level 2A files to level 3A with sen2three.
    Input a tile in format ##XXX, a directory containing L2A files, and an output directory.
    If input and output directories not specified, the program will read all L2A files and output to the present working directory.
    """
    
    # Remove trailing / from input and output directories if present
    input_dir = input_dir.rstrip('/')
    output_dir = output_dir.rstrip('/')
    
    # Test that input location contains appropriate files in .SAFE format
    infiles = glob.glob('%s/*_MSIL2A_*.SAFE'%input_dir)
    assert len(infiles) > 0, "Input files must be in .SAFE format."

    # Validate tile input format for search   
    assert validateTile(tile), "The tile name input (%s) does not match the format ##XXX (e.g. 36KWA)."%tile
    
    # Test whether directory contains files from only one tile. Sen2three will process everything in a directory, so this is important
    for i in infiles:
        assert i.split('_')[-2] == 'T%s'%tile, "The tile name input (%s) does not match all L2A files in input directory. As  sen2Three will process everything in a directory, each tile needs to be placed in its own directory."
    
    # Move to output directory and run sen2cor (L3_Process)
    with cd(output_dir):
        L3A_output = subprocess.check_output(['L3_Process', '--clean', this_file])
    
    # Determine output file path
    outpath = glob.glob('%s/*_MSIL03_*_T%s_*.SAFE'%(output_dir, tile))[0]
    
    # Tidy up huge .database.h5 files. These files are very large, and aren't subsequently required.
    h5_files = glob.glob('%s/GRANULE/*/IMG_DATA/R*m/.database.h5'%outpath)
    
    for h5_file in h5_files:
        shutil.rmtree(h5_file)


def main(tile, input_dir, output_dir = os.getcwd()):
    '''
    Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script initiates sen2three from within Python.
    '''

    # Do the processing    
    processToL3A(tile, input_dir, output_dir = output_dir)


if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script initiates sen2three from within Python.')
    
    # Required arguments
    parser.add_argument('input_dir', type = str, help = 'Directory where the Level-2A input files are located.')
    parser.add_argument('-t', '--tile', type = str, help = "Sentinel 2 tile name, in format ##XXX")

    # Optional arguments
    parser.add_argument('-o', '--output_dir', type = str, default = os.getcwd(), help = "Optionally specify an output directory. If nothing specified, outputs will be written to the present working directory.")
    
    # Get arguments
    args = parser.parse_args()
        
    # Run the script
    main(tile, input_dir, output_dir = args.output_dir)