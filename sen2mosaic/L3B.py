#!/usr/bin/env python

import argparse
import glob
import glymur
import numpy as np
import os
from scipy import ndimage
import subprocess

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
    
    output_array = np.zeros((md['nrows'], md['ncols']), dtype = dtype)
    
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


def _loadSourceFile(L3A_file, res, band):
    '''
    Loads a Sentinel-2 level 3A .jp file for a given band and resolution into a numpy array.
    
    Args:
        L3A_file: /path/to/a/ level 3A Sentinel-2 .SAFE file.
        res: Resolution, an integer of 10, 20, or 60 meters.
        band: A string indicating the image band name to load (e.g. 'B02', 'B04', 'SCL').
    
    Returns:
        A numpy array.
    '''
    
    # Remove trailing slash from input filename, if it exists
    L3A_file = L3A_file.rstrip('/')
    
    # Identify source file following the standardised file pattern
    image_path = glob.glob(L3A_file + '/GRANULE/*/IMG_DATA/R%sm/L03*_%s_%sm.jp2'%(str(res), band, str(res)))[0]
       
    # Load the image (.jp2 format)
    jp2 = glymur.Jp2k(image_path)
    
    # Extract array data from .jp2 file
    data = jp2[:]

    return data


def _improveSCLMask(data, res):
    '''
    The median filter of sen2Three can mess up edges of image. This can be fixed by removing 60 m worth of pixels from the edge of the mask with this function.
    
    Args:
        data: Input SCL mask as a numpy array.
        res: Resolution of mask, an integer of 10, 20, or 60 meters.
    
    Returns:
        A numpy array with a slightly modified mask.    
    '''
    
    mask_dilate = ndimage.morphology.binary_dilation((data == 0).astype(np.int), iterations = 120 / res)
    data[mask_dilate] = 0
    
    return data


def _createGdalDataset(md, data_out = None, filename = '', driver = 'MEM', dtype = 3, options = []):
    '''
    Function to create an empty gdal dataset with georefence info from metadata dictionary.

    Args:
        md: A metadata dictionary created by buildMetadataDictionary().
        data_out: Optionally specify an array of data to include in the gdal dataset.
        filename: Optionally specify an output filename, if image will be written to disk.
        driver: GDAL driver type (e.g. 'MEM', 'GTiff'). By default this function creates an array in memory, but set driver = 'GTiff' to make a GeoTiff. If writing a file to disk, the argument filename must be specified.
        dtype: Output data type. Default data type is a 16-bit unsigned integer (gdal.GDT_Int16, 3), but this can be specified using GDAL standards.
        options: A list containing other GDAL options (e.g. for compression, use [compress'LZW'].

    Returns:
        A GDAL dataset.
    '''
    from osgeo import gdal
    
    gdal_driver = gdal.GetDriverByName(driver)
    ds = gdal_driver.Create(filename, md['ncols'], md['nrows'], 1, gdal.GDT_Int16, options = options)
    ds.SetGeoTransform(md['geo_t'])
    ds.SetProjection(md['proj'].ExportToWkt())
    
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
    
    proj_source = md_source['proj'].ExportToWkt()
    proj_dest = md_dest['proj'].ExportToWkt()
    
    # Reproject source into dest project coordinates
    gdal.reprojectImage(ds_source, ds_dest, proj_source, proj_dest, gdal.GRA_NearestNeighbour)
            
    ds_resampled = ds_dest.GetRasterBand(1).ReadAsArray()
    
    return ds_resampled


def _testOutsideTile(md_source, md_dest):
    '''
    Function that uses metadata dictionaries from buildMetadatadisctionary() metadata to test whether any part of a source data falls inside destination tile.
    
    Args:
        md_source: A metadata dictionary created by buildMetadataDictionary() representing the source image.
        md_dest: A metadata dictionary created by buildMetadataDictionary() representing the destination image.
        
    Returns:
        A boolean (True/False) value.
    '''
    
    import osr
            
    # Set up function to translate coordinates from source to destination
    tx = osr.CoordinateTransformation(md_source['proj'], md_dest['proj'])
         
    # And translate the source coordinates
    md_source['ulx'], md_source['uly'], z = tx.TransformPoint(md_source['ulx'], md_source['uly'])
    md_source['lrx'], md_source['lry'], z = tx.TransformPoint(md_source['lrx'], md_source['lry'])   
    
    out_of_tile =  md_source['ulx'] >= md_dest['lrx'] or \
                   md_source['lrx'] <= md_dest['ulx'] or \
                   md_source['uly'] <= md_dest['lry'] or \
                   md_source['lry'] >= md_dest['uly']
    
    return out_of_tile


