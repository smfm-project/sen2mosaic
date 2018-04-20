#!/usr/bin/env python

import datetime as dt
import glob
import numpy as np
import os
import scipy.ndimage

import pdb


# This module contains functions to help in image mosaicking and masking.
# It's kept separate, as it's functions will be used elsewhere.



def histogram_match(source, reference):
    """       
    Adjust the values of a source array so that its histogram matches that of a reference array
    
    From: https://github.com/mapbox/rio-hist/blob/master/rio_hist/match.py
    
    Args:
        source: numpy array
        reference: numpy array

    Returns:
        target: A numpy array array with the same shape as source
    """
    
    orig_shape = source.shape
    source = source.ravel()

    if np.ma.is_masked(reference):
        reference = reference.compressed()
    else:
        reference = reference.ravel()

    # get the set of unique pixel values
    # and their corresponding indices and counts
    s_values, s_idx, s_counts = np.unique(
        source, return_inverse=True, return_counts=True)
    r_values, r_counts = np.unique(reference, return_counts=True)
    s_size = source.size

    if np.ma.is_masked(source):
        mask_index = np.ma.where(s_values.mask)
        s_size = np.ma.where(s_idx != mask_index[0])[0].size
        s_values = s_values.compressed()
        s_counts = np.delete(s_counts, mask_index)

    # take the cumsum of the counts; empirical cumulative distribution
    s_quantiles = np.cumsum(s_counts).astype(np.float64) / s_size
    r_quantiles = np.cumsum(r_counts).astype(np.float64) / reference.size

    # find values in the reference corresponding to the quantiles in the source
    interp_r_values = np.interp(s_quantiles, r_quantiles, r_values)

    if np.ma.is_masked(source):
        interp_r_values = np.insert(interp_r_values, mask_index[0], source.fill_value)

    # using the inverted source indicies, pull out the interpolated pixel values
    target = interp_r_values[s_idx]

    if np.ma.is_masked(source):
        target = np.ma.masked_where(s_idx == mask_index[0], target)
        target.fill_value = source.fill_value

    return target.reshape(orig_shape)




def getS2Metadata(granule_file, resolution = 20):
    '''
    Function to extract georefence info from level 2A Sentinel 2 data in .SAFE format.
    
    Args:
        granule_file: String with /path/to/the/granule folder bundled in a .SAFE file.
        resolution: Integer describing pixel size in m (10, 20, or 60). Defaults to 20 m.

    Returns:
        A list describing the extent of the .SAFE file granule, in the format [xmin, ymin, xmax, ymax].
        EPSG code of the coordinate reference system of the granule
    '''

    import lxml.etree as ET
    
    # Remove trailing / from granule directory if present 
    granule_file = granule_file.rstrip('/')
    
    assert len(glob.glob((granule_file + '/*MTD*.xml'))) > 0, "The location %s does not contain a metadata (*MTD*.xml) file."%granule_file
    
    # Find the xml file that contains file metadata
    xml_file = glob.glob(granule_file + '/*MTD*.xml')[0]
    
    # Parse xml file
    tree = ET.ElementTree(file = xml_file)
    root = tree.getroot()
            
    # Define xml namespace (specific to level 2A Sentinel 2 .SAFE files)
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
    datetime = dt.datetime.strptime(datestring,'%Y-%m-%dT%H:%M:%S')
    
    # Get nodata percentage
    vegetated = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/L2A_Image_Content_QI/VEGETATION_PERCENTAGE",ns).text
    not_vegetated = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/L2A_Image_Content_QI/NOT_VEGETATED_PERCENTAGE",ns).text
    water = root.find("n1:Quality_Indicators_Info[@metadataLevel='Standard']/L2A_Image_Content_QI/WATER_PERCENTAGE",ns).text
    
    nodata_percent = 100. - float(water) - float(vegetated) - float(not_vegetated)
    
    # Get tile from granule filename
    if granule_file.split('/')[-1].split('_')[1] == 'USER':
        
        # If old file format
        tile = granule_file.split('/')[-1].split('_')[-2]
        
    else:
        
        # If new file format
        tile = granule_file.split('/')[-1].split('_')[1]
    
    return extent, EPSG, datetime, tile, nodata_percent


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
    
    # Make a temporary dataset to prevent dilated masks overwriting each other
    data_temp = data.copy()
    
    for i in [3,8,9]:
        # Grow the area of each input class
        mask_dilate = scipy.ndimage.morphology.binary_dilation((data==i).astype(np.int), iterations = iterations)
        
        # Set dilated area to the same value as input class
        data_temp[mask_dilate] = i
        
    data = data_temp

    # Erode outer 3 km of image tile (should retain overlap)
    iterations = 3000/res # 3 km buffer around edge
    
    # Shrink the area of measured pixels (everything that is not equal to 0)
    mask_erode = scipy.ndimage.morphology.binary_erosion((data_orig != 0).astype(np.int), iterations=iterations)
    
    # Set these eroded areas to 0
    data[mask_erode == False] = 0
    
    return data


