import tarfile
from typing import List
from zipfile import ZipFile
import tempfile
import subprocess
from multiprocessing import Process, Queue

Q = Queue()

CMDpipdownload2 = 'pip3 download {package} -d {tempdir} --no-binary :all: --no-deps --extra-index-url=https://pypi.lyft.net/simple'
CMDpipdownload = 'pip3 download {package} -d {tempdir} --python-version 3 --no-deps --extra-index-url=https://pypi.lyft.net/simple'
CMDgetdownloadedpackage = 'find {dir} -name {pattern}'
PYTYPED = 'py.typed'


def tar_contains_pytyped_files(members) -> bool:
    return any(ti.isfile() and ti.name.endswith(PYTYPED) for ti in members)


def zip_contains_pytyped_files(zfile: ZipFile) -> bool:
    return any(f.endswith(PYTYPED) for f in zfile.namelist())


def check_mypy_support(package):
    with tempfile.TemporaryDirectory() as td:
        print('created temporary directory', td, 'for package', package)
        result = subprocess.run(CMDpipdownload.format(package=package, tempdir=td).split(), stdout=subprocess.PIPE)
        if result.returncode != 0:
            raise Exception(f'Failed to download {package}. {result.stdout}')
        print('downloaded pkg ', package)
        result = subprocess.run(CMDgetdownloadedpackage.format(dir=td, pattern='*').split(), stdout=subprocess.PIPE)
        print(f'{package} get fname result {vars(result)}')
        package_file = result.stdout.decode('utf-8').strip().split()[-1]
        if package_file.endswith('.zip') or package_file.endswith('.whl'):
            with ZipFile(package_file) as zf:
                return zip_contains_pytyped_files(zf)
        elif package_file.endswith('.tar.gz'):
            with tarfile.open(package_file, "r:gz") as tf:
                return tar_contains_pytyped_files(tf)
        else:
            raise Exception(f'Unexpected file type {package_file}')


def get_direct_dep_packages(requirements_file) -> List[str]:
    pkgs = []
    with open(requirements_file) as f:
        for line in f.readlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('#')
            print(parts)
            if len(parts) > 1 and parts[1].strip().startswith('via'):  # skip indirect dep
                continue
            if parts[0].split()[0].startswith('-e'):
                pkgs.append(parts[0].split()[1].strip())
            else:
                pkgs.append(parts[0].strip())
    return pkgs


def process_func(pkg, q):
    supported = False
    try:
        supported = check_mypy_support(pkg)
        q.put((pkg, supported))
    except Exception as ex:
        q.put((pkg, ex))


def run():
    processes = [Process(target=process_func, args=(pkg, Q,))
                 for pkg in get_direct_dep_packages('/Users/panliu/src/enterprise/requirements3.txt')]

    for p in processes:
        p.start()

    for p in processes:
        p.join()

    supported_pkgs = []
    error_pkgs = []

    for p in processes:
        res = Q.get()
        if res[1] is True:
            supported_pkgs.append(res[0])
        elif isinstance(res[1], Exception):
            error_pkgs.append(f'pkg {res[0]} exception {res[1]}')

    print('\n\n\n')
    print('##############################################################')
    print('##############################################################')
    print('The following direct dependencies support type checking:')
    print('\n'.join(sorted(supported_pkgs)))
    print('\n##############################################################\n')
    print('The following direct dependencies check failed due to errors:')
    print('\n'.join(sorted(error_pkgs)))
    print('##############################################################')
    print('##############################################################')
    


run()
