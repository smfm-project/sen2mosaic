from setuptools import setup

setup(name='sen2mosaic',
      packages = ['sen2mosaic'],
      data_files=[('./cfg/', ["cfg/L2A_GIPP.xml"])],
      version='0.2',
      description='Tools to generate cloud-free mosaics of Sentinel-2 data.',
      url='https://bitbucket.org/sambowers/sen2mosaic',
      author='Samuel Bowers',
      author_email='sam.bowers@ed.ac.uk',
      license='GNU General Public License',
      zip_safe=False)

#      install_requires=['argparse', 'copy', 'datetime', 'functools', 'glob', 'multiprocessing', 'numpy', 'os', 'osgeo', 'pandas', 'pdb', 'psutil', 'queue', 're', 'scipy', 'sentinelsat', 'shutil', 'signal', 'subprocess', 'tempfile', 'time', 'xml', 'zipfile']
