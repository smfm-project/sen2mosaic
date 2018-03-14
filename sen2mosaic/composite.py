#!/usr/bin/env python

import argparse
import datetime
import glob
import numpy as np
import os
import re
import shutil
import signal
import subprocess
import xml.etree.ElementTree as ET

import pdb


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


def _getDate(infile):
    '''
    Return a datetime object for an input GRANULE.
    
    Args:
        infile: A Sentinel-2 level 2A granule.
    Returns:
        A datetime object
    '''
    
    timestring = infile.split('/')[-1].split('_')[-1].split('T')[0]
    
    return datetime.datetime.strptime(timestring, '%Y%m%d')
    
    
    
def _validateInput(tile, input_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d')):
    """_validateInput(tile, input_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'))
    
    Test whether appropriate input files exist in the input directory
    
    Args:
        tile: A Sentinel-2 tile (stripped of preceding T).
        input_dir: Input directory
        start: start date in format YYYYMMDD. Defaults to beginning of Sentinel-2 era.
        end: end date in format YYYYMMDD. Defaults to today's date.
    """
      
    # Test that input location contains level 2A files for tile.
    infiles = glob.glob('%s/S2?_MSIL2A_*.SAFE/GRANULE/*T%s*'%(input_dir,tile))
    
    assert len(infiles) >= 1, "Input directory must contain at least one Sentinel-2 level 2A file from tile T%s."%tile
    
    # Test that input location contains at least one file within date range
    dates = np.array([_getDate(i) for i in infiles])
    
    valid_dates = np.logical_and(dates >= datetime.datetime.strptime(start, '%Y%m%d'), dates <= datetime.datetime.strptime(end, '%Y%m%d'))
    
    assert valid_dates.sum() > 0, "Input directory must contain at least one file between dates %s and %s."%(start, end)
        
    

def getL3AFile(tile, input_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d')):
    """getL3AFile(tile, input_dir = os.getcwd(), output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'))
    
    Determine the level 3A tile path name from an input file (level 2A) tile.
    
    Args:
        ...
    Returns:
        ...
    """
    
    # Cleanse input
    input_dir = os.path.abspath(input_dir).rstrip('/')
    
    #Get dates from infiles, and use to format first date
    infiles = glob.glob('%s/S2?_MSIL2A_*.SAFE/GRANULE/*T%s*'%(input_dir,tile))
    first_date = np.array([_getDate(i) for i in infiles]).min()
    first_date_formatted = str(first_date.year) + str(first_date.month).zfill(2) + str(first_date.day).zfill(2)
    
    # Generate expected file pattern
    L3_format = 'S2?_MSIL03_%sT??????_N????_R???_T%s_%sT000000.SAFE'%(first_date_formatted, tile, start)
    
    return L3_format


def _setGipp(gipp, tile, output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), algorithm = 'TEMP_HOMOGENEITY'):
    """
    Function that tweaks options in sen2cor's L2A_GIPP.xml file to specify an output directory.
    
    Args:
        gipp: The path to a copy of the L3_GIPP.xml file.
        output_dir: The desired output directory. Defaults to the same directory as input files.
        
    Returns:
        The directory location of a temporary .gipp file, for input to L2A_Process
    """
    
    # Test that GIPP and output directory exist
    assert gipp != None, "GIPP file must be specified if you're changing sen2three options."
    assert os.path.isfile(gipp), "GIPP XML options file doesn't exist at the location %s."%gipp  
    assert os.path.isdir(output_dir), "Output directory %s doesn't exist."%output_dir
    assert algorithm in ['MOST_RECENT', 'TEMP_HOMOGENEITY', 'RADIOMETRIC_QUALITY', 'AVERAGE'], "sen2three algorithm %s must be one of 'MOST_RECENT', 'TEMP_HOMOGENEITY', 'RADIOMETRIC_QUALITY', 'AVERAGE'. You input %s"%str(algorithm)
    
    # Adds a trailing / to output_dir if not already specified
    output_dir = os.path.join(output_dir, '')
    
    # Read GIPP file
    tree = ET.ElementTree(file = gipp)
    root = tree.getroot()
    
    # Change output directory    
    root.find('Common_Section/Target_Directory').text = output_dir
    
    # Set Min_Time
    root.find('L3_Synthesis/Min_Time').text = '%s-%s-%sT00:00:00Z'%(start[:4], start[4:6], start[6:])
    
    # Set Max_Time
    root.find('L3_Synthesis/Max_Time').text = '%s-%s-%sT23:59:59Z'%(end[:4], end[4:6], end[6:])
    
    # Set tile filer
    root.find('L3_Synthesis/Tile_Filter').text = 'T%s'%tile
    
    # Set algorithm
    root.find('L3_Synthesis/Algorithm').text = algorithm
    
    # Get location of gipp file
    gipp_file = os.path.abspath(os.path.expanduser('~/sen2three/cfg/L3_GIPP.xml'))
    
    # Ovewrite old GIPP file with new options
    tree.write(gipp_file)
    
    return gipp_file


def processToL3A(tile, input_dir = os.getcwd(), output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), gipp = None, verbose = False):
    """processToL3A(tile, input_dir = os.getcwd(), output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), verbose = False):
    
    Processes Sentinel-2 level 2A files to level 3A with sen2three.
    
    Args:
        input_dir: Directory containing level 2A Sentinel-2 .SAFE files. Directory must contain files from only one single tile.
    """
      
    # Cleanse input formats.
    input_dir = os.path.abspath(input_dir).rstrip('/')
    output_dir = os.path.abspath(output_dir).rstrip('/')
    tile = tile.lstrip('T')
    
    # Test that tile is properly formatted
    assert _validateTile(tile), "Tile %s is not a correctly formatted Sentinel-2 tile (e.g. T36KWA)."%str(tile)
    
    # Test that appropraiate inputs exist
    _validateInput(tile, input_dir = input_dir, start = start, end = end)
        
    # Determine output filename
    outpath = getL3AFile(tile, input_dir = input_dir, start = start, end = end)
    
    # Check if output file already exists
    if len(glob.glob('%s/%s'%(output_dir,outpath))):
        raise ValueError('An output file with pattern %s already exists in output directory! Delete it to run L3_Process.'%outpath)
    
    # Get location of exemplar gipp file for modification
    if gipp == None:
        gipp = '/'.join(os.path.abspath(__file__).split('/')[:-2] + ['cfg','L3_GIPP.xml'])
    
    # Set options in L3 GIPP xml. Returns the modified .GIPP file. This prevents concurrency issues with multiple instances.
    gipp_file = _setGipp(gipp, tile, output_dir = output_dir, start = start, end = end)
        
    # Set up sen2three command
    command = ['L3_Process', input_dir, '--clean']
    
    # Print command for user info
    if verbose: print ' '.join(command)
       
    # Do the processing
    output_text = _runCommand(command, verbose = verbose)
    
    # Run sen2three (L3_Process)
    #subprocess.call(command)
       
    # Tidy up huge .database.h5 files. These files are very large, and aren't subsequently required.
    h5_files = glob.glob('%s/GRANULE/*/IMG_DATA/R*m/.database.h5'%outpath)
    
    for h5_file in h5_files:
        os.remove(h5_file)


