#!/usr/bin/env python

import argparse
import functools
import glob
import glymur
import multiprocessing
import numpy as np
import os
import re
from scipy import ndimage
import shutil
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

import pdb

     

def _validateTile(tile):
    '''
    Validate the name structure of a Sentinel-2 tile. This tests whether the input tile format is correct.
    
    Args:
        tile: A string containing the name of the tile to to download.
    
    Returns:
        A boolean, True if correct, False if not.
    '''
    
    # Tests whether string is in format ##XXX
    name_test = re.match("[0-9]{2}[A-Z]{3}$",tile)
    
    return bool(name_test)



def _setGipp(gipp, output_dir = os.getcwd(), n_processes = 1):
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



def _runCommand(command, verbose = False):
    """
    Function to capture KeyboardInterrupt.
    Idea from: https://stackoverflow.com/questions/38487972/target-keyboardinterrupt-to-subprocess

    Args:
        command: A list containing a command for subprocess.Popen().
    """
    
    try:
        p = None

        # Register handler to pass keyboard interrupt to the subprocess
        def handler(sig, frame):
            if p:
                p.send_signal(signal.SIGINT)
            else:
                raise KeyboardInterrupt
                
        signal.signal(signal.SIGINT, handler)
        
        #p = subprocess.Popen(command)
        p = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        
        if verbose:
            for stdout_line in iter(p.stdout.readline, ""):
                print stdout_line
        
        text = p.communicate()[0]
                
        if p.wait():
            raise Exception('Command failed: %s'%' '.join(command))
        
    finally:
        # Reset handler
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    return text.decode('utf-8'),split('/n')



def getL2AFile(infile, output_dir = os.getcwd(), SAFE = False):
    """
    Determine the level 2A tile path name from an input file (level 1C) tile.
    
    Args:
        infile: Input .SAFE file tile (e.g. '/PATH/TO/*.SAFE/GRANULE/*').
        output_dir: Directory of processed file.
        SAFE: Return path of base .SAFE file
    Returns:
        The name and directory of the output file
    """
    
    # Determine output file name, replacing two instances only of substring L1C_ with L2A_
    outfile = '/'.join(infile.split('/')[-3:])[::-1].replace('L1C_'[::-1],'L2A_'[::-1],2)[::-1]
    
    # Replace _OPER_ with _USER_ for case of old file format (in final 2 cases)
    outfile = outfile[::-1].replace('_OPER_'[::-1],'_USER_'[::-1],2)[::-1]
    
    outpath = os.path.join(output_dir, outfile)
    
    # Get outpath of base .SAFE file
    if SAFE: outpath = '/'.join(outpath.split('.SAFE')[:-1]) + '.SAFE'# '/'.join(outpath.split('/')[:-2])
    
    return outpath.rstrip('/')



def processToL2A(infile, gipp = None, output_dir = os.getcwd(), n_processes = 1, resolution = 0, verbose = False):
    """
    Processes Sentinel-2 level 1C files to level L2A with sen2cor.
    
    Args:
        infile: A level 1C Sentinel-2 .SAFE file.
        gipp: Optionally specify a copy of the L2A_GIPP.xml file in order to tweak options.
        output_dir: Optionally specify an output directory. Defaults to current working directory.
        n_processes: Number of processes to allocate to sen2cor. We don't use this, as we implement our own paralellisation via multiprocessing.
        resolution: Optionally specify a resolution (10, 20 or 60) meters. Defaults to 0, which processes all three
    Returns:
        Absolute file path to the output file.
    """
    
    # Test that input file is in .SAFE format
    assert infile.split('/')[-3][-5:] == '.SAFE', "Input files must be in .SAFE format. This file is %s."%infile
    
    # Test that resolution is reasonable
    assert resolution in [0, 10, 20, 60], "Input resolution must be 10, 20, 60, or 0 (for 10, 20 and 60). The input resolution was %s"%str(resolution)
    
    # Determine output filename
    outpath = getL2AFile(infile, output_dir = output_dir)
      
    # Check if output file already exists
    if os.path.exists(outpath):
        raise ValueError('The output file %s already exists! Delete it to run L2_Process.'%outpath)
    
    # Get location of exemplar gipp file for modification
    if gipp == None:
        gipp = '/'.join(os.path.abspath(__file__).split('/')[:-2] + ['cfg','L2A_GIPP.xml'])
        
    # Set options in L2A GIPP xml. Returns the modified .GIPP file. This prevents concurrency issues in multiprocessing.
    temp_gipp = _setGipp(gipp, output_dir = output_dir, n_processes = n_processes)
             
    # Set up sen2cor command
    if resolution != 0:
        command = ['L2A_Process', '--GIP_L2A', temp_gipp, '--resolution', str(resolution), infile]
    else:
        command = ['L2A_Process', '--GIP_L2A', temp_gipp, infile]
    
    # Print command for user info
    print ' '.join(command)
       
    # Do the processing, and capture exceptions
    try:
        output_text = _runCommand(command, verbose = verbose)
    except Exception as e:
        # Tidy up temporary options file
        os.remove(temp_gipp)
        raise

    # Tidy up temporary options file
    os.remove(temp_gipp)
    
    # Get path of .SAFE file.
    outpath_SAFE = getL2AFile(infile, output_dir = output_dir, SAFE = True)
    
    # Test if AUX_DATA output directory exists. If not, create it, as it's absense crashes sen2three.
    if not os.path.exists('%s/AUX_DATA'%outpath_SAFE):
        os.makedirs('%s/AUX_DATA'%outpath_SAFE)
    
    # Occasionally sen2cor outputs a _null directory. This needs to be removed, or sen2Three will crash.
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
        
    # Important options for .jp2 file, required for sen2cor/sen2three to understand image
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
    shutil.copy2(image_path, image_path[:-7] + 'old_' + image_path[-7:])

    # Overwite original file
    jp2_out.wrap(image_path, boxes = boxes_out)
    
    # Tidy up temporary .jp2 file
    os.remove(temp_jp2)



