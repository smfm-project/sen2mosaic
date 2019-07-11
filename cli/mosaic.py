#!/usr/bin/env python

import argparse
import datetime
import numpy as np
import os

import sen2mosaic.core
import sen2mosaic.IO
import sen2mosaic.mosaic

import pdb

#############################################################
### Command line interface for mosaicking Sentinel-2 data ###
#############################################################

def _getBands(resolution):
    '''
    Get a list of Sentinel-2 bands given an input resolution
    
    Args:
        resolution: Sentinel-2 resolution (10, 20, or 60 m)
    Returns:
        A list of resolutions
        A list of band names
    '''
    
    band_list = []
    res_list = []
    
    if resolution == 60 or resolution == 0:
        band_list.extend(['B01','B02','B03','B04','B05','B06','B07','B8A','B09','B11','B12'])
        res_list.extend([60] * 11)
        
    if resolution == 20 or resolution == 0:
        band_list.extend(['B02','B03','B04','B05','B06','B07','B8A','B11','B12'])
        res_list.extend([20] * 9)
        
    if resolution == 10 or resolution == 0:
        band_list.extend(['B02','B03','B04','B08'])
        res_list.extend([10] * 4)
        
    return np.array(res_list), np.array(band_list)



def main(source_files, extent_dest, EPSG_dest, resolution = 0, percentile = 25., level = '1C', start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), improve_mask = False, colour_balance = False, processes = 1, output_dir = os.getcwd(), output_name = 'mosaic', masked_vals = 'auto', temp_dir = '/tmp', verbose = False):
    """main(source_files, extent_dest, EPSG_dest, start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), resolution = 0, improve_mask = False, colour_balance = False, processes = 1, output_dir = os.getcwd(), output_name = 'mosaic', masked_vals = 'auto', temp_dir = '/tmp', verbose = False)
    
    Function to generate seamless mosaics from a list of Sentinel-2 level-2A input files.
        
    Args:
        source_files: A list of level 1C/2A Sentinel-2 input files or a directory.
        extent_dest: List desciribing corner coordinate points in destination CRS [xmin, ymin, xmax, ymax].
        EPSG_dest: EPSG code of destination coordinate reference system. Must be a UTM projection. See: https://www.epsg-registry.org/ for codes.
        resolution: Process 10, 20, or 60 m bands. Defaults to processing all three.
        percentile: Percentile of reflectance to output. Defaults to 25%, which tends to produce good results.
        level: Sentinel-2 level 1C '1C' or level 2A '2A' input data.
        start: Start date to process, in format 'YYYYMMDD' Defaults to start of Sentinel-2 era.
        end: End date to process, in format 'YYYYMMDD' Defaults to today's date.
        improve_mask: Set True to apply improvements Sentinel-2 cloud mask. Not generally recommended.
        processes: Number of processes to run similtaneously. Defaults to 1.
        output_dir: Optionally specify an output directory.
        output_name: Optionally specify a string to precede output file names. Defaults to 'mosaic'.
        masked_vals: List of SLC mask values to not include in the final mosaic. Defaults to 'auto', which masks everything except [4,5,6]
        temp_dir: Directory to temporarily write L1C mask files. Defaults to /tmp
        verbose: Make script verbose (set True).
    """
    
    # Get output bands based on input resolution
    res_list, band_list = _getBands(resolution)
    
    # For each of the input resolutions
    for res in np.unique(res_list)[::-1]:

        # Build metadata of output object
        md_dest = sen2mosaic.core.Metadata(extent_dest, res, EPSG_dest)
        
        # Only output one mask layer
        output_mask = True
        for band in band_list[res_list==res]:
            
            if verbose: print('Building band %s at %s m resolution'%(band, str(res)))
            
            # Build composite image for list of input scenes
            band_out, QA_out = sen2mosaic.mosaic.buildComposite(source_files, band, md_dest, level = level, resolution = resolution, output_dir = output_dir, output_name = output_name, start = start, end = end, colour_balance = colour_balance, improve_mask = improve_mask, percentile = 25., processes = processes, step = 2000, masked_vals = masked_vals, temp_dir = temp_dir, verbose = verbose, output_mask = output_mask)            
            
            # Only output mask on first iteration
            output_mask = False
            
        # Build VRT output files for straightforward visualisation
        if verbose: print('Building .VRT images for visualisation')
        
        # Natural colour image (10 m)
        sen2mosaic.mosaic.buildVRT('%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B02.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_RGB.vrt'%(output_dir, output_name, str(res)))

        # Near infrared image. Band at (10 m) has a different format to bands at 20 and 60 m.
        if res == 10:
            sen2mosaic.mosaic.buildVRT('%s/%s_R%sm_B08.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_NIR.vrt'%(output_dir, output_name, str(res)))    
        else:
            sen2mosaic.mosaic.buildVRT('%s/%s_R%sm_B8A.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_NIR.vrt'%(output_dir, output_name, str(res)))
        
    if verbose: print('Processing complete!')


