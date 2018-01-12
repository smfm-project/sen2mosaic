#!/usr/bin/env python

import argparse
import glob
import glymur
import numpy as np
import os
import re
from scipy import ndimage
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pdb

def _validateTile(tile):
    '''
    Validate the name structure of a Sentinel-2 tile. This tests whether the input tile format is correct.
    
    Args:
        tile: A string containing the name of the tile to to download.
    '''
    
    # Tests whether string is in format ##XXX
    name_test = re.match("[0-9]{2}[A-Z]{3}$",tile)
    
    return bool(name_test)



def _setGipp(gipp, output_dir = os.getcwd(), n_processes = '1'):
    """
    Function that tweaks options in sen2cor's L2A_GIPP.xml file to specify an output directory.
    
    Args:
        gipp: The path to a copy of the L2A_GIPP.xml file.
        output_dir: The desired output directory. Defaults to the same directory as input files.
        n_processes: The number of processes to use for sen2cor. Defaults to 1.
    
    Returns:
        The directory location of a temporary .gipp file, for input to L2A_Process
    """
    
    # Test that GIPP and output directory exist
    assert gipp != None, "GIPP file must be specified if you're changing sen2cor options."
    assert os.path.isfile(gipp), "GIPP XML options file doesn't exist at the location %s."%gipp  
    assert os.path.isdir(output_dir), "Output directory %s doesn't exist."%output_dir
    
    # Adds a trailing / to output_dir if not already specified
    output_dir = os.path.join(output_dir, '')
   
    # Read GIPP file
    tree = ET.ElementTree(file = gipp)
    root = tree.getroot()

    # Change output directory    
    root.find('Common_Section/Target_Directory').text = output_dir
    
    # Change number of processes
    root.find('Common_Section/Nr_Processes').text = str(n_processes)
    
    # Generate a temporary output file
    temp_gipp = tempfile.mktemp(suffix='.xml')
    
    # Ovewrite old GIPP file with new options
    tree.write(temp_gipp)
    
    return temp_gipp



def processToL2A(infile, gipp = None, output_dir = os.getcwd(), n_processes = '1'):
    """
    Processes Sentinel-2 level 1C files to level L2A with sen2cor.
    
    Args:
        infile: A level 1C Sentinel-2 .SAFE file.
        gipp: Optionally specify a copy of the L2A_GIPP.xml file in order to tweak options.
        output_dir: Optionally specify an output directory. Defaults to current working directory.
    Returns:
        Absolute file path to the output file.
    """
    
    # Test that input file is in .SAFE format
    assert infile.split('/')[-3][-5:] == '.SAFE', "Input files must be in .SAFE format. This file is %s."%infile
    
    # Get location of exemplar gipp file for modification
    if gipp == None:
        gipp = '/'.join(os.path.abspath(__file__).split('/')[:-2] + ['cfg','L2A_GIPP.xml'])
        
    # Set options in L2A GIPP xml. Returns the modified .GIPP file
    temp_gipp = _setGipp(gipp, output_dir = output_dir, n_processes = n_processes)
             
    # Set up sen2cor command
    command = ['L2A_Process', '--GIP_L2A', temp_gipp, infile]
    
    # Print command for user info
    print '%s'%' '.join(command)
    pdb.set_trace() 
    # Run sen2cor (L2A_Process)
    subprocess.call(command)
      
    # Determine output file name, replacing two instances only of substring L1C_ with L2A_
    outfile = infile[::-1].replace('L1C_'[::-1],'L2A_'[::-1],2)[::-1]
        
    # Replace _OPER_ with _USER_ for case of old file format (in final 2 cases)
    outfile = outfile[::-1].replace('_OPER_'[::-1],'_USER_'[::-1],2)[::-1]
    
    outpath = os.path.join(output_dir, outfile)
    
    # Get outpath of base .SAFE file
    outpath_SAFE = '/'.join(outpath.split('/')[:-2])
    
    # Test if AUX_DATA output directory exists. If not, create it, as it's absense crashes sen2Three.
    if not os.path.exists('%s/AUX_DATA'%outpath_SAFE):
        os.makedirs('%s/AUX_DATA'%outpath_SAFE)
    
    # Occasioanlly sen2cor outputs a _null directory. This needs to be removed, or sen2Three will crash.
    bad_directories = glob.glob('%s/GRANULE/*_null/'%outpath_SAFE)
    
    if bad_directories:
        [shutil.rmtree(bd) for bd in bad_directories]
    
    return outpath



