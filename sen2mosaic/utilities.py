#!/usr/bin/env python

import datetime
import glob
import numpy as np
import os
import re
import scipy.ndimage

import pdb

# This module contains functions to help in image mosaicking, masking, preparation and loading. It is used by sen2mosaic, and deforest tools.


class Metadata(object):
    '''
    This is a generic metadata class for Geospatial data
    '''
    
    def __init__(self, extent, res, EPSG):
        '''
        Args:
            extent: A list in the form [xmin. ymin, xmax, ymax]
            res: Pixel resolution
            EPSG: The EPSG code of the desired resolution
        '''
           
        
        # Define projection from EPSG code
        self.EPSG_code = EPSG
        
        # Define resolution
        self.res = res
        
        self.xres = float(res)
        self.yres = float(-res)
        
        # Define image extent data
        self.extent = extent
        
        self.ulx = float(extent[0])
        self.lry = float(extent[1])
        self.lrx = float(extent[2])
        self.uly = float(extent[3])
        
        # Get projection
        self.proj = self.__getProjection()
                
        # Calculate array size
        self.nrows = self.__getNRows()
        self.ncols = self.__getNCols()
        
        # Define gdal geotransform (Affine)
        self.geo_t = self.__getGeoT()
        
        
    def __getProjection(self):
        '''
        '''
        
        from osgeo import osr
        
        # Get GDAL projection string
        proj = osr.SpatialReference()
        proj.ImportFromEPSG(self.EPSG_code)
        
        return proj
    
    def __getNRows(self):
        '''
        '''
        
        return int(round((self.lry - self.uly) / self.yres))
    
    def __getNCols(self):
        '''
        '''
        
        return int(round((self.lrx - self.ulx) / self.xres))
    
    def __getGeoT(self):
        '''
        '''
        
        geo_t = (self.ulx, self.xres, 0, self.uly, 0, self.yres)
        
        return geo_t
    
    def createBlankArray(self, dtype = np.uint16):
        '''
        Create a blank array with the extent of the Metadata class.
            
        Args:
            dtype: Data type from numpy, defaults to np.uint16.
            
        Returns:
            A numpy array sized to match the specification of the utilities.Metadata() class.
        '''
        
        return np.zeros((self.nrows, self.ncols), dtype = dtype)
        
        
