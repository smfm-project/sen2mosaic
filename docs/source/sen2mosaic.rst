Using sen2mosaic in Python
==========================

This is harder than the command line, but you may be interested in importing the sen2mosaic functions into Python in order to customise the processing chain.

To make sen2mosaic accesible in Python, edit your ``.bashrc`` file (usually located at ``~/.bashrc`` to contain the line:

.. code-block:: console
    
    export PYTHONPATH=$PYTHONPATH:/path/to/sen2mosaic/

You should now be able to import each of the four modules in Python as follows:

.. code-block:: python
    
    import sen2mosaic.download
    import sen2mosaic.preprocess
    import sen2mosaic.composite
    import sen2mosaic.mosaic

Help for each function can be accessed interactively from Python. For example:

.. code-block:: python
    
    >>> help(sen2mosaic.download.connectToAPI)
            Help on function connectToAPI in module sen2mosaic.download:

            connectToAPI(username, password)
            Connect to the SciHub API with sentinelsat.
            
            Args:
                username: Scihub username. Sign up at https://scihub.copernicus.eu/.
                password: Scihub password.

On this page each of the functions from the download, preprocess, composite and mosaic modules are documented. Note that the ``main()`` function in each is what is driven by the command line tools, so in addition to it's component parts you can call the entire processing chain from Python.

Download module
---------------

.. automodule:: sen2mosaic.download
    :members:
    :undoc-members:
    :show-inheritance:

Preprocess module
-----------------

.. automodule:: sen2mosaic.L2A
    :members:
    :undoc-members:
    :show-inheritance:

Composite module
----------------

.. automodule:: sen2mosaic.L3A
    :members:
    :undoc-members:
    :show-inheritance:

Mosaic module
-------------

.. automodule:: sen2mosaic.L3B
    :members:
    :undoc-members:
    :show-inheritance:

