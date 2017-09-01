.. sen2mosaic documentation master file, created by
   sphinx-quickstart on Wed Aug 30 14:56:28 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to sen2mosaic's documentation!
======================================

This is a set of tools to aid in the production of large-scale cloud-free seasonal mosaic products from Sentinel-2 data.

This repository contains three command-line based tools to perform the following tasks:

    Downloading Sentinel-2 data from the Copernicus Open Access Hub for a particular tile, specifying date ranges and degrees of cloud cover.
    Executing the sen2cor tool to perform atmospheric correction, and performing simple improvements to its cloud mask.
    Building a mosaic of cloud-free outputs from sen2three.

How do I get set up?
--------------------

These tools are written in Python for use in Linux. You will need to have first successfully installed:

    sentinelhub: A library for searching and downloading Sentinel-2 products.
    sen2cor: Atmospheric correction and cloud masking for Sentinel-2.
    sen2three: Synthesis of atmospherically corrected Sentinel-2 images into cloud-free composite images (version 1.1.0 or later).

which are both built around the Anaconda distribution of Python. The modules used in these scripts are all available in Anaconda Python.
How does it work?

Who do I talk to?
-----------------

Written and maintained by Samuel Bowers (sam.bowers@ed.ac.uk).

Contents:

.. toctree::
   :maxdepth: 2
   :numbered:
   
   setup.rst
   command_line.rst
   python.rst

Search
======

* :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