def loadMask(L2A_file, res):
    """
    Load classification mask given .SAFE file and resolution.
    
    Args:
        L2A_file: A level 2A Sentinel-2 .SAFE file, processed with sen2cor.
        res: Integer of resolution to be processed (i.e. 10 m, 20 m, 60 m).
    
    Returns:
        A glymur .jp2 file the path to the classified image.
        The directory location of the .jp2 mask file.
    """
        
    # Remove trailing slash from input filename, if it exists
    L2A_file = L2A_file.rstrip('/')
    
    # Identify the cloud mask following the standardised file pattern
    image_path = glob.glob('%s/IMG_DATA/R%sm/*_SCL_*m.jp2'%(L2A_file,str(res)))
    
    # In case of old file format structure, the SCL file is stored elsewhere
    if len(image_path) == 0:
        image_path = glob.glob('%s/IMG_DATA/*_SCL_*%sm.jp2'%(L2A_file,str(res)))
    
    # Load the cloud mask (.jp2 format)
    jp2 = glymur.Jp2k(image_path[0])

    return jp2, image_path[0]



def improveMask(jp2, res):
    """
    Tweaks the cloud mask output from sen2cor. Processes are: (1) Changing 'dark features' to 'cloud shadows, (2) Dilating 'cloud shadows', 'medium probability cloud' and 'high probability cloud' by 180 m. (3) Eroding outer 3 km of the tile to improve stitching of images by sen2Three.
    
    Args:
        jp2: A glymur .jp2 file from loadMask().
        res: Integer of resolution to be processed (i.e. 10 m, 20 m, 60 m).
    
    Returns:
        A numpy array of the SCL mask with modifications.
    """
    
    # Read file as numpy array
    data = jp2[:]
    
    # Make a copy of the original classification mask
    data_orig = data.copy()
    
    # Change pixels labelled as 'dark features' to cloud shadows
    data[data==2] = 3
    
    # Change cloud shadows not within 1800 m of a cloud pixel to water
    iterations = 1800/res
    
    # Identify pixels proximal to any measure of cloud cover
    cloud_dilated = ndimage.morphology.binary_dilation((np.logical_or(data==8, data==9)).astype(np.int), iterations = iterations)
    
    data[np.logical_and(data == 3, cloud_dilated == 0)] = 6
        
    # Dilate cloud shadows, med clouds and high clouds by 180 m.
    iterations = 180 / res
    
    # Make a temporary dataset to prevent dilated masks overwriting each other
    data_temp = data.copy()
    
    for i in [3,8,9]:
        # Grow the area of each input class
        mask_dilate = ndimage.morphology.binary_dilation((data==i).astype(np.int), iterations = iterations)
        
        # Set dilated area to the same value as input class
        data_temp[mask_dilate] = i
        
    data = data_temp

    # Erode outer 3 km of image tile (should retain overlap)
    iterations = 3000/res # 3 km buffer around edge
    
    # Shrink the area of measured pixels (everything that is not equal to 0)
    mask_erode = ndimage.morphology.binary_erosion((data_orig != 0).astype(np.int), iterations=iterations)
    
    # Set these eroded areas to 0
    data[mask_erode == False] = 0
    
    return data