class LoadScene(object):
    '''
    Load a Sentinel-2, L1C or L2A scene
    '''
        
    def __init__(self, filename, resolution = 20):
        '''
        Args:
            filename: The path to a Sentinel-2 granule file
            resolution: The resolution to be loaded (10, 20, or 60 metres).
        '''
                
        # Format filename, and check that it exists
        self.filename = self.__checkFilename(filename)
                
        # Get file format
        self.file_format = self.__getFormat()
        
        # Save satellite name
        self.satellite = 'S2'
        
        # Save image type (S1_single, S1_dual, S2)
        self.image_type = 'S2'

        self.level = self.__getLevel()
                
        self.resolution = self.__checkResolution(resolution)
           
        self.__getMetadata()
        
        # Define source metadata
        self.metadata = Metadata(self.extent, self.resolution, self.EPSG)
        
        
    def __checkFilename(self, filename):
        '''
        Test that the granule exists
        '''
        
        # Get rid of trailing '/' if present
        filename = filename.rstrip()
        
        # Test that file exists
        assert os.path.exists(filename),"Cannot find file %s "%filename
        
        return filename
    
    def __getFormat(self):
        '''
        Test that the file of of an appropriate format
        '''
        
        if self.filename.split('/')[-3].split('.')[-1] == 'SAFE':
            return 'SAFE'

        else:
            raise IOError('File %s does not match any expected file pattern'%self.filename)
        
    def __getLevel(self):
        '''
        Determines the level of Sentinel-2 image.
        
        Returns:
            An integer
        '''
        
        if self.filename.split('/')[-1][:3] == 'L2A':    
            level = '2A'
        elif self.filename.split('/')[-1][:3] == 'L1C':    
            level = '1C'
        elif self.filename.split('/')[-1].split('_')[3] == 'L2A':
            level = '2A'
        elif self.filename.split('/')[-1].split('_')[3] == 'L1C':
            level = '1C'
        else:
            level = 'unknown'
                        
        return level
    
    def __checkResolution(self, resolution):
        '''
        Makes sure that the resolution matches a Sentinel-2 resolution
        '''
        
        assert resolution in [10, 20, 60], "Resolution must be 10, 20 or 60 m."
        
        return resolution
                
    def __getMetadata(self):
        '''
        Extract metadata from the Sentinel-2 file.
        '''
                
        self.extent, self.EPSG, self.datetime, self.tile, self.nodata_percent = getS2Metadata(self.filename, self.resolution)
    
    def __getImagePath(self, band, resolution = 20):
        '''
        Get the path to a mask or band (Jpeg2000 format).
        '''

        # Identify source file following the standardised file pattern
        
        if self.level == '2A':
            
            image_path = glob.glob(self.filename + '/IMG_DATA/R%sm/*%s*%sm.jp2'%(str(resolution), band, str(resolution)))
            
            # In old files the mask can be in the base folder
            if len(image_path) == 0 and band == 'SCL':
                image_path = glob.glob(self.filename + '/IMG_DATA/*%s*%sm.jp2'%(band, str(resolution)))
        
        elif self.level == '1C':
            image_path = glob.glob(self.filename + '/IMG_DATA/T%s_%s.jp2'%(str(self.tile), band))        
        
        assert len(image_path) > 0, "No file found for band: %s, resolution: %s in file %s."%(band, str(resolution), self.filename)
        
        return image_path[0]

    
    def getMask(self, correct = False, md = None):
        '''
        Load the mask to a numpy array.
        
        Args:
            correct: Set to True to apply improvements to the Sentinel-2 mask (recommended)
        '''
        
        if self.level == '1C':
            print 'Level 1C Sentinel-2 data are not masked. Try loading a level 2A image.'
            return False
        
        import cv2
                
        # Load mask at appropriate resolution
        if self.metadata.res in [20, 60]:
            image_path = self.__getImagePath('SCL', resolution = self.resolution)
        else:
            # In case of 10 m image, use 20 m mask
            image_path = self.__getImagePath('SCL', resolution = 20)
        
        # Load the image (.jp2 format)
        mask = cv2.imread(image_path, cv2.IMREAD_ANYDEPTH)
        
        # Expand 20 m resolution mask to match 10 metre image resolution if required
        if self.metadata.res == 10:
            mask = scipy.ndimage.zoom(mask, 2, order = 0)
        
        # Apply corrections?
        if correct:
            mask = improveMask(mask, self.resolution)
        
        # Reproject?
        if md is not None:
            mask = reprojectBand(self, mask, md, dtype = 1)
        
        return mask
    
    
    def getBand(self, band, md = None):
        '''
        Load a Sentinel-2 band to a numpy array.
        '''
        
        import cv2
        
        image_path = self.__getImagePath(band, resolution = self.resolution)
        
        # Load image with cv2 (faster than glymur)
        data = cv2.imread(image_path, cv2.IMREAD_ANYDEPTH)
        
        # Reproject?
        if md is not None:
            data = reprojectBand(self, data, md, dtype = 2) 
            
        return data


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
    data_resampled = reprojectImage(ds_source, ds_dest, scene.metadata, md_dest, resampling = resampling)
    
    return data_resampled


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


def reprojectImage(ds_source, ds_dest, md_source, md_dest, resampling = 0):
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
    
    proj_source = md_source.proj.ExportToWkt()
    proj_dest = md_dest.proj.ExportToWkt()
    
    # Reproject source into dest project coordinates
    gdal.ReprojectImage(ds_source, ds_dest, proj_source, proj_dest, gdal.GRA_NearestNeighbour)
            
    ds_resampled = ds_dest.GetRasterBand(1).ReadAsArray()
    
    return ds_resampled


