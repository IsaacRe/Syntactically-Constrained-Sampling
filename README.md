We use the _sre module from the python 3.11 branch of Python/cpython/Modules/_sre.

Steps:
1. Install python 3.11 developer dependencies:
    ```bash
    wget https://www.python.org/ftp/python/3.11.3/Python-3.11.3.tar.xz
    tar xf Python-3.11.3.tar.xz
    cd Python-3.11.3
    ./configure --enable-optimizations --enable-shared
    make -j$(nproc)
    sudo make altinstall
    cd ..
    ```
2. Clone _sre module:
    ```bash
    cd syntactically-constrained-sampling
    svn export https://github.com/python/cpython/branches/3.11/Modules/_sre _sre
    ```
3. Make changes to `sre.c` to export the model as `scs_sre` instead of `_sre`
4. Run `sudo python3.11 setup.py install` to install
    - **The python version you install it to must be the same version whose headers were compiled against**


To build, make sure you have python3.8 installed and run 