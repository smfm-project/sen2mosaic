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

import utilities

import pdb



### Functions to enable command line interface with multiprocessing

def _do_work(job_queue, counter=None):
    """
    Processes jobs from  the multiprocessing queue until all jobs are finished
    Adapted from: https://github.com/ikreymer/cdx-index-client
    
    Args:
        job_queue: multiprocessing.Queue() object
        counter: multiprocessing.Value() object
    """
    
    import Queue
        
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    while not job_queue.empty():
        try:
            job = job_queue.get_nowait()
            
            main_partial(job)

            num_done = 0
            with counter.get_lock():
                counter.value += 1
                num_done = counter.value
                
        except Queue.Empty:
            pass

        except KeyboardInterrupt:
            break

        except Exception:
            if not job:
                raise


def _run_workers(n_processes, jobs):
    """
    This script is a queuing system that respects KeyboardInterrupt.
    Adapted from: https://github.com/ikreymer/cdx-index-client
    Which in turn was adapted from: http://bryceboe.com/2012/02/14/python-multiprocessing-pool-and-keyboardinterrupt-revisited/
    
    Args:
        n_processes: Number of parallel processes
        jobs: List of input tiles for sen2cor
    """
    
    import psutil 
    
    # Queue up all jobs
    job_queue = multiprocessing.Queue()
    counter = multiprocessing.Value('i', 0)
    
    for job in jobs:
        job_queue.put(job)
    
    workers = []
    
    for i in xrange(0, n_processes):
        
        tmp = multiprocessing.Process(target=_do_work, args=(job_queue, counter))
        tmp.daemon = True
        tmp.start()
        workers.append(tmp)

    try:
        
        for worker in workers:
            worker.join()
            
    except KeyboardInterrupt:
        for worker in workers:
            print 'Keyboard interrupt (ctrl-c) detected. Exiting all processes.'
            # This is an impolite way to kill sen2cor, but it otherwise does not listen.
            parent = psutil.Process(worker.pid)
            children = parent.children(recursive=True)
            parent.send_signal(signal.SIGKILL)
            for process in children:
                process.send_signal(signal.SIGKILL)
            worker.terminate()
            worker.join()
            
        raise



### Primary functions


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
    
    return text.decode('utf-8').split('/n')



def getL2AFile(L1C_file, output_dir = os.getcwd(), SAFE = False):
    """
    Determine the level 2A tile path name from an input file (level 1C) tile.
    
    Args:
        L1C_file: Input level 1C .SAFE file tile (e.g. '/PATH/TO/*.SAFE/GRANULE/*').
        output_dir: Directory of processed file.
        SAFE: Return path of base .SAFE file
    Returns:
        The name and directory of the output file
    """
    
    # Determine output file name, replacing two instances only of substring L1C_ with L2A_
    outfile = '/'.join(L1C_file.split('/')[-3:])[::-1].replace('L1C_'[::-1],'L2A_'[::-1],2)[::-1]
    
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
    assert resolution in [0, 10, 20, 60], "Input resolution must be 10, 20, 60, or 0 (for all resolutions). The input resolution was %s"%str(resolution)
    
    # Test that output directory is writeable
    output_dir = os.path.abspath(output_dir)
    assert os.access(output_dir, os.W_OK), "Output directory (%s) does not have write permission. Try setting a different output directory"%output_dir
    
    # Determine output filename
    outpath = getL2AFile(infile, output_dir = output_dir)
    
    # Check if output file already exists
    if os.path.exists(outpath):
      print 'The output file %s already exists! Delete it to run L2_Process.'%outpath
      return outpath
    
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
    if verbose: print ' '.join(command)
       
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


def testCompletion(L1C_file, output_dir = os.getcwd(), resolution = 0):
    """
    Test for successful completion of sen2cor processing. 
    
    Args:
        L1C_file: Path to level 1C granule file (e.g. /PATH/TO/*_L1C_*.SAFE/GRANULE/*)
    Returns:
        A boolean describing whether processing completed sucessfully.
    """
      
    L2A_file = getL2AFile(L1C_file, output_dir = output_dir, SAFE = False)
    
    failure = False
    
    # Test all expected 10 m files are present
    if resolution == 0 or resolution == 10:
        
        for band in ['B02', 'B03', 'B04', 'B08', 'AOT', 'TCI', 'WVP']:
            
            if not len(glob.glob('%s/IMG_DATA/R10m/*_%s_10m.jp2'%(L2A_file,band))) == 1:
                failure = True
    
    # Test all expected 20 m files are present
    if resolution == 0 or resolution == 20:
        
        for band in ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12', 'AOT', 'TCI', 'WVP', 'SCL']:
            
            if not len(glob.glob('%s/IMG_DATA/R20m/*_%s_20m.jp2'%(L2A_file,band))) == 1:
                
                failure = True

    # Test all expected 60 m files are present
    if resolution == 0 or resolution == 60:
        
        for band in ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12', 'AOT', 'TCI', 'WVP', 'SCL']:
            
            if not len(glob.glob('%s/IMG_DATA/R60m/*_%s_60m.jp2'%(L2A_file,band))) == 1:
                
                failure = True
    
    # At present we only report failure/success, can be extended to type of failure 
    return failure == False