def _updateMaskArrays(scl_out, scl_resampled, image_n, n):
    '''
    Function to update contents of scl and image_n arrays.
    
    Args:
        scl_out: A numpy array representing the mask to be output.
        scl_resampled: A numpy array containing resampled data to be added to the scl_out.
        image_n: A numpy array to record the image number for each pixel.
        n: An integer describing the image number (first image = 1, second image = 2 etc.)
    
    Returns:
        The scl_out array with pixels from scl_resampled added.
        The image_n array describing which image each pixel is sources from.
    '''
    
    # Select only places which have new data, and have not already had data allocated
    selection = np.logical_and(image_n == 0, scl_resampled != 0)
    
    # Update SCL code in each newly assigned pixel, and record the image that pixel has come from
    scl_out[selection] = scl_resampled[selection]
    image_n[selection] = n
    
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
    for i in [1, 2, 3, 8, 9, 10, 11, 12]:
        data_out[selection][scl_out[selection] == i] = 0

    return data_out


def getSourceMetadata(safe_file, res):
    '''
    Function to extract georefence info from level 3 Sentinel 2 data in .SAFE format.
    
    Args:
        safe_file: String with /path/to/the/MTD_TL.xml file bundled with a .SAFE file.
        res: Integer describing pixel size in m (10, 20, or 60).

    Returns:
        A list describing the extent of the .SAFE file, in the format [xmin, ymin, xmax, ymax].
        EPSG code of the coordinate reference system of the .SAFE file.
    '''
    
    assert safe_file[-5:] == '.SAFE', "The input to getSourceMetadata() must be a .safe file"
    
    # Remove trailing / from safe files if present 
    safe_file = safe_file.rstrip('/')
    
    # Find the xml file that contains file metadata
    xml_file = glob.glob(safe_file + '/GRANULE/*/MTD_TL.xml')[0]
        
    # Define xml namespace (specific to level 3 Sentinel 2 .SAFE files)
    ns = {'n1':'https://psd-12.sentinel2.eo.esa.int/PSD/S2_PDI_Level-3_Tile_Metadata.xsd'}
    
    # Parse xml file
    tree = ET.ElementTree(file = xml_file)
    root = tree.getroot()
    
    # Get array size
    size = root.find("n1:Geometric_Info/Tile_Geocoding/Size[@resolution='%s']"%str(res),ns)
    nrows = int(size.find('NROWS').text)
    ncols = int(size.find('NCOLS').text)
    
    # Get extent data
    geopos = root.find("n1:Geometric_Info/Tile_Geocoding/Geoposition[@resolution='%s']"%str(res),ns)
    ulx = float(geopos.find('ULX').text)
    uly = float(geopos.find('ULY').text)
    xres = float(geopos.find('XDIM').text)
    yres = float(geopos.find('YDIM').text)
    lrx = ulx + (xres * ncols)
    lry = uly + (yres * nrows)
    
    extent = [ulx, lry, lrx, uly]
    
    # Find EPSG code to define projection
    EPSG = root.find('n1:Geometric_Info/Tile_Geocoding/HORIZONTAL_CS_CODE',ns).text
    EPSG = int(EPSG.split(':')[1])
    
    return extent, EPSG


def buildMetadataDictionary(extent_dest, res, EPSG):
    '''
    Build a metadata dictionary to describe the destination georeference info
    
    Args:
        extent_dest: List desciribing corner coordinate points in destination CRS [xmin, ymin, xmax, ymax]
        res: Integer describing pixel size in m (10, 20, or 60)
        EPSG: EPSG code of destination coordinate reference system. Must be a UTM projection. See: https://www.epsg-registry.org/ for codes.
    
    Returns:
        A dictionary containg projection info.
    '''
    
    from osgeo import osr
    
    # Set up an empty dictionary
    md = {}
    
    # Define projection from EPSG code
    md['EPSG_code'] = EPSG

    # Get GDAL projection string
    proj = osr.SpatialReference()
    proj.ImportFromEPSG(EPSG)
    md['proj'] = proj
    
    # Get image extent data
    md['ulx'] = float(extent_dest[0])
    md['lry'] = float(extent_dest[1])
    md['lrx'] = float(extent_dest[2])
    md['uly'] = float(extent_dest[3])
    md['xres'] = float(res)
    md['yres'] = float(-res)
    
    # Calculate array size
    md['nrows'] = int((md['lry'] - md['uly']) / md['yres'])
    md['ncols'] = int((md['lrx'] - md['ulx']) / md['xres'])
    
    # Define gdal geotransform (Affine)
    md['geo_t'] = (md['ulx'], md['xres'], 0, md['uly'], 0, md['yres'])
    
    return md


