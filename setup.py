# -*- encoding:utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='abupy',
    version='0.4.0',
    description='ABU量化交易系统 - A股策略优化版',
    author='阿布',
    packages=find_packages(exclude=['tests', 'ipython', 'python',
                                     'abupy_lecture', 'abupy_ui']),
    python_requires='>=3.8,<3.10',
    install_requires=[
        'numpy==1.19.5',
        'pandas==0.25.3',
        'scikit-learn>=1.0,<1.1',
        'scipy>=1.7,<1.8',
        'matplotlib>=3.5,<3.6',
        'seaborn>=0.12,<0.13',
        'requests>=2.28',
        'statsmodels>=0.13,<0.14',
        'bokeh>=2.4,<2.5',
        'toolz>=1.0',
        'flask>=2.3',
        'flask-cors>=4.0',
    ],
    entry_points={
        'console_scripts': [
            'abu-server=webapp.app:main',
        ],
    },
    include_package_data=True,
    package_data={
        'abupy': ['RomDataBu/*.zip', 'RomDataBu/*.csv',
                   'RomDataBu/csv/*.csv'],
    },
)