class Metadata(object):
    '''
    This is a generic metadata class for Geosptial data
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



class LoadScene(object):
    '''
    Load a Sentinel-2, level-2 scene
    '''
        
    def __init__(self, filename, resolution = 20):
        '''
        Args:
            filename: The path to a level-2 Sentinel-2 granule file
            resolution: The resolution to be loaded (10, 20, or 60 metres).
        '''
                
        # Format filename, and check that it exists
        self.filename = self.__checkFilename(filename)
                
        # Get file format
        self.file_format = self.__getFormat()
        
        # Extract image type (S1_single, S1_dual, S2), and raise error if filename if formatted incorrectly
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
            print 'File %s does not match any expected file pattern'%self.filename
            raise IOError
        
    def __getLevel(self):
        '''
        Determines the level of Sentinel-2 image.
        
        Returns:
            An integer
        '''
        
        if self.filename.split('/')[-1][:3] == 'L2A':    
            level = 2
        elif self.filename.split('/')[-1].split('_')[3] == 'L2A':
            level = 2
        else:
            level = 1
        
        assert level == 2, "This sript only supports Sentinel-2 level 2 data."
                
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
    
    def __getImagePath(self, band, resolution):
        '''
        Get the path to a mask or band (Jpeg2000 format).
        '''
        
        # Identify source file following the standardised file pattern
        image_path = glob.glob(self.filename + '/IMG_DATA/R%sm/L2A*_%s_%sm.jp2'%(str(resolution), band, str(resolution)))
        
        assert len(image_path) > 0, "No file found for band: %s, resolution: %s."%(band, str(resolution))
        
        return image_path[0]

    
    def getMask(self, correct = False):
        '''
        Load the mask to a numpy array.
        
        Args:
            correct: Set to True to apply imporvements to the Sentinel-2 mask (recommended)
        '''
        
        import glymur

        # Don't rerun processing if mask already present in memory
        if not hasattr(self, 'mask'):
            
            # Load mask at appropriate resolution
            if self.metadata.res in [20, 60]:
                image_path = self.__getImagePath('SCL', self.resolution)
            else:
                image_path = self.__getImagePath('SCL', 20)
            
            # Load the image (.jp2 format)
            jp2 = glymur.Jp2k(image_path)
        
            # Extract array mask from .jp2 file
            mask = jp2[:]
            
            # Expand 20 m resolution mask to match 10 metre image resolution if required
            if self.metadata.res == 10:
                mask = scipy.ndimage.zoom(mask, 2, order=0)
            
            # apply corrections
            if correct:
                mask = improveMask(mask, self.resolution)
                
            # Save mask to class for later use
            self.mask = mask
                
        return self.mask
    
    def getBand(self, band):
        '''
        Load a Sentinel-2 band to a numpy array.
        '''
        
        import glymur
        
        image_path = self.__getImagePath(band, self.resolution)
        
        # Load the image (.jp2 format)
        jp2 = glymur.Jp2k(image_path)
    
        # Extract array mask from .jp2 file
        data = jp2[:]
        
        return data

if __name__ == '__main__':
    '''
    '''
    
    import argparse
    
    # Set up command line parser
    parser = argparse.ArgumentParser(description = "This file contains functions to assist in the mosaicking and masking of Sentinel-2 data. A command line interface for image mosaicking is provided in mosaic.py.")
    
    args = parser.parse_args()