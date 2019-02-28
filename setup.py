import io
import re
import setuptools

with io.open("README.md", "rt", encoding="utf8") as f:
    long_description = f.read()

with io.open("cloudperf/__init__.py", "rt", encoding="utf8") as f:
    version = re.search(r"__version__ = \'(.*?)\'", f.read()).group(1)

setuptools.setup(
    name="cloudperf",
    version=version,
    author="NAGY, Attila",
    author_email="nagy.attila@gmail.com",
    description="Relative performance index for cloud services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bra-fsn/cloudperf",
    packages=setuptools.find_packages(),
    scripts=['bin/cloudperf'],
    install_requires=['cachetools', 'click>=7.0', 'boto3>=1.9.61', 'pandas', 'requests',
                      'python-dateutil', 'paramiko', 'pytimeparse'],
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