def writeMask(jp2, data, image_path):
    """
    Overwrites the old SCL mask with a new one, preserving the metadata (including projection info) from the original .jp2 file.
    
    Args:
        jp2: A glymur jp2 file of the original SCL mask.
        data: A numpy array containing the new data to overwrite the old mask with.
        image_path: The path to the original classified image.
    """
          
    # Get metadata from original .jp2 file (including projection)
    boxes = jp2.box

    # Generate a temporary output file
    temp_jp2 = tempfile.mktemp(suffix='.jp2')
        
    # Important options for .jp2 file, required for sen2cor/sen2Three to understand image
    kwargs = {"tilesize": (640, 640), "prog": "RPCL"}

    # Save temporary image to generate metadata (boxes)
    jp2_out = glymur.Jp2k(temp_jp2, data = data, **kwargs)

    # Replace boxes in modified file with originals
    boxes_out = jp2_out.box

    boxes_out[0] = boxes[0]
    boxes_out[1] = boxes[1]
    boxes_out[2] = boxes[2]
    boxes_out.insert(3,boxes[3]) # This is the projection info
            
    # Make a copy of the original file
    shutil.copy2(image_path, image_path[:-4]+'_old.jp2')

    # Overwite original file
    jp2_out.wrap(image_path, boxes = boxes_out)



def removeL1C(L1C_file):
    """
    Deletes a Level 1C Sentinel-2 .SAFE file from disk.
    
    Args:
        L1C_file: A Sentinel-2 level 1C file.
    """
    
    assert '_MSIL1C_' in L1C_file, "removeL1C function should only be used to delete Sentinel-2 level 1C .SAFE files"
    assert L1C_file.split('/')[-1][-5:] == '.SAFE', "removeL1C function should only be used to delete Sentinel-2 level 1C .SAFE files"
    
    shutil.rmtree(L1C_file)



def main(infile, gipp = None, output_dir = os.getcwd(), n_processes = '1', remove = False):
    """
    Function to initiate sen2cor on level 1C Sentinel-2 files and perform improvements to cloud masking. This is the function that is initiated from the command line.
    
    Args:
        infile: A Level 1C Sentinel-2 .SAFE file.
        gipp: Optionally specify a copy of the L2A_GIPP.xml file in order to tweak options.
        output_dir: Optionally specify an output directory. The option gipp must also be specified if you use this option.
        remove: Boolean value, which when set to True deletes level 1C files after processing is complete. Defaults to False.
    """

    print 'Processing %s'%infile.split('/')[-1]
    
    # Run sen2cor
    L2A_file = processToL2A(infile, gipp = gipp, output_dir = output_dir, n_processes = n_processes)
    
    # Perform improvements to mask for each resolution
    for res in [20,60]:
        cloudmask_jp2, image_path = loadMask(L2A_file, res)
        cloudmask_new = improveMask(cloudmask_jp2, res)
        writeMask(cloudmask_jp2, cloudmask_new, image_path)
    
    if remove: removeL1C(infile)



if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to level 2A. This script initiates sen2cor, which performs atmospheric correction and generate a cloud mask. This script also performs simple improvements to the cloud mask.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    required.add_argument('infiles', metavar = 'L1C_FILES', type = str, nargs = '+', help = 'Sentinel 2 input files (level 1C) in .SAFE format. Specify one or more valid Sentinel-2 granules, or multiple granules through wildcards (e.g. PATH/TO/*_MSIL1C_*.SAFE/GRANULE/*). Input granules will be atmospherically corrected.')
    
    # Optional arguments
    optional.add_argument('-g', '--gipp', type = str, default = None, help = 'Specify a custom L2A_Process settings file (default = sen2cor/cfg/L2A_GIPP.xml).')
    optional.add_argument('-o', '--output_dir', type = str, metavar = 'DIR', default = os.getcwd(), help = "Specify a directory to output level 2A files. If not specified, atmospherically corrected images will be written to the same directory as input files.")
    optional.add_argument('-p', '--n_processes', type = str, metavar = 'N', default = '1', help = "Specify a number of processes to use with sen2cor.")
    optional.add_argument('-r', '--remove', action='store_true', default = False, help = "Delete input level 1C files after processing.")
    
    # Get arguments
    args = parser.parse_args()
    
    # Where only one file input, ensure its a list so that it behaves properly in loops
    infiles = list(args.infiles)
    
    # Get absolute path of input files.
    infiles = [os.path.abspath(i) for i in infiles]
    
    # Get absolute path for output file
    if args.output_dir != 'DEFAULT':
        args.output_dir = os.path.abspath(args.output_dir)
        
    # Run the script for each input file
    for infile in infiles:
        main(infile, gipp = args.gipp, output_dir = args.output_dir, remove = args.remove)
    
