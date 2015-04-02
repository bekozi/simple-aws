from setuptools import setup, find_packages


setup(
    name='saws',
    version='0.01a',
    packages=find_packages(where='./src'),
    package_dir={'': 'src'},
    url='https://github.com/bekozi/simple-aws',
    license='MIT',
    author='bekozi',
    author_email='ben.koziol@gmail.com',
    description='A simple management interface to Amazon Web Services using boto.'
)
