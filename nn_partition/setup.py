from setuptools import setup, find_packages

setup(
    name="nn_partition",
    version="0.0.1",
    install_requires=[
        "torch",
        "alphashape",
        "sklearn",
        "scipy",
        "matplotlib",
        "imageio",
        "keras",
        "pypoman",
        "tqdm",
        "pyclipper",
        "pygifsicle",
    ],
    packages=find_packages(),
)