def testCompletion(L1C_file, output_dir = os.getcwd(), resolution = 0):
    """
    Test for successful completion of sen2cor processing. Not yet functional.
    
    Args:
        L1C_file: Path to level 1C granule file (e.g. /PATH/TO/*_L1C_*.SAFE/GRANULE/*)
    Returns:
        A boolean describing whether processing completed sucessfully.
    """
        
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



def removeL1C(L1C_file):
    """
    Deletes a Level 1C Sentinel-2 .SAFE file from disk.
    
    Args:
        L1C_file: A Sentinel-2 level 1C file.
    """
    
    assert '_MSIL1C_' in L1C_file, "removeL1C function should only be used to delete Sentinel-2 level 1C .SAFE files"
    assert L1C_file.split('/')[-3][-5:] == '.SAFE', "removeL1C function should only be used to delete Sentinel-2 level 1C .SAFE tile files"
    assert testCompletion(L1C_file), "File did not finish processing, so not deleting L1C input file."
    
    shutil.rmtree(L1C_file)



def main(infile, gipp = None, output_dir = os.getcwd(), remove = False, resolution = 0, verbose = False):
    """
    Function to initiate sen2cor on level 1C Sentinel-2 files and perform improvements to cloud masking. This is the function that is initiated from the command line.
    
    Args:
        infile: A Level 1C Sentinel-2 .SAFE file.
        gipp: Optionally specify a copy of the L2A_GIPP.xml file in order to tweak options.
        output_dir: Optionally specify an output directory. The option gipp must also be specified if you use this option.
        remove: Boolean value, which when set to True deletes level 1C files after processing is complete. Defaults to False.
    """

    print 'Processing %s'%infile.split('/')[-1]
    
    
    try:
        L2A_file = processToL2A(infile, gipp = gipp, output_dir = output_dir, resolution = resolution, verbose = verbose)
    except Exception as e:
        raise
    
    # Run sen2cor
    # L2A_file = processToL2A(infile, gipp = gipp, output_dir = output_dir, resolution = resolution)

    # Perform improvements to mask for each resolution   
    if resolution != 10:
        for res in [20, 60] if resolution == 0 else [resolution]:
            cloudmask_jp2, image_path = loadMask(L2A_file, res)
            cloudmask_new = improveMask(cloudmask_jp2, res)
            writeMask(cloudmask_jp2, cloudmask_new, image_path)
    
    if remove: removeL1C(infile)
    
    # Test for completion
    if testCompletion(infile, output_dir = output_dir, resolution = resolution) == False: print 'WARNING: %s did not complete processing.'%infile



