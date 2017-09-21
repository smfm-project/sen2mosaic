Using sen2mosaic in Python
==========================

This is harder than the command line, but you may be interested in importing the sen2mosaic functions into Python in order to customise the processing chain.

To make sen2mosaic accesible in Python, edit your ``.bashrc`` file (usually located at ``~/.bashrc`` to contain the line:

.. code-block:: console
    
    export PYTHONPATH=$PYTHONPATH:/path/to/sen2mosaic/

You should now be able to import each of the four modules in Python as follows:

.. code-block:: python
    
    import sen2mosaic.L1C
    import sen2mosaic.L2A
    import sen2mosaic.L3A
    import sen2mosaic.L3B

Help for each function can be accessed interactively from Python. For example:

.. code-block:: python
    
    >>> help(sen2mosaic.L1C.connectToAPI)
            Help on function connectToAPI in module sen2mosaic.L1C:

            connectToAPI(username, password)
            Connect to the SciHub API with sentinelsat.
            
            Args:
                username: Scihub username. Sign up at https://scihub.copernicus.eu/.
                password: Scihub password.

On this page each of the functions from the L1C, L2A, L3A and L3B modules are documented. Note that the ``main()`` function in each is what is driven by the command line tools, so in addition to it's component parts you can call the entire processing chain from Python.

L1C module
----------

.. automodule:: sen2mosaic.L1C
    :members:
    :undoc-members:
    :show-inheritance:

L2A module
----------

.. automodule:: sen2mosaic.L2A
    :members:
    :undoc-members:
    :show-inheritance:

L3A module
----------

.. automodule:: sen2mosaic.L3A
    :members:
    :undoc-members:
    :show-inheritance:

L3B module
----------

.. automodule:: sen2mosaic.L3B
    :members:
    :undoc-members:
    :show-inheritance:

