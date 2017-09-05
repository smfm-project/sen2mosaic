#!/usr/bin/env python

import argparse
import glob
import glymur
import matplotlib.pyplot as plt
import numpy as np
import os
from osgeo import gdal
from osgeo import osr
from scipy import ndimage
import subprocess

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET



def getSourceMetadata(safe_file, res):
    '''
    This function extracts georefence info from level 3 Sentinel 2 data in .SAFE format
    The input is the MTD_TL.xml file
    Returns a dictionary
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
    extent_dest = a list desciribing corner coordinate points in destination CRS [xmin, ymin, xmax, ymax]
    res = pixel size
    EPSG = EPSG code of destination CRS. See: https://www.epsg-registry.org/
    '''
    
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


def testOutsideTile(md_source, md_dest):
    '''
    Uses metadata to test whether source data falls inside destination tile.
    Returns a boolean (True/False) value.
    '''
            
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


def createOutputArray(md, dtype = np.uint16):
    '''
    Create an output array from metadata dictionary
    '''
    
    output_array = np.zeros((md['nrows'], md['ncols']), dtype = dtype)
    
    return output_array


def sortSourceFiles(source_files):
    '''
    When building a large mosaic, it's necessary for input tiles to be in a consistent order to avoid strange overlap artefcacts.
    This function sorts a list of safe files in alphabetical order by their tile reference.
    '''
       
    source_files.sort(key = lambda x: x.split('/')[-1].split('_T')[1])
    
    return source_files