def validateTile(tile):
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
    assert validateTile(tile) or tile == '', "Tile format not recognised. It should take the format '##XXX' (e.g.' 36KWA')."

    # Make interable if only one item
    if not isinstance(infiles, list):
        infiles = [infiles]
    
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
    
    def testOutsideTile(md_source, md_dest):
        '''
        Function that uses metadata class to test whether any part of a source data falls inside destination tile.
        
        Args:
            md_source: Metadata class from utilities.Metadata() representing the source image.
            md_dest: Metadata class from utilities.Metadata() representing the destination image.
            
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
    
    def testOutsideDate(scene, start = '20150101', end = datetime.datetime.today().strftime('%Y%m%d')):
        '''
        Function that uses LoadScene class to test whether a tile falls within the specified time range.
        
        Args:
            scene: Object from utilities.LoadScene()
            start: Start date to process, in format 'YYYYMMDD' Defaults to start of Sentinel-2 era.
            end: End date to process, in format 'YYYYMMDD' Defaults to today's date.
            
        Returns:
            A boolean (True/False) value.
        '''
                
        start = datetime.datetime.strptime(start,'%Y%m%d')
        end = datetime.datetime.strptime(end,'%Y%m%d')
        
        if scene.datetime > end:
            return True
        if scene.datetime < start:
            return True
        
        return False
        
    # Determine which images are within specified tile bounds
    if verbose: print 'Searching for source files within specified tile...'
    
    do_tile = []

    for scene in scenes:
        
        # Skip processing the file if image falls outside of tile area
        if testOutsideTile(scene.metadata, md_dest):
            do_tile.append(False)
            continue
        
        if testOutsideDate(scene, start = start, end = end):
            do_tile.append(False)
            continue
        
        if verbose: print '    Found one: %s'%scene.filename
        do_tile.append(True)
    
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



def getS2Metadata(granule_file, resolution = 20, level = '2A', tile = ''):
    '''
    Function to extract georefence info from level 1C/2A Sentinel 2 data in .SAFE format.
    
    Args:
        granule_file: String with /path/to/the/granule folder bundled in a .SAFE file.
        resolution: Integer describing pixel size in m (10, 20, or 60). Defaults to 20 m.

    Returns:
        A list describing the extent of the .SAFE file granule, in the format [xmin, ymin, xmax, ymax].
        EPSG code of the coordinate reference system of the granule
    '''

    import lxml.etree as ET
    
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


def improveMask(data, res):
    """
    Function that applied tweaks to the cloud mask output from sen2cor. Processes are: (1) Changing 'dark features' to 'cloud shadows, (2) Dilating 'cloud shadows', 'medium probability cloud' and 'high probability cloud' by 180 m. (3) Eroding outer 3 km of the tile.
    
    Args:
        data: A mask from sen2cor
        res: Integer of resolution to be processed (i.e. 10 m, 20 m, 60 m). This should match the resolution of the mask.
    
    Returns:
        A numpy array of the SCL mask with modifications.
    """
        
    # Make a copy of the original classification mask
    data_orig = data.copy()
    
    # Change pixels labelled as 'dark features' to cloud shadows
    data[data==2] = 3
    
    # Change cloud shadows not within 1800 m of a cloud pixel to water
    iterations = 1800/res
    
    # Identify pixels proximal to any measure of cloud cover
    cloud_dilated = scipy.ndimage.morphology.binary_dilation((np.logical_or(data==8, data==9)).astype(np.int), iterations = iterations)
    
    data[np.logical_and(data == 3, cloud_dilated == 0)] = 6
        
    # Dilate cloud shadows, med clouds and high clouds by 180 m.
    iterations = 180 / res
    sortScenes
    # Make a temporary dataset to prevent dilated masks overwriting each other
    data_temp = data.copy()
    
    for i in [3,8,9]:
        # Grow the area of each input class
        mask_dilate = scipy.ndimage.morphology.binary_dilation((data==i).astype(np.int), iterations = iterations)
        
        # Set dilated area to the same value as input class
        data_temp[mask_dilate] = i
        
    data = data_temp

    # Erode outer 0.6 km of image tile (should retain overlap)
    iterations = 600/res 
    
    # Shrink the area of measured pixels (everything that is not equal to 0)
    mask_erode = scipy.ndimage.morphology.binary_erosion((data_orig != 0).astype(np.int), iterations=iterations)
    
    # Set these eroded areas to 0
    data[mask_erode == False] = 0
    
    return data


def histogram_match(source, reference):
    """       
    Adjust the values of a source array so that its histogram matches that of a reference array
    
    Modified from: https://github.com/mapbox/rio-hist/blob/master/rio_hist/match.py
    
    Args:
        source: A numpy array of Sentinel-2 data
        reference: A numpy array of Sentinel-2 data to match colours to

    Returns:
        target: A numpy array array with the same shape as source
    """
    
    orig_shape = source.shape
    source = source.ravel()

    if np.ma.is_masked(reference):
        reference = reference.compressed()
    else:
        reference = reference.ravel()

    # Get the set of unique pixel values
    s_values, s_idx, s_counts = np.unique(
        source, return_inverse=True, return_counts=True)
    
    # and those to match to
    r_values, r_counts = np.unique(reference, return_counts=True)
    s_size = source.size

    if np.ma.is_masked(source):
        mask_index = np.ma.where(s_values.mask)
        s_size = np.ma.where(s_idx != mask_index[0])[0].size
        s_values = s_values.compressed()
        s_counts = np.delete(s_counts, mask_index)

    # Calculate cumulative distribution
    s_quantiles = np.cumsum(s_counts).astype(np.float64) / s_size
    r_quantiles = np.cumsum(r_counts).astype(np.float64) / reference.size

    # Find values in the reference corresponding to the quantiles in the source
    interp_r_values = np.interp(s_quantiles, r_quantiles, r_values)

    if np.ma.is_masked(source):
        interp_r_values = np.insert(interp_r_values, mask_index[0], source.fill_value)

    # using the inverted source indicies, pull out the interpolated pixel values
    target = interp_r_values[s_idx]

    if np.ma.is_masked(source):
        target = np.ma.masked_where(s_idx == mask_index[0], target)
        target.fill_value = source.fill_value

    return target.reshape(orig_shape)


if __name__ == '__main__':
    '''
    '''
    
    import argparse
    
    # Set up command line parser
    parser = argparse.ArgumentParser(description = "This file contains functions to assist in the mosaicking and masking of Sentinel-2 data. A command line interface for image mosaicking is provided in mosaic.py.")
    
    args = parser.parse_args()