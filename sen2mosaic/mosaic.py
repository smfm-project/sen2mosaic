#!/usr/bin/env python

import argparse
import datetime
import glob
import numpy as np
import os
from scipy import ndimage
from scipy import interpolate
import subprocess

import utilities

import pdb

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def _createOutputArray(md, dtype = np.uint16):
    '''
    Create an output array from Metadata class from utilities.Metadata().
    
    Args:
        md: Metadata class from utilities.Metadata()
    
    Returns:
        A numpy array sized to match the specification of the utilities.Metadata() class.
    '''
    
    output_array = np.zeros((md.nrows, md.ncols), dtype = dtype)
    
    return output_array


def _createGdalDataset(md, data_out = None, filename = '', driver = 'MEM', dtype = 3, options = []):
    '''
    Function to create an empty gdal dataset with georefence info from Metadata class.

    Args:
        md: Metadata class from utilities.Metadata().
        data_out: Optionally specify an array of data to include in the gdal dataset.
        filename: Optionally specify an output filename, if image will be written to disk.
        driver: GDAL driver type (e.g. 'MEM', 'GTiff'). By default this function creates an array in memory, but set driver = 'GTiff' to make a GeoTiff. If writing a file to disk, the argument filename must be specified.
        dtype: Output data type. Default data type is a 16-bit unsigned integer (gdal.GDT_Int16, 3), but this can be specified using GDAL standards.
        options: A list containing other GDAL options (e.g. for compression, use [compress='LZW'].

    Returns:
        A GDAL dataset.
    '''
    
    from osgeo import gdal
    
    gdal_driver = gdal.GetDriverByName(driver)
    ds = gdal_driver.Create(filename, md.ncols, md.nrows, 1, dtype, options = options)
    ds.SetGeoTransform(md.geo_t)
    ds.SetProjection(md.proj.ExportToWkt())
    
    # If a data array specified, add it to the gdal dataset
    if type(data_out).__module__ == np.__name__:
        ds.GetRasterBand(1).WriteArray(data_out)
    
    # If a filename is specified, write the array to disk.
    if filename != '':
        ds = None
    
    return ds


def _reprojectImage(ds_source, ds_dest, md_source, md_dest):
    '''
    Reprojects a source image to match the coordinates of a destination GDAL dataset.
    
    Args:
        ds_source: A gdal dataset from _createGdalDataset() containing data to be repojected.
        ds_dest: A gdal dataset from _createGdalDataset(), with destination coordinate reference system and extent.
        md_source: Metadata class from utilities.Metadata() representing the source image.
        md_dest: Metadata class from utilities.Metadata() representing the destination image.
    
    Returns:
        A GDAL array with resampled data
    '''
    
    from osgeo import gdal
    
    proj_source = md_source.proj.ExportToWkt()
    proj_dest = md_dest.proj.ExportToWkt()
    
    # Reproject source into dest project coordinates
    gdal.ReprojectImage(ds_source, ds_dest, proj_source, proj_dest, gdal.GRA_NearestNeighbour)
            
    ds_resampled = ds_dest.GetRasterBand(1).ReadAsArray()
    
    return ds_resampled



