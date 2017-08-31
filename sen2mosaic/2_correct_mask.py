# Makes efforts to replicate gmv cloud masking improvement algorithm
# Only run once and don't interrupt, else things will get funky

import glob
import numpy as np
import matplotlib.pyplot as plt
from scipy import ndimage
import argparse
import os
import glymur
import tempfile

  
def main(this_file):
  
    
    class_images = sorted(glob.glob('%s/GRANULE/*/IMG_DATA/R*m/*_SCL_*.jp2'%this_file))
    
    for class_im in class_images:
      
        print 'Doing %s'%class_im.split('/')[-1] 
        
        # Load each file
        jp2 = glymur.Jp2k(class_im) #ds = gdal.Open(class_im)
               
        data_in = jp2[:] #data_in = ds.ReadAsArray() # Input array
        data = data_in # Working array
        
        # Get rid of 'low clouds' (set to 'vegetation' instead)
        # data[data==7] = 4
        
        # Change 'dark features' to cloud shadows
        data[data==2] = 3

        # Get resolution        
        res = int(class_im.split('.')[-2].split('_')[-1].split('m')[0]) # 20 or 60 m
        
        # Grow cloud shadows, med clouds and high clouds
        iterations = 120/res # 120 m buffer around edge of clouds/shadows

        data_temp = data # Don't allow classes to shrink each other
        for i in [3,8,9]:
            mask_dilate = ndimage.morphology.binary_dilation((data==i).astype(np.int), iterations=iterations)
            data_temp[mask_dilate] = i
        data = data_temp

        # Erode outer 3 km of sub-image (should retain overlap)
        iterations = 3000/res # 3 km buffer around edge
        
        mask_erode = ndimage.morphology.binary_erosion((data_in!=0).astype(np.int), iterations=iterations)
        data[mask_erode==False] = 0
        
        # To view data:
        #ax1 = plt.subplot(121)
        #ax1.imshow(data_in,vmin=0,vmax=11)
        #ax2 = plt.subplot(122, sharex=ax1, sharey=ax1)
        #ax2.imshow(data,vmin=0,vmax=11)
        #plt.show()
        
        # Get metadata (including projection)
        boxes = jp2.box


        # Generate a temporary output file
        temp_jp2 = tempfile.mktemp(suffix='.jp2') #'/'+'/'.join(class_im.split('/')[:-1])+'/temp_out.jp2'
        
        # Important options for .jp2 file for sen2cor/sen2Three to understand image
        kwargs = {"tilesize": (640, 640), "prog": "RPCL"}

        # Save temporary image to generate metadata (boxes)
        jp2_out = glymur.Jp2k(temp_jp2, data=data, **kwargs)

        # Replace boxes in modified file with originals
        boxes_out = jp2_out.box

        boxes_out[0] = boxes[0]
        boxes_out[1] = boxes[1]
        boxes_out[2] = boxes[2]
        boxes_out.insert(3,boxes[3])

        # Make a copy of the original file
        os.system('cp %s %s'%(class_im,class_im[:-4]+'_old.jp2'))

        # Overwite original file
        jp2_out.wrap(class_im,boxes=boxes_out)



if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser()
    parser.add_argument('infiles', metavar='N', type=str, nargs='+', help='Input files. Either specify a valid level 2a .SAFE file, or multiple files through wildcards.')
    parser.add_argument('-v', '--verbose', action='store_true', default = False, help='Do you want the script to speak? Use this flag if so.')

    args = parser.parse_args()
    
    infiles = sorted([os.path.abspath(i) for i in args.infiles]) # Convert to absolute path
    verbose = args.verbose
    
    for infile in infiles:
        
        if verbose: print 'Processing %s'%infile.split('/')[-1]
        
        main(infile)

   



        