def testCompletion(tile, input_dir = os.getcwd(), output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), resolution = 0):
    """
    Test for successful completion of sen2three processing.
    
    Args:
    Returns:

    """
    
    file_creation_failure = False
    band_creation_failure = False
    
    L3_file = getL3AFile(tile, input_dir = input_dir, start = start, end = end)
    
    if len(glob.glob(L3_file)) == 0:
        file_creation_failure = True   
    
    # Test all expected 10 m files are present
    if resolution == 0 or resolution == 10:
        
        for band in ['B02', 'B03', 'B04', 'B08', 'TCI', 'SCL']:
            
            if not len(glob.glob('%s/GRANULE/*/IMG_DATA/R10m/L03_T%s_%s_10m.jp2'%(L3_file,tile,band))) == 1:
                band_creation_failure = True
    
    # Test all expected 20 m files are present
    if resolution == 0 or resolution == 20:
        
        for band in ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12', 'TCI', 'SCL']:
            
            if not len(glob.glob('%s/GRANULE/*/IMG_DATA/R20m/L03_T%s_%s_20m.jp2'%(L3_file,tile,band))) == 1:
                band_creation_failure = True

    # Test all expected 60 m files are present
    if resolution == 0 or resolution == 60:
        
        for band in ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'B09', 'B11', 'B12', 'TCI', 'SCL']:
            
            if not len(glob.glob('%s/GRANULE/*/IMG_DATA/R60m/L03_T%s_%s_60m.jp2'%(L3_file,tile,band))) == 1:
                band_creation_failure = True
    
    # At present we only report failure/success. More work requried to get the type of failure.
    return np.logical_and(file_creation_failure, band_creation_failure) == False