def getSafeFilesInTile(source_files, md_dest, res):
    '''
    Takes a list of source files as input, and determines where each falls within extent of output tile.
    
    Args:
        source_files: A list of level 3A input files.
        md_dest: Dictionary from buildMetaDataDictionary() containing output projection details.
        res: Resolution, an integer of 10, 20, or 60 meters.

    Returns:
        A reduced list of source_files containing only files that will contribute to each tile.
    '''
    
    # Sort source files alphabetically by tile reference.    
    source_files = _sortSourceFiles(source_files)
                
    # Determine which L3A images are within specified tile bounds
    print 'Searching for source files within specified tile...'
    
    do_tile = []
    
    for safe_file in source_files:
                                           
        # Get source file metadata
        extent_source, EPSG_source = getSourceMetadata(safe_file, res)
        
        # Define source file metadata dictionary
        md_source = buildMetadataDictionary(extent_source, res, EPSG_source)

        # Skip processing the file if image falls outside of tile area
        if _testOutsideTile(md_source, md_dest):
            do_tile.append(False)
            continue
        
        print '    Found one: %s'%safe_file
        do_tile.append(True)
    
    # Get subset of source_files in specified tile
    source_files_tile = list(np.array(source_files)[np.array(do_tile)])
    
    return source_files_tile


def generateSCLArray(source_files, md_dest, res, output_dir = os.getcwd(), output_name = 'L3B_output'):
    '''generateSCLArray(source_files, md_dest, output_dir = os.getcwd(), output_name = 'L3B_output')
    
    Function which generates an mask GeoTiff file from list of level 3B source files for a specified output band and extent, and an array desciribing which source_image each pixel comes from

    Args:
        source_files: A list of level 3A input files.
        md_dest: Dictionary from buildMetaDataDictionary() containing output projection details.
        res: Resolution, an integer of 10, 20, or 60 meters.
        output_dir: Optionally specify directory for output file. Defaults to current working directory.
        output_name: Optionally specify a string to prepend to output files. Defaults to 'L3B_output'.
        
    Returns:
        A numpy array containing mosaic data for the input band.
        A numpy array describing the image number each pixel is sourced from. 0 = No data, 1 = first source_file, 2 = second source_file etc.
    '''
    
    # Create array to contain output classified cloud mask array
    scl_out = _createOutputArray(md_dest, dtype = np.uint8)
    
    # Create array to contain record of the number of source image
    image_n = _createOutputArray(md_dest, dtype = np.uint8) 

    for n, safe_file in enumerate(source_files):
        
        print '    Getting pixels from %s'%safe_file.split('/')[-1]

        # Get source file metadata
        extent_source, EPSG_source = getSourceMetadata(safe_file, res)
        
        # Define source file metadata dictionary
        md_source = buildMetadataDictionary(extent_source, res, EPSG_source)
        
        # Load source data
        scl = _loadSourceFile(safe_file, res, 'SCL')
        
        # Tweak output mask to fix anomalies introduced by sen2Three median filter
        scl = _improveSCLMask(scl, res)
        
        # Write array to a gdal dataset
        ds_source = _createGdalDataset(md_source, data_out = scl, dtype = 3)
         
        # Create an empty gdal dataset for destination
        ds_dest = _createGdalDataset(md_dest, dtype = 1)
        
        # Reproject source to destination projection and extent
        scl_resampled = _reprojectImage(ds_source, ds_dest, md_source, md_dest)

        # Add reprojected data to SCL output array
        scl_out, image_n = _updateMaskArrays(scl_out, scl_resampled, image_n, n + 1)
        
        # Tidy up
        ds_source = None
        ds_dest = None
    
    
    print 'Outputting SCL mask'
    
    # Write output cloud mask to disk for each resolution
    ds_out = _createGdalDataset(md_dest, data_out = scl_out,
                               filename = '%s/%s_SCL_R%sm.tif'%(output_dir, output_name, str(res)),
                               driver='GTiff', dtype = 1, options = ['COMPRESS=LZW'])
    
    return scl_out, image_n


