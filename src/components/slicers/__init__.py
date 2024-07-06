import pkgutil
__path__ = pkgutil.extend_path(__path__, __name__)

__all__ = []

def convert(word):
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