from distutils.core import setup, Extension

module = Extension(
    'scs_sre',
    sources=['_sre/sre.c'],
    include_dirs=['/usr/local/include/python3.11', '/usr/local/include/python3.11/internal'],
    extra_compile_args=["-D", "Py_BUILD_CORE"],
)

setup(name='scs_re', version='1.0', description='Example module', ext_modules=[module], packages=["scs_re"])