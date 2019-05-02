

import datetime
import glob
import numpy as np
import os
from osgeo import gdal, osr
import re
import xml.etree.ElementTree as ET


### Functions for data input and output, and image reprojection


#########################################
### Geospatial manipulation functions ###
#########################################

def _reprojectImage(ds_source, ds_dest, md_source, md_dest, resampling = 0):
    '''
    Reprojects a source image to match the coordinates of a destination GDAL dataset.
    
    Args:
        ds_source: A gdal dataset from utilities.createGdalDataset() containing data to be repojected.
        ds_dest: A gdal dataset from utilities.createGdalDataset(), with destination coordinate reference system and extent.
        md_source: Metadata class from utilities.Metadata() representing the source image.
        md_dest: Metadata class from utilities.Metadata() representing the destination image.
    
    Returns:
        A GDAL array with resampled data
    '''
    
    from osgeo import gdal
    
    def _copyds(ds):
        '''
        Build a copy of an input ds, where performing fix on nodata values
        '''
        
        proj = osr.SpatialReference(wkt=ds.GetProjection())
        proj.AutoIdentifyEPSG()
        epsg = int(proj.GetAttrValue('AUTHORITY',1))
                
        geo_t = ds.GetGeoTransform()
        ulx = geo_t[0]
        lrx = geo_t[0] + (geo_t[1] * ds.RasterXSize)
        lry = geo_t[3] + (geo_t[5] * ds.RasterYSize)
        uly = geo_t[3]
        
        extent = [ulx, lry, lrx, uly]
                
        md = Metadata(extent, ds.GetGeoTransform()[1], epsg)
        return createGdalDataset(md, dtype = 1)
    
    proj_source = md_source.proj.ExportToWkt()
    proj_dest = md_dest.proj.ExportToWkt()
    
    # Reproject source into dest project coordinates
    gdal.ReprojectImage(ds_source, ds_dest, proj_source, proj_dest, resampling)
            
    ds_resampled = ds_dest.GetRasterBand(1).ReadAsArray()
    
    # As GDAL fills in all nodata pixels as zero, re-do transfromation with array of ones and re-allocate zeros to nodata. Only run where a nodata value has been assigned to ds_source.
    if ds_source.GetRasterBand(1).GetNoDataValue() is not None:
        
        ds_source_mask = _copyds(ds_source)
        ds_dest_mask = _copyds(ds_dest)
        ds_source_mask.GetRasterBand(1).WriteArray(np.ones_like(ds_source.GetRasterBand(1).ReadAsArray()))
        gdal.ReprojectImage(ds_source_mask, ds_dest_mask, proj_source, proj_dest, gdal.GRA_NearestNeighbour)
        ds_resampled[ds_dest_mask.GetRasterBand(1).ReadAsArray() == 0] = ds_source.GetRasterBand(1).GetNoDataValue()
    
    return ds_resampled



def createGdalDataset(md, data_out = None, filename = '', driver = 'MEM', dtype = 3, RasterCount = 1, nodata = None, options = []):
    '''
    Function to create an empty gdal dataset with georefence info from metadata dictionary.

    Args:
        md: Object from Metadata() class.
        data_out: Optionally specify an array of data to include in the gdal dataset.
        filename: Optionally specify an output filename, if image will be written to disk.
        driver: GDAL driver type (e.g. 'MEM', 'GTiff'). By default this function creates an array in memory, but set driver = 'GTiff' to make a GeoTiff. If writing a file to disk, the argument filename must be specified.
        dtype: Output data type. Default data type is a 16-bit unsigned integer (gdal.GDT_Int16, 3), but this can be specified using GDAL standards.
        options: A list containing other GDAL options (e.g. for compression, use [compress='LZW'].

    Returns:
        A GDAL dataset.
    '''
    from osgeo import gdal, osr
        
    gdal_driver = gdal.GetDriverByName(driver)
    ds = gdal_driver.Create(filename, md.ncols, md.nrows, RasterCount, dtype, options = options)
    
    ds.SetGeoTransform(md.geo_t)
    
    proj = osr.SpatialReference()
    proj.ImportFromEPSG(md.EPSG_code)
    ds.SetProjection(proj.ExportToWkt())
    
    # If a data array specified, add data to the gdal dataset
    if type(data_out).__module__ == np.__name__:
        
        if len(data_out.shape) == 2:
            data_out = np.ma.expand_dims(data_out,2)
        
        for feature in range(RasterCount):
            ds.GetRasterBand(feature + 1).WriteArray(data_out[:,:,feature])
            
            if nodata != None:
                ds.GetRasterBand(feature + 1).SetNoDataValue(nodata)
    
    # If a filename is specified, write the array to disk.
    if filename != '':
        ds = None
    
    return ds