def _updateMaskArrays(scl_out, scl_resampled, image_n, n, algorithm = 'TEMP_HOMOGENEITY'):
    '''
    Function to update contents of scl and image_n arrays.
    
    Args:
        scl_out: A numpy array representing the mask to be output. Should be initialised to an array of 0s.
        scl_resampled: A numpy array containing resampled data to be added to the scl_out.
        image_n: A numpy array to record the image number for each pixel.
        n: An integer describing the image number (first image = 1, second image = 2 etc.)
    
    Returns:
        The scl_out array with pixels from scl_resampled added.
        The image_n array describing which image each pixel is sources from.
    '''
    
    assert algorithm in ['MOST_RECENT', 'MOST_DISTANT', 'TEMP_HOMOGENEITY'], "Compositing algorithm (%s) not recognised."%str(algorithm)
    
    # Keep pixels where the mask has a value 4 to 6
    good_px = np.logical_and(scl_resampled >= 4, scl_resampled <= 6)
    #other_px = np.logical_and(scl_resampled > 0, good_px == False)
    
    if algorithm == 'MOST_RECENT':
        
        # Select all pixels that have data in this image, or some usable data where no good data already exist
        selection = good_px
        #selection = np.logical_or(good_px, np.logical_and(other_px, np.logical_or(scl_out < 4, scl_out > 6)))
        
    elif algorithm == 'MOST_DISTANT':
        
        # Select only pixels which have new data, and have not already had data allocated
        selection = np.logical_and(np.logical_or(scl_out < 4, scl_out > 6), good_px)
        #selection = np.logical_or(selection, np.logical_and(other_px, scl_out == 0))
        
    
    elif algorithm == 'TEMP_HOMOGENEITY':
        
        # Replace any unmeasured pixels with 'good' values
        selection = np.logical_and(good_px, image_n == 0)
                
        # Also replace pixels where sum of current good pixels greater than those already in the output for a given tile
        _, counts = np.unique(image_n[np.logical_and(image_n > 0, scl_resampled != 0)], return_counts = True)
        
        # For every image past the first, replace all pixels with good_px if the result is a more homogenous image
        if counts.size != 0:
            if np.sum(good_px) > counts.max():
                selection = np.logical_or(selection, good_px)
                        
    else:
        raise
    
    # Update SCL code in each newly assigned pixel
    scl_out[selection] = scl_resampled[selection]
    
    # Update the image each pixel has come from
    image_n[selection] = n
    
    # Set unfilled pixels to zero
    image_n[np.logical_or(scl_out < 4, scl_out > 6)] = 0
    
    return scl_out, image_n


def _updateBandArray(data_out, data_resampled, image_n, n, scl_resampled):
    '''
    Function to update contents of output array based on image_n array.
    
    Args:
        data_out: A numpy array representing the band data to be output.
        data_resampled: A numpy array containing resampled band data to be added to data_out.
        image_n: A numpy array representing the image number from _updateMaskArrays().
        n: An integer describing the image number (first image = 1, second image = 2 etc.).
        scl_resampled: A numpy array representing the SCL mask for data_resampled
    
    Returns:
        The data_out array with pixels from data_resampled added.
        
    '''
                
    # Find pixels that can be replaced in this image (valid, or selected). Add all valid, to aid with colour balancing between scenes.
    #selection = np.logical_and(np.logical_or(image_n == n, data_out == 0),np.logical_and(scl_resampled>=4,scl_resampled<=6))
    selection = image_n == n
    
    # Add good data to data_out array
    data_out[selection] = data_resampled[selection]
    
    return data_out

    
def loadMask(scene, md_dest, correct = False):
    '''
    Funciton to load, correct and reproject a Sentinel-2 mask array.
    
    Args:
        scenes: A level-2A scene of class utilties.LoadScene().
        md_dest: An object of class utilties.Metadata() to reproject image to.
        correct: Set to True to perform corrections to sen2cor mask.
    
    Returns:
        A numpy array of resampled mask data
    '''
    
    # Write mask array to a gdal dataset
    ds_source = _createGdalDataset(scene.metadata, data_out = scene.getMask(correct = correct), dtype = 3)
        
    # Create an empty gdal dataset for destination
    ds_dest = _createGdalDataset(md_dest, dtype = 1)
    
    # Reproject source to destination projection and extent
    scl_resampled = _reprojectImage(ds_source, ds_dest, scene.metadata, md_dest)
    
    return scl_resampled


