from setuptools import setup, find_namespace_packages

setup(
    name="home_index",
    version="1.0.0",
    description="A package for running the home-index server.",
    author="Nash Spence",
    author_email="nashspence@gmail.com",
    url="https://github.com/nashspence/home-index",
    py_modules=["main"],
    packages=find_namespace_packages(
        where=".", include=["features*", "shared*"], exclude=["*.test*"]
    ),
    package_dir={"": "."},
    install_requires=[
        "apscheduler==3.11.0",
        "debugpy==1.8.14",
        "meilisearch-python-sdk==4.7.1",
        "python-magic==0.4.27",
        "xxhash==3.5.0",
        "sentence-transformers==4.1.0",
        "transformers==4.53.0",
    ],
    python_requires=">=3.8",
)
