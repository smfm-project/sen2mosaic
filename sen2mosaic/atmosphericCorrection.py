import argparse
from contextlib import contextmanager
import glob
import glymur
import matplotlib.pyplot as plt
import numpy as np
import os
from scipy import ndimage
import shutil
import tempfile


@contextmanager
def cd(newdir):
    """
    This code ensures that the user returns to the original directory after running L2A_Process.
    It's necessary as sen2cor's L2A_Process only outputs to the present working directory.
    """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def processToL2A(infile, output_dir = os.getcwd()):
    """
    Processes Sentinel-2 level 1C files to level L2A with sen2cor.
    Input a single .SAFE file.
    Returns the output file name and its absolute directory location.
    """
    
    # Test that input file is in .SAFE format
    assert infile[-5:] == '.SAFE', "Input files must be in .SAFE format."
    
    # Move to output directory and run sen2cor (L2A_Process)
    with cd(output_dir):
        os.system('L2A_Process %s'%this_file)
    
    # Determine output file name, replacing last instance only of substring _MSIL1C_ with _MSIL2A_
    outfile = infile[::-1].replace('_MSIL1C_','_MSIL2A_',1)[::-1]
    
    outpath = os.path.join(output_dir, outfile)
    
    # Test if AUX_DATA output directory exists. If not, create it, as it's absense crashes sen2Three.
    if not os.path.exists('%s/AUX_DATA'%outpath):
        os.makedirs('%s/AUX_DATA'%outpath)
    
    return outpath


def loadMask(L2A_file, res):
    '''
    Load classification mask given .SAFE file and resolution.
    Returns a glymur .jp2 file the directory and name of the classified image.
    '''
    
    # Remove trailing slash from input filename, if it exists
    L2A_file.rstrip('/')
    
    # Identify the cloud mask following the standardised file pattern
    image_path = glob.glob('%s/GRANULE/*/IMG_DATA/R*m/*_SCL_*R%s*m.jp2'%(L2A_file, str(res)))[0]
    
    # Load the cloud mask (.jp2 format)
    jp2 = glymur.Jp2k(image_path)

    return jp2, image_path


def improveMask(jp2, res):
    '''
    Tweaks the cloud mask output from sen2cor.
    Processes are:
        1) Changing 'dark features' to 'cloud shadows
        2) Dilating 'cloud shadows', 'medium probability cloud' and 'high probability cloud' by 120 m
        3) Eroding outer 3 km of the tile to improve stitching of images by sen2Three.
    '''
    
    # Read file as numpy array
    data = jp2[:]
    
    # Make a copy of the original classification mask
    data_orig = data
    
    # Change pixels labelled as 'dark features' to cloud shadows
    data[data==2] = 3
        
    # Dilate cloud shadows, med clouds and high clouds by 120 m.
    iterations = 120 / res
    
    # Make a temporary dataset to prevent dilated masks overwriting each other
    data_temp = data
    
    for i in [3,8,9]:
        # Grow the area of each input class
        mask_dilate = ndimage.morphology.binary_dilation((data==i).astype(np.int), iterations = iterations)
        
        # Set dilated area to the same value as input class
        data_temp[mask_dilate] = i
        
    data = data_temp

    # Erode outer 3 km of image tile (should retain overlap)
    iterations = 3000/res # 3 km buffer around edge
    
    # Shrink the area of measured pixels (everything that is not equal to 0)
    mask_erode = ndimage.morphology.binary_erosion((data_orig != 0).astype(np.int), iterations=iterations)
    
    # Set these eroided areas to 0
    data[mask_erode == False] = 0
    
    return data


def writeMask(jp2, data, image_path):
    '''
    Overwrites the old mask with a new one, preserving the metadata (including projection info) from the original .jp2 file.
    Inputs are a glymur jp2 file, the new data to overwrite the old mask with, and the path to the original classified image.
    '''
          
    # Get metadata from original .jp2 file (including projection)
    boxes = jp2.box

    # Generate a temporary output file
    temp_jp2 = tempfile.mktemp(suffix='.jp2')
        
    # Important options for .jp2 file, required for sen2cor/sen2Three to understand image
    kwargs = {"tilesize": (640, 640), "prog": "RPCL"}

    # Save temporary image to generate metadata (boxes)
    jp2_out = glymur.Jp2k(temp_jp2, data = data, **kwargs)

    # Replace boxes in modified file with originals
    boxes_out = jp2_out.box

    boxes_out[0] = boxes[0]
    boxes_out[1] = boxes[1]
    boxes_out[2] = boxes[2]
    boxes_out.insert(3,boxes[3]) # This is the projection info
    
    # Make a copy of the original file
    shutil.copy2(image_path, image_path[:-4]+'_old.jp2')

    # Overwite original file
    jp2_out.wrap(image_path, boxes = boxes_out)


def main(infile, output_dir = os.getcwd()):
    """
    Function to initiate L2A_Process on input files and improvements to cloud masking.
    """
    
    # Run sen2cor
    L2A_file = processToL2A(infile, output_dir = output_dir)
    
    # Perform improvements to mask for each resolution
    for res in [20,60]:
        cloudmask_old, image_path = loadMask(L2A_file, res)
        cloudmask_new = improveMask(cloudmask_old, res)
        writeMask(cloudmask_old, cloudmask_new, image_path)


if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to bottom of atmosphere reflectance, and generate a cloud mask. This script initiates sen2cor, then performs simple improvements to the cloud mask.')
    
    # Required arguments
    parser.add_argument('infiles', metavar = 'N', type = str, nargs = '+', help = 'Sentinel 2 input files (level 1C) in .SAFE format. Specify one or more valid Sentinel-2 input files, or multiple files through wildcards (*). Input wills will be atmospherically corrected.')

    # Optional arguments
    parser.add_argument('-o', '--output', type = str, default = os.getcwd(), help = "Optionally specify an output directory. If nothing specified, atmospherically corrected images will be written to the present working directory.")
    
    # Get arguments
    args = parser.parse_args()
    
    # Where only one file input, ensure its a list so that it behaves properly in loops
    infiles = list(args.infiles)
    
    # Get absolute path of input files.
    infiles = [os.path.abspath(i) for i in infiles]
        
    # Run the script for each input file
    for infile in infiles:
        main(infile, output_dir = args.output)
    