def reprojectBand(scene, data, md_dest, dtype = 2, resampling = 0):
    """
    Funciton to load, correct and reproject a Sentinel-2 array
    
    Args:
        scene: A level-2A scene of class utilities.LoadScene().
        data: The array to reproject
        md_dest: An object of class utilities.Metadata() to reproject image to.
    
    Returns:
        A numpy array of resampled mask data
    """
    
    # Write mask array to a gdal dataset
    ds_source = createGdalDataset(scene.metadata, data_out = data, dtype = dtype)
        
    # Create an empty gdal dataset for destination
    ds_dest = createGdalDataset(md_dest, dtype = dtype)
    
    # Reproject source to destination projection and extent
    data_resampled = _reprojectImage(ds_source, ds_dest, scene.metadata, md_dest, resampling = resampling)
    
    return data_resampled



###########################
### Sentinel-2 metadata ###
###########################


def loadMetadata(granule_file, resolution = 20, level = '2A', tile = ''):
    '''
    Function to extract georefence info from level 1C/2A Sentinel 2 data in .SAFE format.
    
    Args:
        granule_file: String with /path/to/the/granule folder bundled in a .SAFE file.
        resolution: Integer describing pixel size in m (10, 20, or 60). Defaults to 20 m.

    Returns:
        A list describing the extent of the .SAFE file granule, in the format [xmin, ymin, xmax, ymax].
        EPSG code of the coordinate reference system of the granule
    '''
    
    assert resolution in [10, 20, 60], "Resolution must be 10, 20 or 60 m."
    assert level in ['1C', '2A'], "Product level must be either '1C' or '2A'."
    
    # Remove trailing / from granule directory if present 
    granule_file = granule_file.rstrip('/')
    
    assert len(glob.glob((granule_file + '/*MTD*.xml'))) > 0, "The location %s does not contain a metadata (*MTD*.xml) file."%granule_file
    
    # Find the xml file that contains file metadata
    xml_file = glob.glob(granule_file + '/*MTD*.xml')[0]
    
    # Parse xml file
    tree = ET.ElementTree(file = xml_file)
    root = tree.getroot()
            
    # Define xml namespace
    ns = {'n1':root.tag[1:].split('}')[0]}
    
    # Get array size
    size = root.find("n1:Geometric_Info/Tile_Geocoding[@metadataLevel='Brief']/Size[@resolution='%s']"%str(resolution),ns)
    nrows = int(size.find('NROWS').text)
    ncols = int(size.find('NCOLS').text)
    
    # Get extent data
    geopos = root.find("n1:Geometric_Info/Tile_Geocoding[@metadataLevel='Brief']/Geoposition[@resolution='%s']"%str(resolution),ns)
    ulx = float(geopos.find('ULX').text)
    uly = float(geopos.find('ULY').text)
    xres = float(geopos.find('XDIM').text)
    yres = float(geopos.find('YDIM').text)
    lrx = ulx + (xres * ncols)
    lry = uly + (yres * nrows)
    
    extent = [ulx, lry, lrx, uly]
    
    # Find EPSG code to define projection
    EPSG = root.find("n1:Geometric_Info/Tile_Geocoding[@metadataLevel='Brief']/HORIZONTAL_CS_CODE",ns).text
    EPSG = int(EPSG.split(':')[1])
    
    # Get datetime
    datestring = root.find("n1:General_Info/SENSING_TIME[@metadataLevel='Standard']",ns).text.split('.')[0]
    date = datetime.datetime.strptime(datestring,'%Y-%m-%dT%H:%M:%S')
    
    if level == '2A':
        try:
            # Get nodata percentage based on scene classification
            vegetated = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/L2A_Image_Content_QI/VEGETATION_PERCENTAGE",ns).text
            not_vegetated = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/L2A_Image_Content_QI/NOT_VEGETATED_PERCENTAGE",ns).text
            water = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/L2A_Image_Content_QI/WATER_PERCENTAGE",ns).text
        except:
            # In case of new sen2cor format
            vegetated = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/Image_Content_QI/VEGETATION_PERCENTAGE",ns).text
            not_vegetated = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/Image_Content_QI/NOT_VEGETATED_PERCENTAGE",ns).text
            water = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/Image_Content_QI/WATER_PERCENTAGE",ns).text
            
        nodata_percent = 100. - float(water) - float(vegetated) - float(not_vegetated)
    
    elif level == '1C':
        # Get nodata percentrage based on estimated cloud cover
        cloud_cover = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/Image_Content_QI/CLOUDY_PIXEL_PERCENTAGE", ns).text
        
        nodata_percent = 100. - float(cloud_cover)
    
    if tile == '':
        # Get tile from granule filename
        if granule_file.split('/')[-1].split('_')[1] == 'USER':
            
            # If old file format
            tile = granule_file.split('/')[-1].split('_')[-2]
            
        else:
            
            # If new file format
            tile = granule_file.split('/')[-1].split('_')[1]
    
    return extent, EPSG, date, tile, nodata_percent



##############################
### Sentinel-2 input files ###
##############################

def prepInfiles(infiles, level, tile = ''):
    """
    Function to select input granules from a directory, .SAFE file (with wildcards) or granule, based on processing level and a tile. Used by command line interface to identify input files.
    
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