def main(infile, gipp = None, output_dir = os.getcwd(), resolution = 0, verbose = False):
    """
    Function to initiate sen2cor on level 1C Sentinel-2 files and perform improvements to cloud masking. This is the function that is initiated from the command line.
    
    Args:
        infile: A Level 1C Sentinel-2 .SAFE file.
        gipp: Optionally specify a copy of the L2A_GIPP.xml file in order to tweak options.
        output_dir: Optionally specify an output directory. The option gipp must also be specified if you use this option.
    """
    
    if verbose: print 'Processing %s'%infile.split('/')[-1]
    
    try:
        L2A_file = processToL2A(infile, gipp = gipp, output_dir = output_dir, resolution = resolution, verbose = verbose)
    except Exception as e:
        raise
                
    # Test for completion, and report back
    if testCompletion(infile, output_dir = output_dir, resolution = resolution) == False:    
        print 'WARNING: %s did not complete processing.'%infile
    

if __name__ == '__main__':
    '''
    '''
    
    
    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to level 2A. This script initiates sen2cor, which performs atmospheric correction and generate a cloud mask. This script also performs simple improvements to the cloud mask.')
    
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    
    # Optional arguments
    optional.add_argument('infiles', metavar = 'L1C_FILES', type = str, default = [os.getcwd()], nargs = '*', help = 'Sentinel 2 input files (level 1C) in .SAFE format. Specify one or more valid Sentinel-2 .SAFE, a directory containing .SAFE files, a Sentinel-2 tile or multiple granules through wildcards (e.g. *.SAFE/GRANULE/*). All granules that match input conditions will be atmospherically corrected.')
    optional.add_argument('-t', '--tile', type = str, default = '', help = 'Specify a specific Sentinel-2 tile to process. If omitted, all tiles in L1C_FILES will be processed.')
    optional.add_argument('-g', '--gipp', type = str, default = None, help = 'Specify a custom L2A_Process settings file (default = sen2cor/cfg/L2A_GIPP.xml).')
    optional.add_argument('-o', '--output_dir', type = str, metavar = 'DIR', default = os.getcwd(), help = "Specify a directory to output level 2A files. If not specified, atmospherically corrected images will be written to the same directory as input files.")
    optional.add_argument('-res', '--resolution', type = int, metavar = '10/20/60', default = 0, help = "Process only one of the Sentinel-2 resolutions, with options of 10, 20, or 60 m. Defaults to processing all three.")
    optional.add_argument('-p', '--n_processes', type = int, metavar = 'N', default = 1, help = "Specify a maximum number of tiles to process in paralell. Bear in mind that more processes will require more memory. Defaults to 1.")
    optional.add_argument('-v', '--verbose', action='store_true', default = False, help = "Make script verbose.")
    
    # Get arguments
    args = parser.parse_args()
        
    # Get all infiles that match tile and file pattern
    infiles = utilities.prepInfiles(args.infiles, '1C', tile = args.tile)
        
    # Get absolute path for output directory
    args.output_dir = os.path.abspath(args.output_dir)
    
    # Strip the output files already exist.
    for infile in infiles[:]:
        outpath = getL2AFile(infile, output_dir = args.output_dir)
        
        if os.path.exists(outpath):
            print 'WARNING: The output file %s already exists! Skipping file.'%outpath
    
    if len(infiles) == 0: raise ValueError('No usable level 1C Sentinel-2 files detected in input directory.')
        
    if args.n_processes == 1:
        
        # Keep things simple when using one processor
        for infile in infiles:
            
            main(infile, gipp = args.gipp, output_dir = args.output_dir, resolution = args.resolution, verbose = args.verbose) 
    
    else:

        # Set up function with multiple arguments, and run in parallel
        main_partial = functools.partial(main, gipp = args.gipp, output_dir = args.output_dir, resolution = args.resolution, verbose = args.verbose)
    
        _run_workers(args.n_processes, infiles)
    
    # Test for completion
    completion = np.array([testCompletion(infile, output_dir = args.output_dir, resolution = args.resolution) for infile in infiles])
    
    # Report back
    if completion.sum() > 0: print 'Successfully processed files:'
    for infile in np.array(infiles)[completion == True]:
        print infile 
    if (completion == False).sum() > 0: print 'Files that failed:'
    for infile in np.array(infiles)[completion == False]:
        print infile 

    
    