def generateSCLArray(scenes, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', algorithm = 'TEMP_HOMOGENEITY', correct_mask = True, verbose = False):
    '''generateSCLArray(scenes, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', algorithm = 'TEMP_HOMOGENEITY', verbose = False)
    
    Function which generates an mask GeoTiff file from list of level 2A source files for a specified output band and extent, and an array desciribing which source_image each pixel comes from

    Args:
        scenes: A list of level 2A inputs (of class LoadScene).
        md_dest: Metadata class from utilities.Metadata() containing output projection details.
        output_dir: Optionally specify directory for output file. Defaults to current working directory.
        output_name: Optionally specify a string to prepend to output files. Defaults to 'mosaic'.
        algorithm: Image compositing algorithm. Choose from 'MOST_RECENT', 'MOST_DISTANT', and 'TEMP_HOMOGENEITY'. Defaults to TEMP_HOMOGENEITY.
        verbose: Set True for printed updates.

    Returns:
        A numpy array containing mosaic data for the input band.
        A numpy array describing the image number each pixel is sourced from. 0 = No data, 1 = first scene, 2 = second scene etc.
    '''
    
    # Sort input scenes
    scenes = utilities.sortScenes(scenes)
    
    # Create array to contain output classified cloud mask array
    scl_out = _createOutputArray(md_dest, dtype = np.uint8)
    
    # Create array to contain record of the number of source image
    image_n = _createOutputArray(md_dest, dtype = np.uint16) 
    
    for n, scene in enumerate(scenes):
        
        if verbose: print '    Getting pixels from %s'%scene.filename.split('/')[-1]
        
        # Reproject mask
        scl_resampled = loadMask(scene, md_dest, correct = correct_mask)
        
        # Add reprojected data to SCL output array
        scl_out, image_n = _updateMaskArrays(scl_out, scl_resampled, image_n, n + 1, algorithm = algorithm)
    
    if verbose: print 'Outputting SCL mask'
    
    # Write output cloud mask to disk for each resolution
    ds_out = _createGdalDataset(md_dest, data_out = scl_out,
                               filename = '%s/%s_R%sm_SCL.tif'%(output_dir, output_name, str(scene.resolution)),
                               driver='GTiff', dtype = 1, options = ['COMPRESS=LZW'])
    
    ds_out = _createGdalDataset(md_dest, data_out = image_n,
                               filename = '%s/%s_R%sm_imageN.tif'%(output_dir, output_name, str(scene.resolution)),
                               driver='GTiff', dtype = 2, options = ['COMPRESS=LZW'])

    return scl_out, image_n


def loadBand(scene, band, md_dest):
    '''
    Funciton to load and reproject a Sentinel-2 band array.
    
    Args:
        scenes: A level-2A scene of class utilties.LoadScene().
        band: The name of a band to load (e.g. 'B02')
        md_dest: An object of class utilties.Metadata() to reproject image to.
    
    Returns:
        A numpy array of resampled data
    '''
    
    # Write array to a gdal dataset
    ds_source = _createGdalDataset(scene.metadata, data_out = scene.getBand(band))                

    # Create an empty gdal dataset for destination
    ds_dest = _createGdalDataset(md_dest, dtype = 2)
            
    # Reproject source to destination projection and extent
    data_resampled = _reprojectImage(ds_source, ds_dest, scene.metadata, md_dest)    
    
    return data_resampled



def _getImageOrder(scenes, image_n):
    '''
    Sort tiles, so that most populated is processed first to improve quality of colour balancing
    
    Args:
        scenes: A list of level 2A inputs (of class LoadScene).
        image_n: An array of integers from generateSCLArray(), which describes the scene that each pixel should come from. 0 = No data, 1 = first scene, 2 = second scene etc.
    '''
    
    def _getCentre(scene, ref_scene):
        '''
        Function to get centre point from scene in CRS of ref_scene
        '''
        from osgeo import osr
        
        # Set up function to translate coordinates from source to destination CRS for each scene
        tx = osr.CoordinateTransformation(ref_scene.metadata.proj, scene.metadata.proj)
        
        # And translate the source coordinates
        x_min, y_min, z = tx.TransformPoint(scene.extent[0], scene.extent[1])
        x_max, y_max, z = tx.TransformPoint(scene.extent[2], scene.extent[3])
        
        return ((y_max - y_min) / 2.) + y_min, ((x_max - x_min) / 2.) + x_min
        
        
    # tile_count = Number of included pixels by tile
    # tile_name  = Granule name in format T##XXX
    # tile_total = Total number of pixels from all images of each tile_count
    # tile_dist  = Euclidean distance to reference tile (in ref tile units)
    
    num, count = np.unique(image_n[image_n!=0], return_counts = True)
    num_sorted = zip(*sorted(zip(count,num), reverse = True))[1]
    tile_count = np.zeros(len(scenes), dtype=np.int)
    tile_count[num-1] = count
    
    tile_name = np.array([scene.tile for scene in scenes])
    
    tile_total = np.zeros(len(scenes),dtype=np.int)
    for tile in np.unique(tile_name):
        tile_total[tile_name == tile] = np.sum(tile_count[tile_name == tile])
    
    # Get reference scene
    ref_scene = np.array(scenes)[tile_total==np.max(tile_total)][0]
    
    tile_dist = []
    
    ref_y, ref_x = _getCentre(ref_scene, ref_scene)
    for n, scene in enumerate(scenes):
        y, x = _getCentre(scene, ref_scene)
        tile_dist.append((((y - ref_y)**2) + ((x - ref_x)**2)) ** 0.5)
    tile_dist = np.array(tile_dist)
    
    # Sort first by distance to refernece tile, then tile name (some tiles are equidistant), then then by contribution of pixels from each overpass. This improves the quality of colour balancing.
    tile_number = np.lexsort((tile_count, tile_name, tile_dist*-1))[::-1] + 1
    
    # Exclude tiles where no data are used
    tile_number = tile_number[tile_count[tile_number-1] > 0]
    
    return tile_number


def generateBandArray(scenes, image_n, band, scl_out, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', colour_balance = 'none', verbose = False):
    """generateBandArray(scenes, image_n, band, scl_out, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False)
    
    Function which generates an output GeoTiff file from list of level 3B source files for a specified output band and extent.

    Args:
        scenes: A list of level 2A inputs (of class LoadScene).
        image_n: An array of integers from generateSCLArray(), which describes the scene that each pixel should come from. 0 = No data, 1 = first scene, 2 = second scene etc.
        band: String describing bad to process. e.g. B02, B03, B8A....
        scl_out: Numpy array with mask from generateSCLArray().
        md_dest: Metadata class from utilities.Metadata() containing output projection details.
        output_dir: Optionally specify directory for output file. Defaults to current working directory.
        output_name: Optionally specify a string to prepend to output files. Defaults to 'mosaic'.
        
    Returns:
        A numpy array containing mosaic data for the input band.
    """
    
    
    # Create array to contain output array for this band
    data_out = _createOutputArray(md_dest, dtype = np.uint16)
    
    # Get data for each image_n
    dates = [scene.datetime.date() for scene in scenes]
    
    # For each source file that contributes pixels
    for n in _getImageOrder(scenes, image_n): #tile_number[tile_count[tile_number-1] > 0]:
                
        # Select scene
        scene = scenes[n-1]
                
        if verbose: print '    Getting pixels from %s'%scene.filename.split('/')[-1]
        
        # Load data and mask
        data_resampled = loadBand(scene, band, md_dest)
        scl_resampled = loadMask(scene, md_dest, correct = True)

        # Perform basic colour balancing by histogram matching
        if colour_balance != 'none':
            
            # Skip first image
            if data_out.sum() != 0:
                
                # Add mask to data_resampled
                data_resampled_ma = np.ma.array(data_resampled, mask = np.logical_or(scl_resampled < 4, scl_resampled > 6))
                
                # Calculate overlap with other images
                overlap = np.logical_and(data_resampled_ma.mask == False, data_out != 0)
                
                # Calculate percent overlap between images
                this_overlap = float(overlap.sum()) / (data_resampled_ma.mask ==False).sum()
                                
                if this_overlap > 0.02 and this_overlap <= 0.5 and colour_balance == 'aggressive':
                    
                    if verbose: print '        scaling'
                                                            
                    sel = np.logical_and(data_resampled_ma.mask == False, scl_resampled != 6)
                    
                    # Gain compensation (simple inter-scene correction)                    
                    this_intensity = np.mean(data_resampled[overlap])
                    ref_intensity = np.mean(data_out[overlap])
                    
                    data_resampled[sel] = np.round(data_resampled[sel] * (ref_intensity/this_intensity),0).astype(np.uint16)
                    
                elif this_overlap > 0.5:
                    
                    if verbose: print '        matching'
                    
                    data_resampled = utilities.histogram_match(data_resampled_ma, np.ma.array(data_out, mask = data_out == 0)).data
                    
                else:
                    
                    if verbose: print '        adding'
                
                
        # Add reprojected data to band output array at appropriate image_n
        data_out = _updateBandArray(data_out, data_resampled, image_n, n, scl_resampled)
        
        
    if verbose: print 'Outputting band %s'%band
    
    # Write output for this band to disk
    ds_out = _createGdalDataset(md_dest, data_out = data_out,
                                filename = '%s/%s_R%sm_%s.tif'%(output_dir, output_name, str(scene.resolution), band),
                                driver='GTiff', dtype = 2, options = ['COMPRESS=LZW'])

    return data_out


def buildVRT(red_band, green_band, blue_band, output_path):
    """
    Builds a three band RGB vrt for image visualisation. Outputs a .VRT file.
    
    Args:
        red_band: Filename to add to red band
        green_band: Filename to add to green band
        blue_band: Filename to add to blue band
        output_name: Path to output file
    """
    
    # Remove trailing / from output directory name if present
    output_path = output_path.rstrip('/')
    
    # Ensure output name is a VRT
    if output_path[-4:] != '.vrt':
        output_path += '.vrt'
    
    command = ['gdalbuildvrt', '-separate', '-overwrite']
    command += [output_path, red_band, green_band, blue_band]
    
    subprocess.call(command)

def _getBands(resolution):
    '''
    Get bands and resolutions for each
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

    
        
def main(source_files, extent_dest, EPSG_dest, start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), algorithm = 'TEMP_HOMOGENEITY', colour_balance = 'none', resolution = 0, correct_mask = True, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False):
    """main(source_files, extent_dest, EPSG_dest, start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d'), algorithm = 'TEMP_HOMOGENEITY', colour_balance = 'none', resolution = 0, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False)
    
    Function to generate seamless mosaics from a list of Sentinel-2 level-2A input files.
        
    Args:
        source_files: A list of level 3A input files.
        extent_dest: List desciribing corner coordinate points in destination CRS [xmin, ymin, xmax, ymax].
        EPSG_dest: EPSG code of destination coordinate reference system. Must be a UTM projection. See: https://www.epsg-registry.org/ for codes.
        start: Start date to process, in format 'YYYYMMDD' Defaults to start of Sentinel-2 era.
        end: End date to process, in format 'YYYYMMDD' Defaults to today's date.
        algorithm: Image compositing algorithm. Choose from 'MOST_RECENT', 'MOST_DISTANT', and 'TEMP_HOMOGENEITY'. Defaults to TEMP_HOMOGENEITY.
        colour_balance: Set to 'none', 'basic' or 'aggressive'
        resolution: Process 10, 20, or 60 m bands. Defaults to processing all three.
        correct_mask: Set True to apply improvements to mask from sen2cor.
        output_dir: Optionally specify an output directory.
        output_name: Optionally specify a string to precede output file names. Defaults to 'mosaic'.
        verbose: Make script verbose (set True).
    """

    assert len(extent_dest) == 4, "Output extent must be specified in the format [xmin, ymin, xmax, ymax]"
    assert len(source_files) >= 1, "No source files in specified location."
    assert resolution in [0, 10, 20, 60], "Resolution must be 10, 20, or 60 m, or 0 to process all three."
    assert colour_balance in ['none', 'basic', 'aggressive'], "colour_balance must be 'none', 'basic', or 'aggressive'."
    assert type(correct_mask) == bool, "correct_mask can only be set to True or False."
    
    # Remove trailing / from output directory if present 
    output_dir = output_dir.rstrip('/')
    
    res_list, band_list = _getBands(resolution)
    
    # For each of the input resolutions
    for res in np.unique(res_list)[::-1]:
                
        # Load metadata for all Sentinel-2 datasets
        scenes = [utilities.LoadScene(source_file, resolution = res) for source_file in source_files]
        
        # Build metadata of output object
        md_dest = utilities.Metadata(extent_dest, res, EPSG_dest)
        
        # Reduce the pool of scenes to only those that overlap with output tile
        scenes_tile = utilities.getSourceFilesInTile(scenes, md_dest, start = start, end = end, verbose = verbose)       
        
        # It's only worth processing a tile if at least one input image is inside tile
        if len(scenes_tile) == 0:
            print "    No data inside specified tile for resolution %s. Skipping."%str(res)
            continue
        
        # Sort scenes to minimise artefacts
        scenes_tile = utilities.sortScenes(scenes_tile)
        
        if verbose: print 'Doing SCL mask at %s m resolution'%str(res)
        
        # Generate a classified mask
        scl_out, image_n = generateSCLArray(scenes_tile, md_dest, output_dir = output_dir, output_name = output_name, algorithm = algorithm, correct_mask = correct_mask, verbose = verbose)

        # Process images for each band
        for band in band_list[res_list==res]:
            
            if verbose: print 'Doing band %s at %s m resolution'%(band, str(res))
            
            # Using image_n, combine pixels into outputs images for each band
            band_out = generateBandArray(scenes_tile, image_n, band, scl_out, md_dest, output_dir = output_dir, output_name = output_name, colour_balance = colour_balance, verbose = verbose)
    
        # Build VRT output files for straightforward visualisation
        if verbose: print 'Building .VRT images for visualisation'
        
        # Natural colour image (10 m)
        buildVRT('%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B02.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_RGB.vrt'%(output_dir, output_name, str(res)))

        # Near infrared image. Band at (10 m) has a different format to bands at 20 and 60 m.
        if res == 10:
            buildVRT('%s/%s_R%sm_B08.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_NIR.vrt'%(output_dir, output_name, str(res)))    
        else:
            buildVRT('%s/%s_R%sm_B8A.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_NIR.vrt'%(output_dir, output_name, str(res)))
        
    print 'Processing complete!'



if __name__ == "__main__":
    
    # Set up command line parser    

    parser = argparse.ArgumentParser(description = "Process Sentinel-2 level 2A data to a composite mosaic product. This script mosaics data into a customisable grid square, based on specified UTM coordinate bounds. Files are output as GeoTiffs, which are easier to work with than JPEG2000 files.")

    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')

    # Required arguments
    required.add_argument('-te', '--target_extent', nargs = 4, metavar = ('XMIN', 'YMIN', 'XMAX', 'YMAX'), type = float, help = "Extent of output image tile, in format <xmin, ymin, xmax, ymax>.")
    required.add_argument('-e', '--epsg', type=int, help="EPSG code for output image tile CRS. This must be UTM. Find the EPSG code of your output CRS as https://www.epsg-registry.org/.")
    
    # Optional arguments
    optional.add_argument('infiles', metavar = 'L2A_FILES', type = str, default = [os.getcwd()], nargs = '*', help = 'Sentinel 2 input files (level 2A) in .SAFE format. Specify one or more valid Sentinel-2 .SAFE, a directory containing .SAFE files, or multiple granules through wildcards (e.g. *.SAFE/GRANULE/*). Defaults to processing all granules in current working directory.')
    optional.add_argument('-st', '--start', type = str, default = '20150101', help = "Start date for tiles to include in format YYYYMMDD. Defaults to processing all dates.")
    optional.add_argument('-en', '--end', type = str, default = datetime.datetime.today().strftime('%Y%m%d'), help = "End date for tiles to include in format YYYYMMDD. Defaults to processing all dates.")
    optional.add_argument('-r', '--resolution', metavar = 'N', type=int, default = 0, help="Specify a resolution to process (10, 20, 60, or 0 for all).")
    optional.add_argument('-a', '--algorithm', type=str, metavar='NAME', default = 'TEMP_HOMOGENEITY', help="Optionally specify an image compositing algorithm ('MOST_RECENT', 'MOST_DISTANT', 'TEMP_HOMOGENEITY'). Defaults to 'TEMP_HOMOGENEITY'.")
    optional.add_argument('-b', '--balance', type=str, default='none', help="Perform colour balancing when generating composite images ('none', 'basic' or 'aggressive'). Defaults to none.")
    optional.add_argument('-c', '--correct_mask', action='store_true', default = False, help = "Apply improvements to sen2cor cloud mask.")
    optional.add_argument('-o', '--output_dir', type=str, metavar = 'DIR', default = os.getcwd(), help="Specify an output directory. Defaults to the present working directory.")
    optional.add_argument('-n', '--output_name', type=str, metavar = 'NAME', default = 'mosaic', help="Specify a string to precede output filename. Defaults to 'mosaic'.")
    optional.add_argument('-v', '--verbose', action='store_true', default = False, help = "Make script verbose.")
    
    # Get arguments
    args = parser.parse_args()
    
    # Get absolute path of input .safe files.
    infiles = [os.path.abspath(i) for i in args.infiles]
    
    # Find all matching granule files
    infiles = utilities.prepInfiles(infiles, '2A')
    
    main(infiles, args.target_extent, args.epsg, resolution = args.resolution, start = args.start, end = args.end, algorithm = args.algorithm, colour_balance = args.balance, correct_mask = args.correct_mask, output_dir = args.output_dir, output_name = args.output_name, verbose = args.verbose)
    
    
