from setuptools import setup

setup(
    name="home-index",
    version="1.0.0",
    description="A package for running the home-index server.",
    author="Nash Spence",
    author_email="nashspence@gmail.com",
    url="https://github.com/nashspence/home-index",
    py_modules=["run_server"],
    package_dir={"": "src"},
)
