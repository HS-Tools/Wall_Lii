from setuptools import find_packages, setup

setup(
    name="hs-bg-leaderboards",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "requests-futures",
        "boto3",
        # add other dependencies here
    ],
)
