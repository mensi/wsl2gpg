import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name='wsl2gpg',
    version='0.0.1',
    author='Manuel Stocker',
    author_email='mensi@mensi.ch',
    description='Create UNIX sockets and proxy to the gpg4win agent',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/mensi/wsl2gpg',
    packages=setuptools.find_packages(),
    python_requires='>=3.5',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX'
    ],
    entry_points={
        'console_scripts': [
            'wsl2gpg = wsl2gpg:main'
        ]
    }
)
