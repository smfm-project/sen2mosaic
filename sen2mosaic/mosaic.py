#!/usr/bin/env python

import argparse
import glob
import glymur
import numpy as np
import os
from scipy import ndimage
import subprocess

import utilties

import pdb

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def _createOutputArray(md, dtype = np.uint16):
    '''
    Create an output array from metadata dictionary.
    
    Args:
        md: A metadata dictionary created by buildMetadataDictionary().
    
    Returns:
        A numpy array sized to match the specification of the metadata dictionary.
    '''
    
    output_array = np.zeros((md.nrows, md.ncols), dtype = dtype)
    
    return output_array


def _sortSourceFiles(source_files):
    '''
    When building a large mosaic, it's necessary for input tiles to be in a consistent order to avoid strange overlap artefacts. This function sorts a list of safe files in alphabetical order by their tile reference.
    
    Args:
        source_files: A list of level 3A Sentinel-2 .SAFE files.
    
    Returns:
        A list of source_files alphabetised by tile name.
    '''
    
    source_files.sort(key = lambda x: x.split('/')[-1].split('_T')[1])
    
    return source_files




def _createGdalDataset(md, data_out = None, filename = '', driver = 'MEM', dtype = 3, options = []):
    '''
    Function to create an empty gdal dataset with georefence info from metadata dictionary.

    Args:
        md: A metadata dictionary created by buildMetadataDictionary().
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
        md_source: A metadata dictionary created by buildMetadataDictionary() representing the source image.
        md_dest: A metadata dictionary created by buildMetadataDictionary() representing the destination image.
    
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


def _testOutsideTile(md_source, md_dest):
    '''
    Function that uses metadata class to test whether any part of a source data falls inside destination tile.
    
    Args:
        md_source: A metadata dictionary created by buildMetadataDictionary() representing the source image.
        md_dest: A metadata dictionary created by buildMetadataDictionary() representing the destination image.
        
    Returns:
        A boolean (True/False) value.
    '''
    
    import osr
            
    # Set up function to translate coordinates from source to destination
    tx = osr.CoordinateTransformation(md_source.proj, md_dest.proj)
         
    # And translate the source coordinates
    md_source.ulx, md_source.uly, z = tx.TransformPoint(md_source.ulx, md_source.uly)
    md_source.lrx, md_source.lry, z = tx.TransformPoint(md_source.lrx, md_source.lry)   
    
    out_of_tile =  md_source.ulx >= md_dest.lrx or \
                   md_source.lrx <= md_dest.ulx or \
                   md_source.uly <= md_dest.lry or \
                   md_source.lry >= md_dest.uly
    
    return out_of_tile


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
        
    if algorithm == 'MOST_RECENT':
        
        # Select all pixels that have data in this image
        selection = good_px
        
    elif algorithm == 'MOST_DISTANT':
        
        # Select only pixels which have new data, and have not already had data allocated
        selection = np.logical_and(image_n == 0, good_px)
    
    elif algorithm == 'TEMP_HOMOGENEITY':
        
        # Automatically replace any unmeaured pixels
        selection = image_n == 0
        
        # Also replace pixels where sum of current good pixels greater than those already in the output
        _, counts = np.unique(image_n[image_n > 0], return_counts = True)
        
        if counts.size == 0:
            # For first image
            selection = good_px
        elif np.sum(good_px) > counts.max():
            selection = good_px
    
    else:
        raise
        
    # Update SCL code in each newly assigned pixel
    scl_out[selection] = scl_resampled[selection]
    
    # Update the image each pixel has come from
    image_n[selection] = n
    image_n[np.logical_or(scl_out < 4, scl_out > 6)] = 0
    
    return scl_out, image_n


def _updateBandArray(data_out, data_resampled, image_n, n, scl_out):
    '''
    Function to update contents of output array based on image_n array.
    
    Args:
        data_out: A numpy array representing the band data to be output.
        data_resampled: A numpy array containing resampled band data to be added to data_out.
        image_n: A numpy array representing the image number from _updateMaskArrays().
        n: An integer describing the image number (first image = 1, second image = 2 etc.).
        scl_out: A numpy array representing the SCL mask from _updateMaskArrays().
    
    Returns:
        The data_out array with pixels from data_resampled added.
        
    '''
    
    # Find pixels that need replacing in this image
    selection = image_n == n
    
    # Add good data to data_out array
    data_out[selection] = data_resampled[selection]
        
    # Set bad values from scl mask to 0, to keep things tidy
    #for i in [1, 2, 3, 8, 9, 10, 11, 12]:
    #    data_out[selection][scl_out[selection] == i] = 0

    return data_out



def getSourceFilesInTile(source_files, md_dest, verbose = False):
    '''
    Takes a list of source files as input, and determines where each falls within extent of output tile.
    
    Args:
        source_files: A list of level 3A input files.
        md_dest: Dictionary from buildMetaDataDictionary() containing output projection details.

    Returns:
        A reduced list of source_files containing only files that will contribute to each tile.
    '''
    
    # Determine which L3A images are within specified tile bounds
    if verbose: print 'Searching for source files within specified tile...'
    
    do_tile = []
    
    for source_file in source_files:
        
        # Skip processing the file if image falls outside of tile area
        if _testOutsideTile(source_file.metadata, md_dest):
            do_tile.append(False)
            continue
        
        if verbose: print '    Found one: %s'%source_file.filename
        do_tile.append(True)
    
    # Get subset of source_files in specified tile
    source_files_tile = list(np.array(source_files)[np.array(do_tile)])
    
    return source_files_tile


def sortScenes(scenes):
    '''
    Function to sort a list of scenes by tile, then by date. This reduces some artefacts in mosaics.
    
    Args:
        scenes: A list of LoadScene() Sentinel-2 objects
    Returns:
        A sorted list of scenes
    '''
    
    scenes_out = []
    
    scenes = np.array(scenes)
    
    dates = np.array([scene.datetime for scene in scenes])
    tiles = np.array([scene.tile for scene in scenes])
    
    for tile in np.unique(tiles):
        scenes_out.extend(scenes[tiles == tile][np.argsort(dates[tiles == tile])].tolist())
       
    return scenes_out
    


def generateSCLArray(scenes, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False):
    '''generateSCLArray(source_files, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False)
    
    Function which generates an mask GeoTiff file from list of level 2A source files for a specified output band and extent, and an array desciribing which source_image each pixel comes from

    Args:
        scenes: A list of level 2A inputs (of class LoadScene).
        md_dest: Dictionary from buildMetaDataDictionary() containing output projection details.
        output_dir: Optionally specify directory for output file. Defaults to current working directory.
        output_name: Optionally specify a string to prepend to output files. Defaults to 'L3B_output'.
        
    Returns:
        A numpy array containing mosaic data for the input band.
        A numpy array describing the image number each pixel is sourced from. 0 = No data, 1 = first scene, 2 = second scene etc.
    '''
    
    # Sort input scenes
    scenes = sortScenes(scenes)
    
    # Create array to contain output classified cloud mask array
    scl_out = _createOutputArray(md_dest, dtype = np.uint8)
    
    # Create array to contain record of the number of source image
    image_n = _createOutputArray(md_dest, dtype = np.uint16) 
    
    for n, scene in enumerate(scenes):
        
        if verbose: print '    Getting pixels from %s'%scene.filename.split('/')[-1]
                
        # Write mask array to a gdal dataset
        ds_source = _createGdalDataset(scene.metadata, data_out = scene.getMask(correct = True), dtype = 3)
         
        # Create an empty gdal dataset for destination
        ds_dest = _createGdalDataset(md_dest, dtype = 1)
        
        # Reproject source to destination projection and extent
        scl_resampled = _reprojectImage(ds_source, ds_dest, scene.metadata, md_dest)
        
        # Add reprojected data to SCL output array
        scl_out, image_n = _updateMaskArrays(scl_out, scl_resampled, image_n, n + 1)
        
        # Tidy up
        ds_source = None
        ds_dest = None
        
    if verbose: print 'Outputting SCL mask'
    
    # Write output cloud mask to disk for each resolution
    ds_out = _createGdalDataset(md_dest, data_out = scl_out,
                               filename = '%s/%s_R%sm_SCL.tif'%(output_dir, output_name, str(scene.resolution)),
                               driver='GTiff', dtype = 1, options = ['COMPRESS=LZW'])
    
    ds_out = _createGdalDataset(md_dest, data_out = image_n,
                               filename = '%s/%s_R%sm_imageN.tif'%(output_dir, output_name, str(scene.resolution)),
                               driver='GTiff', dtype = 2, options = ['COMPRESS=LZW'])

    return scl_out, image_n


def generateBandArray(scenes, image_n, band, scl_out, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False):
    """generateBandArray(scenes, image_n, band, scl_out, md_dest, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False)
    
    Function which generates an output GeoTiff file from list of level 3B source files for a specified output band and extent.

    Args:
        scenes: A list of level 2A inputs (of class LoadScene).
        image_n: An array of integers from generateSCLArray(), which describes the scene that each pixel should come from. 0 = No data, 1 = first scene, 2 = second scene etc.
        band: String describing bad to process. e.g. B02, B03, B8A....
        scl_out: Numpy array with mask from generateSCLArray().
        md_dest: Dictionary from buildMetaDataDictionary() containing output projection details.
        output_dir: Optionally specify directory for output file. Defaults to current working directory.
        output_name: Optionally specify a string to prepend to output files. Defaults to 'L3B_output'.
        
    Returns:
        A numpy array containing mosaic data for the input band.
    """
    
    # Sort input scenes
    scenes = sortScenes(scenes)
    
    # Create array to contain output array for this band
    data_out = _createOutputArray(md_dest, dtype = np.uint16)
    
    # For each source file
    for n, scene in enumerate(scenes):
        
        # Skip image where no data is used from it
        if np.sum(image_n[image_n==n+1]) == 0:
            continue
        
        if verbose: print '    Getting pixels from %s'%scene.filename.split('/')[-1]
        
        # Write array to a gdal dataset
        ds_source = _createGdalDataset(scene.metadata, data_out = scene.getBand(band))                

        # Create an empty gdal dataset for destination
        ds_dest = _createGdalDataset(md_dest, dtype = 2)
                
        # Reproject source to destination projection and extent
        data_resampled = _reprojectImage(ds_source, ds_dest, scene.metadata, md_dest)
                
        # Add reprojected data to band output array at appropriate image_n
        data_out = _updateBandArray(data_out, data_resampled, image_n, n + 1, scl_out)
        
        # Tidy up
        ds_source = None
        ds_dest = None

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


    
        
def main(source_files, extent_dest, EPSG_dest, resolution = 0, output_dir = os.getcwd(), output_name = 'mosaic', verbose = False):
    """main(source_files, extent_dest, EPSG_dest, resolution = 0, output_dir = os.getcwd(), output_name = 'mosaic')
    
    Function to run through the entire chain for converting output of sen2Three into custom mosaics. This is the function that is initiated from the command line.
        
    Args:
        source_files: A list of level 3A input files.
        extent_dest: List desciribing corner coordinate points in destination CRS [xmin, ymin, xmax, ymax].
        EPSG_dest: EPSG code of destination coordinate reference system. Must be a UTM projection. See: https://www.epsg-registry.org/ for codes.
        resolution: Process 0, 20, or 60 m bands. Defaults to 0 and processes all three.
        output_dir: Optionally specify an output directory.
        output_name: Optionally specify a string to precede output file names. Defaults to 'mosaic'.
        verbose: Make script verbose (set True).
    """

    assert len(extent_dest) == 4, "Output extent must be specified in the format [xmin, ymin, xmax, ymax]"
    assert len(source_files) >= 1, "No source files in specified location."
    assert resolution in [0, 10, 20, 60], "Resolution must be 10, 20, or 60 m, or 0 to process all three."
    
    # Remove trailing / from output directory if present 
    output_dir = output_dir.rstrip('/')
    
    res_list, band_list = _getBands(resolution)
    
    # For each of the input resolutions
    for res in np.unique(res_list)[::-1]:
                
        # Load metadata for all Sentinel-2 datasets
        scenes = [utilties.LoadScene(source_file, resolution = res) for source_file in source_files]
                
        # Build metadata of output object
        md_dest = utilties.Metadata(extent_dest, res, EPSG_dest)
        
        # Reduce the pool of scenes to only those that overlap with output tile
        scenes_tile = getSourceFilesInTile(scenes, md_dest, verbose = verbose)       
                
        # It's only worth processing a tile if at least one input image is inside tile
        assert len(scenes_tile) >= 1, "No data inside specified tile. Not processing this tile."
                
        if verbose: print 'Doing SCL mask at %s m resolution'%str(res)
        
        # Generate a classified mask
        scl_out, image_n = generateSCLArray(scenes_tile, md_dest, output_dir = output_dir, output_name = output_name, verbose = verbose)

        # Process images for each band
        for band in band_list[res_list==res]:
            
            if verbose: print 'Doing band %s at %s m resolution'%(band, str(res))
            
            # Using image_n, combine pixels into outputs images for each band
            band_out = generateBandArray(scenes_tile, image_n, band, scl_out, md_dest, output_dir = output_dir, output_name = output_name, verbose = verbose)
    
        # Build VRT output files for straightforward visualisation
        if verbose: print 'Building .VRT images for visualisation'
        
        # Natural colour image (10 m)
        buildVRT('%s/%s_R%sm_B04.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B03.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_B02.tif'%(output_dir, output_name, str(res)), '%s/%s_R%sm_RGB.vrt'%(output_dir, output_name, str(res)))

        # Near infrared image (10 m )
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
    required.add_argument('infiles', metavar = 'L2A_FILES', type = str, nargs = '+', help = 'Sentinel-2 level 2A input files in .SAFE format. Specify a valid S2 input file or multiple files through wildcards (e.g. PATH/TO/*_MSIL2A_*.SAFE).')
    required.add_argument('-te', '--target_extent', nargs = 4, metavar = ('XMIN', 'YMIN', 'XMAX', 'YMAX'), type = float, help = "Extent of output image tile, in format <xmin, ymin, xmax, ymax>.")
    required.add_argument('-e', '--epsg', type=int, help="EPSG code for output image tile CRS. This must be UTM. Find the EPSG code of your output CRS as https://www.epsg-registry.org/.")
    
    # Optional arguments
    optional.add_argument('-r', '--resolution', metavar = 'N', type=int, default = 0, help="Specify a resolution to process (10, 20, 60, or 0 for all).")
    optional.add_argument('-o', '--output_dir', type=str, metavar = 'DIR', default = os.getcwd(), help="Optionally specify an output directory. If nothing specified, downloads will output to the present working directory, given a standard filename.")
    optional.add_argument('-n', '--output_name', type=str, metavar = 'NAME', default = 'mosaic', help="Optionally specify a string to precede output filename.")
    optional.add_argument('-v', '--verbose', action='store_true', default = False, help = "Make script verbose.")
    
    # Get arguments
    args = parser.parse_args()

    # Get absolute path of input .safe files.
    args.infiles = [os.path.abspath(i) for i in args.infiles]

    main(args.infiles, args.target_extent, args.epsg, resolution = args.resolution, output_dir = args.output_dir, output_name = args.output_name, verbose = args.verbose)
    
    