def loadSourceFile(L3A_file, res, band):
    '''
    Loads a Sentinel-2 level 3A .jp file for a given band and resolution.
    L3A_file = Path to a level 3A Sentinel-2 .SAFE file.
    res = Resolution, an integer of 10, 20, or 60 meters.
    band = A string indicating the image band name to load (e.g. 'B02', 'B04', 'SCL').
    Returns a numpy array.
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


def improveSCLMask(data, res):
    '''
    The median filter of sen2Three can mess up edges of image.
    This can be fixed by removing 60 m worth of pixels from the edge of the mask.
    data = Input SCL mask as a numpy array
    res = Resolution, an integer of 10, 20, or 60 meters
    Returns a numpy array with a slightly modified mask.    
    '''
    
    mask_dilate = ndimage.morphology.binary_dilation((data == 0).astype(np.int), iterations = 60 / res)
    data[mask_dilate] = 0
    
    return data


def createGdalDataset(md, data_out = None, filename = '', driver = 'MEM', dtype = gdal.GDT_Int16, options = []):
    '''
    Function to create an empty gdal dataset with georefence info from metadata dictionary.
    md = A metadata dictionary created by buildMetadataDictionary().
    data_out = An array of data to include in the gdal dataset.
    filename = An output filename, if image will be written to disk.
    driver = GDAL driver type (e.g. 'MEM', 'GTiff'). By default this function creates an array in memory, but set driver = 'GTiff' to make a GeoTiff.
    dtype = Output data type. Default data type is a 16-but unsigned integer, but this can be specified using GDAL standards.
    options = A list containing other GDAL options (e.g. for compression, use [compress'LZW'].
    Returns a GDAL dataset.
    '''
       
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


def reprojectImage(ds_source, ds_dest, md_source, md_dest):
    '''
    Reprojects a source image to match the coordinates of a destination GDAL dataset.
    ds_source = A gdal dataset from createGdalDataset() containing data to be repojected.
    ds_dest = A gdal dataset from createGdalDataset(), with destination coordinate reference system and extent.
    md_source = A metadata dictionary created by buildMetadataDictionary() representing the source image.
    md_dest = A metadata dictionary created by buildMetadataDictionary() representing the destination image.
    Returns a GDAL array with resampled data
    '''
    
    proj_source = md_source['proj'].ExportToWkt()
    proj_dest = md_dest['proj'].ExportToWkt()
    
    # Reproject source into dest project coordinates
    gdal.ReprojectImage(ds_source, ds_dest, proj_source, proj_dest, gdal.GRA_NearestNeighbour)
            
    ds_resampled = ds_dest.GetRasterBand(1).ReadAsArray()
    
    return ds_resampled


def updateMaskArrays(scl_out, scl_resampled, image_n, n):
    '''
    Updates contents of scl and image_n arrays
    '''
    
    # Select only places which have new data, and have not already had data allocated
    selection = np.logical_and(image_n == 0, scl_resampled != 0)
    
    # Update SCL code in each newly assigned pixel, and record the image that pixel has come from
    scl_out[selection] = scl_resampled[selection]
    image_n[selection] = n
    
    return scl_out, image_n


def updateBandArray(data_out, data_resampled, scl_resampled, image_n, n):
    '''
    Updates contents of output array based on image_n array
    '''
    
    # Find pixels that need replacing in this image
    selection = image_n == n
               
    # Add good data to data_out array
    data_out[selection] = data_resampled[selection]
               
    # Set bad values from scl mask to 0, to keep things tidy
    for i in [1, 2, 3, 8, 9, 10, 11, 12]:
        data_out[scl_resampled == i] = 0
    
    return data_out


def buildVRT(red_band, green_band, blue_band, output_path):
    '''
    Builds a three band RGB vrt for image visualisation.
    red_band = Filename to add to red band
    green_band = Filename to add to green band
    blue_band = Filename to add to blue band
    output_name = Path to output file
    '''
    
    # Ensure output name is a VRT
    if output_path[-4:] != '.vrt':
        output_path += '.vrt'
    
    subprocess.call('gdalbuildvrt -separate -overwrite %s.vrt %s %s %s'%(output_path,
                     red_band, green_band, blue_band))




def main(source_files, extent_dest, EPSG_dest,
    res_list = np.array([10, 10, 10, 10, 20, 20, 20, 20, 20, 20]),
    band_list = np.array(['B02', 'B03', 'B04', 'B08', 'B05', 'B06', 'B07', 'B8A', 'B11', 'B12']),
    output_dir = os.getcwd(), output_name = 'output'):
    '''
    Convert outputs of sen2Three to a customisable grid, based on specified UTM coordinate bounds.
    '''

    assert len(extent_dest) == 4, "Output extent must be specified in the format [xmin, ymin, xmax, ymax]"
    assert len(res_list) == len(band_list), "For each band to process you must specify a resolution"
      
    # Sort source files alphabetically by tile reference.    
    source_files = sortSourceFiles(source_files)

    
    # For each of the input resolutions
    for res in [10, 20]:
        
        # Define destination file metadata dictionary
        md_dest = buildMetadataDictionary(extent_dest, res, EPSG_dest)
                
        # Create array to contain output classified cloud mask array
        scl_out = createOutputArray(md_dest, dtype = np.uint8)
        
        # Create array to contain record of the number of source image
        image_n = createOutputArray(md_dest, dtype = np.uint8) 
        
        print 'Doing SCL mask at %s m resolution'%str(res)

        # First process classified images of residual cloud cover
        for n, safe_file in enumerate(source_files):
            
            print '    Processing %s'%safe_file.split('/')[-1]
                       
            # Get source file metadata
            extent_source, EPSG_source = getSourceMetadata(safe_file, res)
            
            # Define source file metadata dictionary
            md_source = buildMetadataDictionary(extent_source, res, EPSG_source)

            # Skip processing the file if image falls outside of tile area
            if testOutsideTile(md_source, md_dest):
                print '       Tile out of bounds, skipping...'
                continue
            
            print '        Getting pixels from tile...'
            
            # Load source data
            scl = loadSourceFile(safe_file, res, 'SCL')
            
            # Tweak output mask to fix anomalies introduced by sen2Three median filter
            scl = improveSCLMask(scl, res)
            
            # Write array to a gdal dataset
            ds_source = createGdalDataset(md_source, data_out = scl, dtype = gdal.GDT_Byte)
            
            # Create an empty gdal dataset for destination
            ds_dest = createGdalDataset(md_dest, dtype = gdal.GDT_Byte)
            
            # Reproject source to destination projection and extent
            scl_resampled = reprojectImage(ds_source, ds_dest, md_source, md_dest)

            # Add reprojected data to SCL output array
            scl_out, image_n = updateMaskArrays(scl_out, scl_resampled, image_n, n + 1)
            
            # Tidy up
            ds_source = None
            ds_dest = None
    
        print 'Outputting SCL mask'
    
        # Write output cloud mask to disk for each resolution
        ds_out = createGdalDataset(md_dest, data_out = scl_out,
                                   filename = '%s/%s_SCL_R%sm.tif'%(output_dir, output_name, str(res)),
                                   driver='GTiff', dtype = gdal.GDT_Byte, options = ['COMPRESS=LZW'])

        # Write image number record to disk for each resolution
        ds_out = createGdalDataset(md_dest, data_out = image_n,
                                   filename = '%s/%s_IMG_R%sm.tif'%(output_dir, output_name, str(res)),
                                   driver='GTiff', dtype = gdal.GDT_Byte, options = ['COMPRESS=LZW'])
        
        # Process images for each band
        for band in band_list[res_list==res]:
            
            # Create array to contain output array for this band
            data_out = createOutputArray(md_dest, dtype = np.uint16)
            
            print 'Doing band %s at %s m resolution'%(band, str(res))

            for n, safe_file in enumerate(source_files):
                
                print '    Processing %s'%safe_file.split('/')[-1]
                
                # Skip processing the file if image not part of final output tile
                if np.sum(image_n == n + 1) == 0:
                    print '        Tile out of bounds, skipping...'
                    continue
                
                print '        Getting pixels from tile...'
                
                # Get source file metadata
                extent_source, EPSG_source = getSourceMetadata(safe_file, res)
            
                # Define source file metadata dictionary
                md_source = buildMetadataDictionary(extent_source, res, EPSG_source)
    
                # Load source data for the band
                data = loadSourceFile(safe_file, res, band)
                
                # Write array to a gdal dataset
                ds_source = createGdalDataset(md_source, data_out = data)                

                # Create an empty gdal dataset for destination
                ds_dest = createGdalDataset(md_dest, dtype = gdal.GDT_Byte)
                
                # Reproject source to destination projection and extent
                data_resampled = reprojectImage(ds_source, ds_dest, md_source, md_dest)
                
                # Add reprojected data to band output array
                data_out = updateBandArray(data_out, data_resampled, scl_resampled, image_n, n + 1)
                
                # Tidy up
                ds_source = None
                ds_dest = None

            print 'Outputting band %s'%band

            # Write output for this band to disk
            ds_out = createGdalDataset(md_dest, data_out = data_out,
                                   filename = '%s/%s_%s_R%sm.tif'%(output_dir, output_name, band, str(res)),
                                   driver='GTiff', dtype = gdal.GDT_Byte, options = ['COMPRESS=LZW'])

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
    parser = argparse.ArgumentParser(description = "Process Sentinel-2 level 3A data to unofficial 'level 3B'. This mosaics L3A to a customisable grid, based on specified UTM coordinate bounds. Files are output as GeoTiffs, which are easier to work with than JPEG2000 files.")

    # Required arguments
    parser.add_argument('infiles', metavar = 'N', type = str, nargs = '+', help = 'Sentinel 2 input files (L3A, .SAFE format). Specify a valid S2 input file or multiple files through wildcards.')
    parser.add_argument('-te', '--target_extent', nargs = 4, type = float, help = "Extent of output image tile, in format <xmin, ymin, xmax, ymax>")
    parser.add_argument('-e', '--epsg', type=int, help="EPSG code for output image tile.")

    # Optional arguments
    parser.add_argument('-o', '--output_dir', type=str, default = os.getcwd(), help="Optionally specify an output directory. If nothing specified, downloads will output to the present working directory, given a standard filename.")
    parser.add_argument('-n', '--output_name', type=str, default = 'output', help="Optionally specify a string to precede output filename.")

    # Get arguments
    args = parser.parse_args()

    # Get absolute path of input .safe files.
    args.infiles = [os.path.abspath(i) for i in args.infiles]
    
    # and sort them alphabetically by granule name to ensure that images are always layered in the same order.
    # This assumes that files have not been renamed since being run through sen2three
    args.infiles.sort(key = lambda x: x.split('/')[-1].split('_T')[1])

    main(args.infiles, args.target_extent, args.epsg, output_dir = args.output_dir, output_name = args.output_name)
    
    
