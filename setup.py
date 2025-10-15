"""Setup file for need_scanner."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="need_scanner",
    version="0.1.0",
    author="Your Name",
    description="Pipeline for collecting and analyzing user pain points",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/need_scanner",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "openai>=1.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "typer>=0.9.0",
        "loguru>=0.7.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "rapidfuzz>=3.0.0",
        "requests>=2.31.0",
        "tqdm>=4.65.0",
    ],
    extras_require={
        "faiss": ["faiss-cpu>=1.7.4"],
        "dashboard": ["streamlit>=1.28.0", "matplotlib>=3.7.0"],
    },
    entry_points={
        "console_scripts": [
            "need-scanner=need_scanner.cli:main",
        ],
    },
)
