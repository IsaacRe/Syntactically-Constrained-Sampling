# Modified Regex for Syntactically Constrained LLM Sampling

The `scs_re` package is a modified version of the python `re` module that returns a match for any prefix of a string matching the original regex pattern. For example, the pattern `^abcd` matches the string `abc`. This behavior is used to consider the validity of beams under a particular regex pattern during a language model's output generation.

**Note**: This behavior is only expected for patterns that begin with `^` and end with `$` and therefore define a match contstraint over all characters in a sequence.

### Building from source

We use the _sre module from the python 3.11 branch of Python/cpython/Modules/_sre. You can clone the original source by running

```bash
svn export https://github.com/python/cpython/branches/3.11/Modules/_sre _sre
```

The module requires python 3.11 headers to compile. To install run

```bash
wget https://www.python.org/ftp/python/3.11.3/Python-3.11.3.tar.xz
tar xf Python-3.11.3.tar.xz
cd Python-3.11.3
./configure --enable-optimizations --enable-shared
make -j$(nproc)
sudo make altinstall
```

Then you can install the package with `sudo python3.11 setup.py install` to install. **The python version you install to must be the same version whose headers were compiled against**.