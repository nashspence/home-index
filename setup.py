from setuptools import setup, find_packages

setup(
    name="home_index",
    version="1.0.0",
    description="A package for running the home-index server.",
    author="Nash Spence",
    author_email="nashspence@gmail.com",
    url="https://github.com/nashspence/home-index",
    packages=find_packages(where="packages")
    + find_packages(where="features/F4", include=["home_index_module*"]),
    package_dir={
        "": "packages",
        "home_index_module": "features/F4/home_index_module",
    },
    python_requires=">=3.8",
)
