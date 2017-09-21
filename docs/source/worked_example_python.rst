.. _worked_example_python:

Worked example in Python
========================

[TO COMPLETE]

As an example, here's a Python script that can be run to reproduce the results from the command line operations we ran through in the section :ref:`worked_example_commandline`.

.. code-block:: python
    
    import os
    
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
        output_dir = os.path.join(output_dir, tile)
        
        # Make a directory for each tile, and cd into it
        os.mkdir(output_dir)
        os.chdir(output_dir)
        
        # Download data from Copernicus Open Access Data Hub
        sen2mosaic.L1C.main()
        
        # Perform atmospheric correction on each file
        sen2mosaic.L2A.main()
        
        # Generate a cloud free composite product
        sen2mosaic.L3A.main()
    
    # Combine the L3A files into an output GeoTiff mosaic tile
    sen2mosaic.L3B.main()
        
Let's say that we wanted to generate a mosaic product which did not use the cloud mask improvements implemented in ``sen2mosaic``. In this case you could modify the processing chain as follows:

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
        output_dir = os.path.join(output_dir, tile)
        
        # Make a directory for each tile, and cd into it
        os.mkdir(output_dir)
        os.chdir(output_dir)
        
        # Download data from Copernicus Open Access Data Hub
        sen2mosaic.L1C.main()
        
        # For each level 1C Sentinel-2 file...
        for L1C_file in glob.glob(output_dir + '/*_MSIL1C_*.SAFE):
            
            # Perform atmospheric correction
            sen2mosaic.L2A.processToL2A(L1C_file)
        
        # Generate a cloud free composite product
        sen2mosaic.L3A.main()
    
    # Combine the L3A files into an output GeoTiff mosaic tile
    sen2mosaic.L3B.main()