if __name__ == "__main__":
    
    # Set up command line parser    

    parser = argparse.ArgumentParser(description = "Process Sentinel-2 data to a composite mosaic product to a customisable grid square, based on specified UTM coordinate bounds. Data are output as GeoTiff files for each spectral band, with .vrt files for ease of visualisation.")

    parser._action_groups.pop()
    positional = parser.add_argument_group('positional arguments')
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    
    # Positional arguments
    positional.add_argument('infiles', metavar = 'PATH', type = str, default = [os.getcwd()], nargs = '*', help = 'Sentinel 2 input files (level 1C/2A) in .SAFE format. Specify one or more valid Sentinel-2 .SAFE, a directory containing .SAFE files, a Sentinel-2 tile or multiple granules through wildcards (e.g. *.SAFE/GRANULE/*), or a file containing a list of input files. Leave blank to process files in current working directoy. All granules that match input conditions will be included.')
    
    # Required arguments
    required.add_argument('-te', '--target_extent', nargs = 4, metavar = ('XMIN', 'YMIN', 'XMAX', 'YMAX'), type = float, required = True, help = "Extent of output image tile, in format <xmin, ymin, xmax, ymax>.")
    required.add_argument('-e', '--epsg', metavar = 'EPSG', type=int, required = True, help="EPSG code for output image tile CRS. This must be UTM. Find the EPSG code of your output CRS as https://www.epsg-registry.org/.")
    required.add_argument('-res', '--resolution', metavar = 'm', type=int, help="Specify a resolution in metres.")

    # Optional arguments
    optional.add_argument('-l', '--level', type=str, metavar='1C/2A', default = '2A', help = "Input image processing level, '1C' or '2A'. Defaults to '2A'.")
    optional.add_argument('-st', '--start', type = str, default = '20150101', help = "Start date for tiles to include in format YYYYMMDD. Defaults to processing all dates.")
    optional.add_argument('-en', '--end', type = str, default = datetime.datetime.today().strftime('%Y%m%d'), help = "End date for tiles to include in format YYYYMMDD. Defaults to processing all dates.")
    optional.add_argument('-pc', '--percentile', metavar = 'PC', type=float, default = 25., help="Specify a percentile of reflectance to output. Defaults to 25 percent, which tends to produce good results.")
    optional.add_argument('-m', '--masked_vals', metavar = 'N', type=str, nargs='*', default = ['auto'], help="Specify SLC values to not include in the mosaic (e.g. -m 7 8 9). See http://step.esa.int/main/third-party-plugins-2/sen2cor/ for description of sen2cor mask values. Defaults to 'auto', which masks values 0 and 9. Also accepts 'none', to include all values.")
    optional.add_argument('-b', '--colour_balance', action='store_true', default = False, help = "Perform colour balancing between tiles. Not generally recommended, particularly where working over large areas. Defaults to False.")
    optional.add_argument('-i', '--improve_mask', action='store_true', default = False, help = "Apply improvements to Sentinel-2 cloud mask. Not generally recommended, except where a very conservative mask is desired. Defaults to no improvement.")
    optional.add_argument('-t', '--temp_dir', type=str, metavar = 'DIR', default = '/tmp', help="Directory to write temporary files, only required for L1C data. Defaults to '/tmp'.")
    optional.add_argument('-o', '--output_dir', type=str, metavar = 'DIR', default = os.getcwd(), help="Specify an output directory. Defaults to the present working directory.")
    optional.add_argument('-n', '--output_name', type=str, metavar = 'NAME', default = 'mosaic', help="Specify a string to precede output filename. Defaults to 'mosaic'.")
    optional.add_argument('-p', '--n_processes', type = int, metavar = 'N', default = 1, help = "Specify a maximum number of tiles to process in paralell. Bear in mind that more processes will require more memory. Defaults to 1.")
    optional.add_argument('-v', '--verbose', action='store_true', default = False, help = "Make script verbose.")
    
    # Get arguments
    args = parser.parse_args()
        
    # Convert masked_vals to integers, where specified
    if args.masked_vals != ['auto'] and args.masked_vals != ['none']:
        masked_vals = [int(m) for m in args.masked_vals]
    else:
        masked_vals = args.masked_vals[0]
        
    # Get absolute path of input .safe files.
    infiles = sorted([os.path.abspath(i) for i in args.infiles])
        
    # Find all matching granule files
    #infiles = sen2mosaic.IO.prepInfiles(infiles, args.level)
    
    main(infiles, args.target_extent, args.epsg, resolution = args.resolution, percentile = args.percentile, level = args.level, start = args.start, end = args.end, improve_mask = args.improve_mask, colour_balance = args.colour_balance, processes = args.n_processes, output_dir = args.output_dir, output_name = args.output_name, masked_vals = masked_vals, temp_dir = args.temp_dir, verbose = args.verbose)
    
    