def _prepInfiles(infiles, tile = ''):
    """
    Args:
        infiles: A list of input files, directories, or tiles for Sentinel-2 inputs
        tile: Optionally filter infiles to return only those matching a particular tile
    Returns:
        A list of all Sentinel-2 tiles in infiles, 
    """
    
    # Get absolute path, stripped of symbolic links
    infiles = [os.path.abspath(os.path.realpath(infile)) for infile in infiles]
    
    # List to collate 
    infiles_reduced = []
    
    for infile in infiles:
         
        # Where infile is a directory:
        infiles_reduced.extend(glob.glob('%s/*.SAFE/GRANULE/*'%infile))
        
        # Where infile is a .SAFE file
        if infile.split('/')[-1].split('.')[-1] == 'SAFE': infiles_reduced.extend(glob.glob('%s/GRANULE/*'%infile))
        
        # Where infile is a specific granule 
        if infile.split('/')[-2] == 'GRANULE': infiles_reduced.extend(glob.glob('%s'%infile))
    
    # Strip repeats (in case)
    infiles_reduced = list(set(infiles_reduced))
    
    # Reduce input to infiles that match the tile (where specified)
    infiles_reduced = [infile for infile in infiles_reduced if ('_T%s'%tile in infile.split('/')[-1])]
    
    # Reduce input files to only L1C files
    infiles_reduced = [infile for infile in infiles_reduced if ('_MSIL1C_' in infile.split('/')[-3])]
    
    return infiles_reduced



def _init_worker():
    '''
    Function to allow interruption of multiprocessing.Pool().
    '''
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    

if __name__ == '__main__':
    '''
    '''
    
    
    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to level 2A. This script initiates sen2cor, which performs atmospheric correction and generate a cloud mask. This script also performs simple improvements to the cloud mask.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    required.add_argument('infiles', metavar = 'L1C_FILES', type = str, nargs = '+', help = 'Sentinel 2 input files (level 1C) in .SAFE format. Specify one or more valid Sentinel-2 .SAFE, a directory containing .SAFE files, a Sentinel-2 tile or multiple tiles through wildcards (e.g. *.SAFE/GRANULE/*). All tiles that match input conditions will be atmospherically corrected.')
    
    # Optional arguments
    optional.add_argument('-t', '--tile', type = str, default = '', help = 'Specify a specific Sentinel-2 tile to process. If omitted, all tiles in L1C_FILES will be processed.')
    optional.add_argument('-g', '--gipp', type = str, default = None, help = 'Specify a custom L2A_Process settings file (default = sen2cor/cfg/L2A_GIPP.xml).')
    optional.add_argument('-o', '--output_dir', type = str, metavar = 'DIR', default = os.getcwd(), help = "Specify a directory to output level 2A files. If not specified, atmospherically corrected images will be written to the same directory as input files.")
    optional.add_argument('-res', '--resolution', type = int, metavar = '10/20/60', default = 0, help = "Process only one of the Sentinel-2 resolutions, with options of 10, 20, or 60 m. Defaults to processing all three.")
    optional.add_argument('-r', '--remove', action='store_true', default = False, help = "Delete input level 1C files after processing.")
    optional.add_argument('-p', '--n_processes', type = int, metavar = 'N', default = 1, help = "Specify a maximum number of tiles to processi n paralell. Bear in mind that more processes will require more memory. Defaults to 1.")
    optional.add_argument('-v', '--verbose', action='store_true', default = False, help = "Make script verbose.")
    
    # Get arguments
    args = parser.parse_args()
        
    # Get all infiles that match tile and file pattern
    infiles = _prepInfiles(args.infiles, tile = args.tile)
        
    # Get absolute path for output directory
    args.output_dir = os.path.abspath(args.output_dir)
    
    # Strip the output files already exist.
    for infile in infiles[:]:
        outpath = getL2AFile(infile, output_dir = args.output_dir)
        
        if os.path.exists(outpath):
            infiles.remove(infile)
            print 'The output file %s already exists! Skipping file.'%outpath
    
    if len(infiles) == 0: raise ValueError('No usable level 1C Sentinel-2 files detected in input directory.')
    
    # Set up number of parallel processes
    pool = multiprocessing.Pool(args.n_processes, _init_worker)
    
    # Set up function with multiple arguments
    main_partial = functools.partial(main, gipp = args.gipp, output_dir = args.output_dir, remove = args.remove, resolution = args.resolution, verbose = args.verbose)
    
    # Process for each input file
    p = pool.map_async(main_partial, infiles)
    
    # This structure exits all processes on error (e.g. KeyboardInterrupt)
    try:
        results = p.get(0xFFFF)
    except Exception, e:
        print e
    
    # Kill all remaining processes
    pool.terminate()
    pool.join()
        
    # Test for completion (in case of crashing out of pool)
    completion = np.array([testCompletion(infile, resolution = args.resolution) for infile in infiles])
    
    # Report back
    if completion.sum() > 0: print 'Successfully processed files:'
    for infile in np.array(infiles)[completion == True]:
        print infile 
    if (completion == False).sum() > 0: print 'Files that failed:'
    for infile in np.array(infiles)[completion == False]:
        print infile 
    

    
    

