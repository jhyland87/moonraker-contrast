from pathlib import Path
print('Running' if __name__ == '__main__' else 'Importing', Path(__file__).resolve())

from os.path import dirname, basename, isfile, join

import glob

modules = glob.glob(join(dirname(__file__), "*.py"))
print("modules:",modules)

__all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]




#__all__.append('cura_slicer.CuraSlicer')
#__all__.append('prusa_slicer.PrusaSlicer')
#__all__.append('bamboo_slicer.BambooSlicer')
#__all__.append('base_slicer.BaseSlicer')
#__all__.append('orca_slicer.OrcaSlicer')

__all__.append('generic_slicer')
__all__.append('cura_slicer')
__all__.append('prusa_slicer')
__all__.append('bamboo_slicer')
__all__.append('orca_slicer')

__all__.append('generic_slicer.GenericSlicer')

__all__.append('cura_slicer.CuraSlicer')
__all__.append('prusa_slicer.PrusaSlicer')
__all__.append('bamboo_slicer.BambooSlicer')
__all__.append('orca_slicer.OrcaSlicer')


__all__.append('GenericSlicer')
__all__.append('CuraSlicer')
__all__.append('PrusaSlicer')
__all__.append('BambooSlicer')
__all__.append('OrcaSlicer')



#__all__: ['cura_slicer', 'prusa_slicer', 'bamboo_slicer', 'base_slicer', 'orca_slicer']
print("__all__:",__all__)


#__package__ = ""
"""
import pkgutil
__path__ = pkgutil.extend_path(__path__, __name__)

__all__ = []

def convert(word):import slicers

    return ''.join(x.capitalize() or '_' for x in word.split('_'))


for imp, module, ispackage in pkgutil.walk_packages(path=__path__, prefix=__name__+'.'):
    print("imp:", imp)
    print("module:", module)
    print("ispackage:", ispackage)
    print("__path__:", __path__)
    print("__path__:", __path__)

    __import__(module)
    __all__.append(convert(module.split('.')[1]))

    print("__all__:",__all__)

#import os, pkgutil
#__all__ = list(module for _, module, _ in pkgutil.iter_modules([os.path.dirname(__file__)]))


"""
"""
from os.path import dirname, basename, isfile, join
import glob
modules = glob.glob(join(dirname(__file__), "*.py"))

def convert(word):
    return ''.join(x.capitalize() or '_' for x in word.split('_'))

__all__ = [ convert(basename(f)[:-3]) for f in modules if isfile(f) and not f.endswith('__init__.py')]

print("__all__:",__all__)

#__all__ = ['BaseSlicer', 'PrusaSlicer']
"""

"""
import os
for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module[-3:] != '.py':
        continue
    print(module[:-3])
    __import__(module[:-3], locals(), globals())
del module
"""