import os
from distutils.core import setup, Extension

working_dir = os.getcwd()

module = Extension(
    'scs_sre',
    sources=['_sre/sre.c'],
    include_dirs=['/usr/local/include/python3.11', '/usr/local/include/python3.11/internal', f'{working_dir}/_sre'],
    extra_compile_args=["-D", "Py_BUILD_CORE"],
)

setup(
    name='scs_re',
    version='1.0.3',
    url='https://github.com/IsaacRe/Syntactically-Constrained-Sampling',
    description='Modification of cpython `re` module in which patterns match any string that is a prefix of a matching string under its regex',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    ext_modules=[module],
    packages=["scs_re"],
)