#!/usr/bin/env python

import copy
import cv2
import datetime
import glob
import numpy as np
import os
from osgeo import gdal, osr
import re
import scipy.ndimage
import skimage.measure
import subprocess
import tempfile

import pdb

# Test alternate loading of lxml

#import lxml.etree as ET

# This module contains functions to help in image loading, masking, reprojection and modification. It is used by sen2mosaic, sen1mosaic, and deforest tools.



######################
### List functions ###
######################

def prepInfiles(infiles, level, tile = ''):
    """
    Function to select input granules from a directory, .SAFE file (with wildcards) or granule, based on processing level and a tile.
    
    Args:
        infiles: A string or list of input .SAFE files, directories, or granules for Sentinel-2 inputs
        level: Set to either '1C' or '2A' to select appropriate granules.
        tile: Optionally filter infiles to return only those matching a particular tile
    Returns:
        A list of all matching Sentinel-2 granules in infiles.
    """
    
    assert level in ['1C', '2A'], "Sentinel-2 processing level must be either '1C' or '2A'."
    assert bool(re.match("[0-9]{2}[A-Z]{3}$",tile)) or tile == '', "Tile format not recognised. It should take the format '##XXX' (e.g. '36KWA')."
    
    # Make interable if only one item
    if not isinstance(infiles, list):
        infiles = [infiles]
    
    # Get absolute path, stripped of symbolic links
    infiles = [os.path.abspath(os.path.realpath(infile)) for infile in infiles]
    
    # In case infiles is a list of files
    if len(infiles) == 1 and os.path.isfile(infiles[0]):
        with open(infiles[0], 'rb') as infile:
            infiles = [row.rstrip() for row in infile]
    
    # List to collate 
    infiles_reduced = []
    
    for infile in infiles:
         
        # Where infile is a directory:
        infiles_reduced.extend(glob.glob('%s/*_MSIL%s_*/GRANULE/*'%(infile, level)))
        
        # Where infile is a .SAFE file
        if '_MSIL%s_'%level in infile.split('/')[-1]: infiles_reduced.extend(glob.glob('%s/GRANULE/*'%infile))
        
        # Where infile is a specific granule 
        if infile.split('/')[-2] == 'GRANULE': infiles_reduced.extend(glob.glob('%s'%infile))
    
    # Strip repeats (in case)
    infiles_reduced = list(set(infiles_reduced))
    
    # Reduce input to infiles that match the tile (where specified)
    infiles_reduced = [infile for infile in infiles_reduced if ('_T%s'%tile in infile.split('/')[-1])]
    
    # Reduce input files to only L1C or L2A files
    infiles_reduced = [infile for infile in infiles_reduced if ('_MSIL%s_'%level in infile.split('/')[-3])]
    
    return infiles_reduced


def getSourceFilesInTile(scenes, md_dest, start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), verbose = False):
    '''
    Takes a list of source files as input, and determines where each falls within extent of output tile.
    
    Args:
        scenes: A list of utilitites.LoadScene() Sentinel-2 objects
        md_dest: Metadata class from utilities.Metadata() containing output projection details.
        start: Start date to process, in format 'YYYYMMDD' Defaults to start of Sentinel-2 era.
        end: End date to process, in format 'YYYYMMDD' Defaults to today's date.
        verbose: Set True to print progress.
        
    Returns:
        A reduced list of scenes containing only files that will contribute to each tile.
    '''
    
    # Determine which images are within specified tile bounds
    if verbose: print('Searching for source files within specified tile...')
    
    do_tile = []

    for scene in scenes:
        
        # Skip processing the file if image falls outside of tile area
        if scene.testInsideTile(md_dest) and scene.testInsideDate(start = start, end = end):
            do_tile.append(True)
            if verbose: print('    Found one: %s'%scene.granule)
        else:
            do_tile.append(False)
            continue
            
    # Get subset of scenes in specified tile
    scenes_tile = list(np.array(scenes)[np.array(do_tile)])
    
    return scenes_tile


def sortScenes(scenes, by = 'tile'):
    '''
    Function to sort a list of scenes by tile, then by date. This reduces some artefacts in mosaics.
    
    Args:
        scenes: A list of utilitites.LoadScene() Sentinel-2 objects
        by: Set to 'tile' to sort by tile then date, or 'date' to sort by date then tile
    Returns:
        A sorted list of scenes
    '''
    
    scenes_out = []
    
    scenes = np.array(scenes)
    
    dates = np.array([scene.datetime for scene in scenes])
    tiles = np.array([scene.tile for scene in scenes])
    
    if by == 'tile':
        for tile in np.unique(tiles):
            scenes_out.extend(scenes[tiles == tile][np.argsort(dates[tiles == tile])].tolist())
    
    elif by == 'date':
        for date in np.unique(dates):
            scenes_out.extend(scenes[dates == date][np.argsort(tiles[dates == date])].tolist())
    
    return scenes_out