def generateBandArray(source_files, image_n, band, scl_out, md_dest, res, output_dir = os.getcwd(), output_name = 'L3B_output'):
    """generateBandArray(source_files, image_n, band, scl_out, md_dest, output_dir=os.getcwd(), output_name='L3B_output')
    
    Function which generates an output GeoTiff file from list of level 3B source files for a specified output band and extent.

    Args:
        source_files: A list of level 3A input files.
        image_n: An array of integers from generateSCLArray(), which describes the source_file that each pixel should come from. 0 = No data, 1 = first source_file, 2 = second source_file etc.
        band: String describing bad to process. e.g. B02, B03, B8A....
        scl_out: Numpy array with mask from generateSCLArray().
        md_dest: Dictionary from buildMetaDataDictionary() containing output projection details.
        res: Resolution, an integer of 10, 20, or 60 meters.
        output_dir: Optionally specify directory for output file. Defaults to current working directory.
        output_name: Optionally specify a string to prepend to output files. Defaults to 'L3B_output'.
        
    Returns:
        A numpy array containing mosaic data for the input band.
    """
    
    # Create array to contain output array for this band
    data_out = _createOutputArray(md_dest, dtype = np.uint16)
    
    # For each source file
    for n, safe_file in enumerate(source_files):
        
        print '    Getting pixels from %s'%safe_file.split('/')[-1]
        
        # Get source file metadata
        extent_source, EPSG_source = getSourceMetadata(safe_file, res)
     
        # Define source file metadata dictionary
        md_source = buildMetadataDictionary(extent_source, res, EPSG_source)

        # Load source data for the band
        data = _loadSourceFile(safe_file, res, band)
        
        # Write array to a gdal dataset
        ds_source = _createGdalDataset(md_source, data_out = data)                

        # Create an empty gdal dataset for destination
        ds_dest = _createGdalDataset(md_dest, dtype = 1)
                
        # Reproject source to destination projection and extent
        data_resampled = _reprojectImage(ds_source, ds_dest, md_source, md_dest)
                
        # Add reprojected data to band output array at appropriate image_n
        data_out = _updateBandArray(data_out, data_resampled, image_n, n + 1, scl_out)
                
        # Tidy up
        ds_source = None
        ds_dest = None

    print 'Outputting band %s'%band

    # Write output for this band to disk
    ds_out = _createGdalDataset(md_dest, data_out = data_out,
                               filename = '%s/%s_%s_R%sm.tif'%(output_dir, output_name, band, str(res)),
                               driver='GTiff', dtype = 1, options = ['COMPRESS=LZW'])

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


    

