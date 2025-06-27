from setuptools import setup, find_namespace_packages

setup(
    name="home_index",
    version="1.0.0",
    description="A package for running the home-index server.",
    author="Nash Spence",
    author_email="nashspence@gmail.com",
    url="https://github.com/nashspence/home-index",
    packages=find_namespace_packages(where="packages")
    + find_namespace_packages(where=".", include=["features*"], exclude=["*.test*"]),
    package_dir={
        "": ".",
        "home_index": "packages/home_index",
    },
    python_requires=">=3.8",
)
