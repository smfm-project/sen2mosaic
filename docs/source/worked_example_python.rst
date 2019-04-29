.. _worked_example_python:

Worked example in Python
========================

[NOT CURRENTLY VALID]

As an example, here's a Python script that can be run to reproduce the results from the command line operations we ran through in the section :ref:`worked_example_commandline`.

.. code-block:: python
    
    import os
    import glob 
    
    import sen2mosaic.L1C
    import sen2mosaic.L2A
    import sen2mosaic.L3A
    import sen2mosaic.L3B
    
    # Define the tiles we want to process
    tiles = ['36KWA', '36KWB']
    
    # Set a directory to work in
    data_dir = '/home/user/DATA/worked_example_python/'
    
    for tile in tiles:
        
        # Determine a directory to output a tile into
        output_dir = os.path.join(data_dir, tile)
        
        # Make a directory for each tile, if it doesn't already exist
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        
        # Download data from Copernicus Open Access Data Hub
        sen2mosaic.L1C.main('user.name', 'supersecret', tile, start = '20170501', end = '20170630', maxcloud = 30, output_dir = output_dir)
        
        # For each level 1C Sentinel-2 file...
        for L1C_file in glob.glob(output_dir + '/*_MSIL1C_*.SAFE'):
            
            # Perform atmospheric correction and cloud masking
            sen2mosaic.L2A.main(L1C_file)

        # Generate a cloud free composite product
        sen2mosaic.L3A.main(output_dir)
    
    # Get a list of level 3 output files
    L3_files = glob.glob(data_dir + '/36KW*/*_MSIL03_*.SAFE')
    
    # Combine the L3A files into an output GeoTiff mosaic tile
    sen2mosaic.L3B.main(L3_files, [500000, 7550000, 600000, 7650000], 32736, output_name = 'worked_example')
        
Let's say that we wanted to generate a mosaic product which did not use the cloud mask improvements implemented in ``sen2mosaic``, and that we wanted to delete previous processing steps as we progressed. In this case, we could modify the processing chain as follows:

.. code-block:: python
    
    import os
    import glob
    
    import sen2mosaic.L1C
    import sen2mosaic.L2A
    import sen2mosaic.L3A
    import sen2mosaic.L3B
    
    # Define the tiles we want to process
    tiles = ['36KWA', '36KWB']
    
    # Set a directory to work in
    data_dir = '/home/user/DATA/worked_example_python/'
    
    for tile in tiles:
        
        # Determine a directory to output a tile into
        output_dir = os.path.join(data_dir, tile)
        
        # Make a directory for each tile, if it doesn't already exist
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        
        # Download data from Copernicus Open Access Data Hub
        sen2mosaic.L1C.main('user.name', 'supersecret', tile, start = '20170501', end = '20170630', maxcloud = 30, output_dir = output_dir, remove = True)
        
        # For each level 1C Sentinel-2 file...
        for L1C_file in glob.glob(output_dir + '/*_MSIL1C_*.SAFE'):
            
            # Perform atmospheric correction only
            sen2mosaic.L2A.processToL2A(L1C_file, remove = True)
        
        # Generate a cloud free composite product
        sen2mosaic.L3A.main(output_dir)
    
    # Get a list of level 3 output files
    L3_files = glob.glob(data_dir + '/36KW*/*_MSIL03_*.SAFE')
    
    # Combine the L3A files into an output GeoTiff mosaic tile
    sen2mosaic.L3B.main(L3_files, [500000, 7550000, 600000, 7650000], 32736)