def remove2A(input_dir, tile):
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

    # Only delete files from input tile

    

def main(tile, input_dir = os.getcwd(), output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), remove = False, verbose = False):
    """main(tile, input_dir = os.getcwd(), output_dir = os.getcwd(), start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), remove = False, verbose = False)
    
    Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script calls sen2three from within Python. This is the function that is initiated from the command line.
    
    Args:
        tile: Sentinel-2 tile to process, in format 'T##XXX' or '##XXX' (e.g. 'T36KWA').
        input_dir: Directory containing level 2A Sentinel-2 .SAFE files. Defaults to current working directory.
        remove: Boolean value, which when set to True deletes level 2A files after processing is complete. Defaults to False.
    """
            
    # Do the processing    
    processToL3A(tile, input_dir = input_dir, output_dir = output_dir, start = start, end = end, verbose = verbose)
        
    # Remove level 2A files
    if remove: remove2A(input_dir)
    
    # Test for completion
    if testCompletion(input_dir, output_dir = os.getcwd(), resolution = 0) == False:
        print 'WARNING: %s did not complete processing.'%tile




if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with sen2three. This script initiates sen2three from Python. It also tidies up the large database files left behind by sen2three. Level 3A files will be output to the same directory as input files.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    required.add_argument('-t', '--tile', metavar = 'TILE', type = str, help = 'Sentinel-2 to process, in format T##XXX or ##XXX (e.g. T36KWA).')
    
    # Optional arguments
    optional.add_argument('input_dir', metavar = 'PATH', nargs = '*', type = str, default = [os.getcwd()], help = 'Directory where the Level-2A input files are located (e.g. PATH/TO/L2A_DIRECTORY/). By default this will be the current working directory. Also supports multiple directories through wildcards (*), which will be processed in series.')
    optional.add_argument('-s', '--start', type = str, default = '20150101', help = "Start date for tiles to include in format YYYYMMDD. Defaults to processing all available files.")
    optional.add_argument('-e', '--end', type = str, default = datetime.datetime.today().strftime('%Y%m%d'), help = "End date for tiles to include in format YYYYMMDD. Defaults to processing all available files.")
    optional.add_argument('-o', '--output_dir', type = str, metavar = 'DIR', default = os.getcwd(), help = "Specify a directory to output level 3A file. If not specified, the composite image will be written to the same directory as input files.")
    optional.add_argument('-r', '--remove', action='store_true', default = False, help = "Delete all matching Sentinel-2 level 2A files from input directory after processing. Be careful.")
    optional.add_argument('-v', '--verbose', action = 'store_true', default = False, help = 'Print progress.')
    
    # Get arguments
    args = parser.parse_args()
    
    for input_dir in args.input_dir:
        
        # Run the script
        main(args.tile, input_dir = input_dir, output_dir = args.output_dir, start = args.start, end = args.end, remove = args.remove, verbose = args.verbose)
