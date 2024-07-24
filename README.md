## omnibenchmark

<p align="center">
<a href="ttps://github.com/omnibenchmark/omni-py"><img alt="Tests" src="./reports/tests.svg"></a>
<a href="https://github.com/omnibenchmark/omni-py/actions"><img alt="Actions Status" src="https://github.com/omnibenchmark/omni-py/workflows/Tests/badge.svg"></a>
<a href="ttps://github.com/omnibenchmark/omni-py"><img alt="Coverage Status" src="./reports/coverage.svg"></a>
<a href="https://github.com/omnibenchmark/omni-py/blob/main/LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache_2.0-blue.svg"></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>


The entrypoint to omnibenchmark. It contains a cli and multiple utility functions to support module development via requirements checks, validation and container handling. 

# How to run

## install python

```
mkdir -p ~/soft/python
cd $_
wget https://www.python.org/ftp/python/3.12.3/Python-3.12.3.tgz
tar xzvf Python-3.12.3.tgz
cd Python-3.12.3
./configure --enable-optimizations
make -j 8
sudo make altinstall # to /usr/local/bin/python3.12

```

## pip

```
mkdir -p ~/virtenvs
/usr/local/bin/python3.12 -m venv ~/virtenvs/omni

source ~/virtenvs/omni/bin/activate
#pip install https://github.com/omnibenchmark/omni-py/archive/sw_imallona.zip
pip install https://github.com/omnibenchmark/omni-py/archive/main.zip
```

## Installing poetry too

Create a virtualenv and install poetry, with a compilled (altinstall) python3.12


```
mkdir -p ~/virtenvs
/usr/local/bin/python3.12 -m venv ~/virtenvs/poetry
source ~/virtenvs/poetry/bin/activate
curl -sSL https://install.python-poetry.org | python3 -
poetry --version
```

Clone the repo

```
mkdir -p ~/src
cd ~/src
git clone git@github.com:omnibenchmark/omni-py.git
```

```
cd ~/src/omni-py
poetry shell
poetry install
ob --help
deactivate
```

## Directly

Clone the repo

```
mkdir -p ~/src
cd ~/src
git clone git@github.com:omnibenchmark/omni-py.git
```

Install

```
pip install omni-py
```

To develop

```
pip install poetry
poetry shell
ob --help
ob fetch --help
```

## Once installed

```
source ~/virtenvs/poetry/bin/activate 
poetry shell
```

<!-- ## No-poetry, no-environ -->

<!-- Largely as in https://stackoverflow.com/questions/71769359/how-to-use-python-poetry-to-install-package-to-a-virtualenv-in-a-standalone-fash -->

<!-- ``` -->
<!-- su - $(whoami) # start clean -->
<!-- echo $PATH -->

<!-- cd ~/src/omni-py -->

<!-- ## export to a requirements.txt; assume `poetry` is available from somewhere -->
<!-- poetry export --without-hashes -f requirements.txt -o /tmp/requirements.txt -->

<!-- # create a new venv -->
<!-- mkdir -p ~/virtenvs && cd ~/virtenvs -->
<!-- /usr/local/bin/python3.12 -m venv omni && . omni/bin/activate -->

<!-- # then install the dependencies -->
<!-- pip install --no-cache-dir --no-deps -r /tmp/requirements.txt -->
<!-- pip install setuptools # https://stackoverflow.com/a/76691103 -->
<!-- pip install poetry     # so poetry is installed in an env NOT handled by poetry -->

<!-- # install cli -->
<!-- cd ~/src/omni-py -->
<!-- pip install . -->

<!-- eb --help -->
<!-- snakemake --version -->
<!-- poetry --version -->
<!-- ``` -->

# How to get the conda and mamba dependencies (particularly for testing)

```
## assuming the repo is at ~/src/omni-py
mamba env create -n "test" -f ~/src/omni-py/test-environment.yml
conda activate test
cd ~/src/omni-py
pip install .
```

# How tu contribute

Lorem ipsum
