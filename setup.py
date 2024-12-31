from setuptools import setup, find_packages

setup(
    name="home-index",
    version="1.0.0",
    description="A package for running the home-index server.",
    author="Nash Spence",
    author_email="nashspence@gmail.com",
    url="https://github.com/nashspence/home-index",
    packages=find_packages(where="packages"),
    package_dir={"": "packages"},
)
