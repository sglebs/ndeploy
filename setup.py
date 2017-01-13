from setuptools import setup

setup(
    name='ndeploy',
    version='0.1',
    description='Source code KALOI (using Understand).',
    url='https://github.com/sglebs/ndeploy',
    author='Marcio Marchini',
    author_email='marcio@betterdeveloper.net',
    install_requires=[
        'gitpython',
        'Jinja2',
        'timeout-decorator',
        'toml',
        'click'
    ],
    py_modules=['ndeploy'],
    entry_points='''
        [console_scripts]
        ndeploy=ndeploy:cli
    ''',
)