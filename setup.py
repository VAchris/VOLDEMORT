from distutils.core import setup

setup(
    name='VOLDEMORT',
    version='0.2',
    packages=['vdm','vdm.copies'],
    package_data={'vdm': ['resources/GOLD.zip', 'resources/*.csv']},
    url="https://github.com/OSEHR/VOLDEMORT",
    license='Apache License (2.0)',
    description="VOLDEMORT - VistA Comparison Tool",
    # scripts=['vdmrun'],
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators'
    ]
)
