from setuptools import setup, find_packages

setup(
    name='ndeploy',
    version='0.7.0',
    packages=find_packages(),
    description='Deploys n microservices to n PaaS',
    url='https://github.com/sglebs/ndeploy',
    author='Marcio Marchini',
    author_email='marcio@betterdeveloper.net',
    install_requires=[
        'gitpython',
        'Jinja2',
        'timeout-decorator',
        'toml',
        'pyyaml',
        'click',
        'requests',
        'requests-file'
    ],
    py_modules=['ndeploy'],
    entry_points='''
        [console_scripts]
        ndeploy=ndeploy:cli
    ''',
)