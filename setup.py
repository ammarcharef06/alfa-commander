# ============================================================
# Alfa Commander - Setup Script
# ============================================================

from setuptools import setup, find_packages
from pathlib import Path

README = Path(__file__).parent / "README.md"
long_desc = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="alfa-commander",
    version="1.0.0",
    description="منصة اختبار اختراق لاسلكي متكاملة لمحولات Alfa",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    author="Alfa Commander Project",
    license="MIT",
    packages=find_packages(exclude=["tests", "docs"]),
    python_requires=">=3.11",
    install_requires=[
        "PyQt6>=6.6",
        "scapy>=2.5",
        "PyYAML>=6.0",
        "aiosqlite>=0.19",
        "mac-vendor-lookup>=0.1.12",
        "psutil>=5.9",
        "rich>=13.0",
    ],
    entry_points={
        "console_scripts": [
            "alfa-commander=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "app": [
            "data/templates/*.html",
            "gui/resources/**/*",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security",
    ],
)
