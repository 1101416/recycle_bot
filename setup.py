from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ai-waste-classification-bot",
    version="1.0.0",
    author="AI Waste Classification Team",
    author_email="contact@example.com",
    description="AI-powered LINE Bot for waste classification and recycling guidance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/ai-waste-classification-bot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Communications :: Chat",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "docs": [
            "sphinx>=4.0",
            "sphinx-rtd-theme>=0.5",
        ],
    },
    entry_points={
        "console_scripts": [
            "waste-bot=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.md", "*.yml", "*.yaml", "*.json"],
    },
    keywords="ai, machine-learning, line-bot, waste-classification, recycling, environment, chatbot",
    project_urls={
        "Bug Reports": "https://github.com/your-username/ai-waste-classification-bot/issues",
        "Source": "https://github.com/your-username/ai-waste-classification-bot",
        "Documentation": "https://ai-waste-classification-bot.readthedocs.io/",
    },
)