def main(source_files, extent_dest, EPSG_dest,
    res_list = [10, 10, 10, 10, 20, 20, 20, 20, 20, 20],
    band_list = ['B02', 'B03', 'B04', 'B08', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12'],
    output_dir = os.getcwd(), output_name = 'L3B_output'):
    """main(source_files, extent_dest, EPSG_dest, res_list = [10, 10, 10, 10, 20, 20, 20, 20, 20, 20], band_list = ['B02','B03','B04','B08','B05','B06','B07','B8A','B11','B12'], output_dir = os.getcwd(), output_name = 'L3B_output')
    
    Function to run through the entire chain for converting output of sen2Three into custom mosaics. This is the function that is initiated from the command line.
    
    Args:
        source_files: A list of level 3A input files.
        extent_dest: List desciribing corner coordinate points in destination CRS [xmin, ymin, xmax, ymax].
        EPSG_dest: EPSG code of destination coordinate reference system. Must be a UTM projection. See: https://www.epsg-registry.org/ for codes.
        res_list: Optionally specify a list of integers describing pixel size in m (10, 20, or 60). Must be accompanied by a band_list of the same size. Defaults to native resolution of each band.
        band_list: Optionally specify a list of output band names. Must be accompanied by a res_list of the same size. Defaults to processing all 10 and 20 m bands.
        output_dir: Optionally specify an output directory.
        output_name: Optionally specify a string to precede output file names.
    """

    assert len(extent_dest) == 4, "Output extent must be specified in the format [xmin, ymin, xmax, ymax]"
    assert len(res_list) == len(band_list), "For each band to process you must specify a resolution"
    assert len(source_files) > 1, "No source files in specified location."
    
    # Convert band and res list to numpy arrays for indexing
    res_lis = np.array(res_list)
    band_list = np.array(band_list)
    
    
    # Remove trailing / from output directory if present 
    output_dir = output_dir.rstrip('/')
       
    # For each of the input resolutions
    for res in sorted(list(set(res_list))):
        
        # Build a dictionary with output projection metadata
        md_dest = buildMetadataDictionary(extent_dest, res, EPSG_dest)    
        
        # Reduce the pool of source_files to only those that overlap with output tile
        source_files_tile = getSafeFilesInTile(source_files, md_dest, res)
        
        # It's only worth processing a tile if at least one input image is inside tile
        assert len(source_files_tile) > 1, "No data inside specified tile. Not processing this tile."
        
        print 'Doing SCL mask at %s m resolution'%str(res)
       
        # Generate a classified mask
        scl_out, image_n = generateSCLArray(source_files_tile, md_dest, res, output_dir = output_dir, output_name = output_name)
               
        # Process images for each band
        for band in band_list[res_list==res]:
            
            print 'Doing band %s at %s m resolution'%(band, str(res))
            
            # Using image_n, combine pixels into outputs images for each band
            band_out = generateBandArray(source_files_tile, image_n, band, scl_out, md_dest, res, output_dir = output_dir, output_name = output_name)
    
    # Build VRT output files for straightforward visualisation
    print 'Building .VRT images for visualisation'

    # Natural colour image (10 m)
    buildVRT('%s/%s_B04_R10m.tif'%(output_dir, output_name), '%s/%s_B03_R10m.tif'%(output_dir, output_name),
              '%s/%s_B02_R10m.tif'%(output_dir, output_name), '%s/%s_RGB.vrt'%(output_dir, output_name))

    # Near infrared image (10 m )
    buildVRT('%s/%s_B08_R10m.tif'%(output_dir, output_name), '%s/%s_B04_R10m.tif'%(output_dir, output_name),
              '%s/%s_B03_R10m.tif'%(output_dir, output_name), '%s/%s_NIR.vrt'%(output_dir, output_name))    
  
    print 'Processing complete!'



if __name__ == "__main__":
    
    # Set up command line parser
    parser = argparse.ArgumentParser(description = "Process Sentinel-2 level 3A data to unofficial 'level 3B'. This script mosaics L3A into a customisable grid square, based on specified UTM coordinate bounds. Files are output as GeoTiffs, which are easier to work with than JPEG2000 files.")

    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')

    # Required arguments
    required.add_argument('infiles', metavar = 'L3A_FILES', type = str, nargs = '+', help = 'Sentinel-2 level 3A input files in .SAFE format. Specify a valid S2 input file or multiple files through wildcards (e.g. PATH/TO/*_MSIL3A_*.SAFE).')
    required.add_argument('-te', '--target_extent', nargs = 4, metavar = ('XMIN', 'YMIN', 'XMAX', 'YMAX'), type = float, help = "Extent of output image tile, in format <xmin, ymin, xmax, ymax>.")
    required.add_argument('-e', '--epsg', type=int, help="EPSG code for output image tile CRS. This must be UTM. Find the EPSG code of your output CRS as https://www.epsg-registry.org/.")

    # Optional arguments
    optional.add_argument('-o', '--output_dir', type=str, metavar = 'DIR', default = os.getcwd(), help="Optionally specify an output directory. If nothing specified, downloads will output to the present working directory, given a standard filename.")
    optional.add_argument('-n', '--output_name', type=str, metavar = 'NAME', default = 'L3B_output', help="Optionally specify a string to precede output filename.")

    # Get arguments
    args = parser.parse_args()

    # Get absolute path of input .safe files.
    args.infiles = [os.path.abspath(i) for i in args.infiles]

    main(args.infiles, args.target_extent, args.epsg, output_dir = args.output_dir, output_name = args.output_name)
    
    
