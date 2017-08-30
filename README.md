# README #

### What is this repository for? ###

This is a set of tools to aid in the production of large-scale cloud-free seasonal mosaic products from Sentinel-2 data.

This repository contains three command-line based tools to perform the following tasks:

* Downloading Sentinel-2 data from the [Sentinel Scientific Data Hub](https://scihub.copernicus.eu/) for a particular tile, specifying date ranges and degrees of cloud cover.
* Executing the [sen2cor](http://step.esa.int/main/third-party-plugins-2/sen2cor/) tool to perform atmospheric correction, and performing simple improvements to its cloud mask.
* Building a mosaic of cloud-free outputs from [sen2three](http://step.esa.int/main/third-party-plugins-2/sen2three/).

### How do I get set up? ###

These tools are written in Python for use in Linux. You will need to have first successfully installed:

* [sen2cor](http://step.esa.int/main/third-party-plugins-2/sen2cor/)
* [sen2three](http://step.esa.int/main/third-party-plugins-2/sen2three/)

which are both built around the [Anaconda](https://www.anaconda.com/download/) distribution of Python. The modules used in these scripts are all available in Anaconda Python.

### Who do I talk to? ###

Written and maintained by Samuel Bowers ([sam.bowers@ed.ac.uk](mailto:sam.bowers@ed.ac.uk)).