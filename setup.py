from setuptools import setup, find_packages

setup(
    name="capsulelab",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "typer>=0.12.0",
        "rich>=13.7.0",
        "pyyaml>=6.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
    ],
    entry_points={
        "console_scripts": [
            "cap=cli.main:cli",
        ],
    },
    python_requires=">=3.11",
)
