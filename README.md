# ndeploy
=========

Building and deploying apps that follow [12factor](http://www.12factor.net) is fun but can be tedious to properly configure - all those environment variables! 
Also, when you have to deal with DEV, STAGING, LIVE the setting of these env vars can be a pain. If you want to be PaaS-portable, things get worse,
as each PaaS has its own CLI and Web UI - deploying and tweaking the vars can be very time consuming.

ndeploy helps you deploy a set of ("n") apps/services/microservices (we call this set a "solution", borrowing Microsoft's Visual Studio terminology) 
to various PaaS ("n"), with a focus on developer productivity. 

Using a config file as input (yaml, json or toml) you define all shared services (redis, postgres, etc)  and your apps/services/microservices to be deployed.

ndeploy is basic and fragile for now, but quite useful and time saver (at least for us!).

# PaaS support
==============

PaaS support is pluggable via Python modules. Example: ```--cloud=foo``` will work if ndeploy can find/load a "foo" Python module (foo.py) dynamically.
We ship a few, prefixed with "nd" (nd stands for ndeploy) to avoid name collisions with the ones you may wish to provide. Currently
we have support for:

  * dokku (```--cloud=nd.dokku``` for our built-in implementation - see sources in nd/dokku.py)
  * openshift origin (```--cloud=nd.openshift``` for our built-in implementation - see sources in nd/openshift.py)
  * heroku (```--cloud=nd.heroku``` for our built-in implementation - see sources in nd/heroku.py)
  * HP Stackato (```--cloud=nd.stackato``` for our built-in implementation - see sources in nd/stackato.py)
  
Planned:
  * IBM BlueMix
  * Microsoft Azure
  * Google/docker
  * AWS / docker
  * tsuru
  * ...
  
# Pre-requisites
================

You need the CLI versions of each PaaS already installed:

 * dokku : https://github.com/dokku/dokku
  * redis plugin: https://github.com/dokku/dokku-redis (if you plan to use Redis)
  * postgres single container plugin: https://github.com/Flink/dokku-psql-single-container (if you plan to use Postgres)
  * rabbitmq plugin: https://github.com/dokku/dokku-rabbitmq (if you plan to use RabbitMQ)
  * mongo plugin: https://github.com/dokku/dokku-mongo (if you plan to use MongoDB)
   
 * oc if you plan to deploy to openshift origin (see https://blog.openshift.com/using-openshift-3-on-your-local-environment/ )
 
 * heroku if you plan to deploy to Heroku
 
 * stackato: http://downloads.stackato.com/client/v3.2.4/
 
You need the PaaS already installed. You probably want to start with them under Vagrant on your PC for development. 
For each one of them, you want the plugins already installed (PostgreSQL, RabbitMQ, etc).

# How to install ndeploy
========================

 * pip3 install git+https://github.com/sglebs/ndeploy

# How to configure your solution ("n" apps/services/microservices)
==================================================================

You need to build a config file describing your solution. It can be yaml, json or toml.
This file can be templated (we use jinja2 internally), with values passed in at the command-line.

Let's start with a simple project: 1 microservice with one database, described in yaml format:

```yaml
apps:
  - name: "gift-card-{{ scenario }}"
    git : "https://gitlab.foo.com/gift-card/gift-card.git"
    branch : "master"
    services_used:
      - "pg-for-gift-card"
    envs:
      WEB_CONCURRENCY: 4
shared_services:
  postgres:
    - "pg-for-gift-card"
````

The project above can be deployed against heroku for example: ```ndeploy deploy --cloud=nd.heroku --scenario=dev solution.yaml``` .
It can be undeployed like this:  ```ndeploy undeploy --cloud=nd.heroku --scenario=dev solution.yaml```

Note how the ```--scenario``` passed at command-line gets injected into the template yaml file, as ```{{ scenario }}``` (jinja2 notation).

Now a more elaborate solution in .yaml format for 2 microservices in python which use a celery each, 
a redis each (one is shared between the two) and one postgres each. 
For the live deploy, an existing AMAZON RDS database is used instead, whereas for dev deploys a new postgres is
created on-the-fly (PaaS add-on).

```yaml
apps:
  - name: "core-{{ scenario }}-{{ area }}"
    git : "git@bitbucket.org:fooon/core-server.git"
    branch : "master"
    services_used:
      - "redis-for-core-server"
      - "pg-for-core-server"
    domains:
      #here you declare all the domains that the core-server can respond to
      {% if scenario|string() == "live" %}
      - "v1.{{scenario}}.core.fooon.com"
      - "get.v1.{{scenario}}.core.fooon.com"
      - "v1.{{scenario}}.core.foomobile.com"
      - "get.v1.{{scenario}}.core.foomobile.com"
      {% endif %}
      - "{{scenario}}.core.fooon.com"
      - "get.{{scenario}}.core.fooon.com"
      - "{{scenario}}.core.foomobile.com"
      - "get.{{scenario}}.core.foomobile.com"
    paas_tweaks:
      dokku-docker-options:
        - "run:-m 128m"
      openshift-template: "python:2.7~{repofullpath} --name={appname}{suffixfromlabel} -l app={appname}{suffixfromlabel} -e PORT=8080 -e PROCFILE_TARGET={procfilelabel}"
    envs:
      {% if system|string() == "openshift" %}
      EXEC_CMD: "gunicorn -c gunicorn_config.py -w $WEB_WORKER_COUNT -k gevent --threads 50 --worker-connections $GUNICORN_WORKER_CONNECTIONS --timeout 29 --keep-alive 1 --backlog $GUNICORN_BACKLOG --log-syslog --log-syslog-prefix GUNICORN --log-level $LOGLEVEL --log-file=- --access-logfile=- restserver:application"
      PORT: 8080
      {% endif %}
      BUILDPACK_URL: "https://github.com/heroku/heroku-buildpack-python.git#v57"
      {% if scenario|string() == "dev" %}
      AD_MAX_DAYS_WITH_AD: 9999
      {% endif %}
      {% if scenario|string() == "staging" %}
      AD_MAX_DAYS_WITH_AD: 9999
      {% endif %}
      {% if scenario|string() == "live" %}
      AD_MAX_DAYS_WITH_AD: 365
      {% endif %}
      APP_NAME: "core-{{ scenario }}-{{ area }}"
      BASE_PATH: "/api"
      BASE_URL: "core-{{ scenario }}-{{ area }}.{{ exposehost }}"
      CELERY_ALWAYS_EAGER: 0
      MYCELERY_BROKER_URL: "%REDIS_URL/14"
      DISABLE_GEVENT: 0
      ENABLE_STUNNEL_AMAZON_RDS_FIX: 1
      GUNICORN_BACKLOG: 2048
      GUNICORN_WORKER_CONNECTIONS: 750
      {% if scenario|string() == "live" %}
      HEROKU_API_KEY: "sdfsdfsdfsd"
      {% endif %}
      LANG: "pt_BR.UTF-8"
      LOGLEVEL: "DEBUG"
      NEW_RELIC_APP_NAME: "core-{{ scenario }}-{{ area }}"
      NEW_RELIC_LOG_LEVEL: "info"
      NEW_RELIC_SSL: "false"
      NOAUTH_TOKEN: "QAi)asfasfsffdf)sadfasf.yXc"
      {% if scenario|string() == "dev" %}
      POSTGRES_READ: "DATABASE_URL"
      POSTGRES_WRITE: "DATABASE_URL"
      POSTGRES_SNAP001: "DATABASE_URL"
      POSTGRES_SNAP_FOR_SCRIPTS: "DATABASE_URL"
      {% endif %}
      {% if scenario|string() == "staging" %}
      AMAZON_RDS_URL: "postgres://vvv:eeee@dbm3medium.ffffffff.us-east-1.rds.amazonaws.com:5432/fooonstaging"
      POSTGRES_READ: "AMAZON_RDS_URL"
      POSTGRES_WRITE: "AMAZON_RDS_URL"
      POSTGRES_SNAP001: "AMAZON_RDS_URL"
      POSTGRES_SNAP_FOR_SCRIPTS: "AMAZON_RDS_URL"
      {% endif %}
      {% if scenario|string() == "live" %}
      AMAZON_RDS_URL: "postgres://vvv:eeee@dbm3medium.ffffffff.us-east-1.rds.amazonaws.com:5432/fooonlive"
      POSTGRES_READ: "AMAZON_RDS_URL"
      POSTGRES_WRITE: "AMAZON_RDS_URL"
      POSTGRES_SNAP001: "AMAZON_RDS_URL"
      POSTGRES_SNAP_FOR_SCRIPTS: "AMAZON_RDS_URL"
      {% endif %}
      REDIS_1: "REDIS_URL"
      {% if scenario|string() == "dev" %}
      S3_SERVER_PROFILEPICTURE_BUCKET: "staging.profilepicture.foomobile.com"
      S3_SERVER_PROFILEPICTURE_ID: "sdfsdfsfdsf"
      S3_SERVER_PROFILEPICTURE_SECRET: "sfsdfsdf/sfsdfdffd+sfsdfdfs/eorbL"
      SENDGRID_PASSWORD: "sfdfsdfsdfds"
      SENDGRID_USERNAME: "sdfsdffd@heroku.com"
      SQLALCHEMY_LOGLEVEL: "WARNING"
      {% endif %}
      {% if scenario|string() == "staging" %}
      S3_SERVER_PROFILEPICTURE_BUCKET: "staging.profilepicture.foomobile.com"
      S3_SERVER_PROFILEPICTURE_ID: "sfdfsdfsdfsdfsdf"
      S3_SERVER_PROFILEPICTURE_SECRET: "sfsdfdsf/gKH9fo+sfdsfsdfdfs/sfdfds"
      SENDGRID_PASSWORD: "sfsdfsdfdf"
      SENDGRID_USERNAME: "sfsdfddf@heroku.com"
      SQLALCHEMY_LOGLEVEL: "WARNING"
      {% endif %}
      {% if scenario|string() == "live" %}
      S3_SERVER_PROFILEPICTURE_BUCKET: "live.profilepicture.foomobile.com"
      S3_SERVER_PROFILEPICTURE_ID: "sfsdfsdfsdfdsfdsf"
      S3_SERVER_PROFILEPICTURE_SECRET: "sfsdfdsf/sdfsdf+sfsdfdsfdsfdfs"
      SENDGRID_PASSWORD: "sdfsdfsdfsdfdsf"
      SENDGRID_USERNAME: "sdfsdfsdfdsfdsf@heroku.com"
      SQLALCHEMY_LOGLEVEL: "ERROR"
      {% endif %}
      TIGER_MAX_ONLINE_VICTIMS: 50
      TIGER_MAX_STALING_VICTIMS: 50
      VERSION: 1
      {% if scenario|string() == "dev" %}
      WEB_WORKER_COUNT: 1
      {% endif %}
      {% if scenario|string() == "staging" %}
      WEB_WORKER_COUNT: 2
      {% endif %}
      {% if scenario|string() == "live" %}
      WEB_WORKER_COUNT: 4
      {% endif %}
  - name: "messenger-{{ scenario }}-{{ area }}"
    git: "git@bitbucket.org:fooon/messenger-server.git"
    branch: "master"
    services_used:
      - "redis-for-messenger-server"
      - "redis-for-core-server"
      - "pg-for-messenger-server"
    domains:
      #here you declare all the domains that the messenger-server can respond to
      {% if scenario|string() == "live" %}
      - "v1.{{scenario}}.messenger.fooon.com"
      - "get.v1.{{scenario}}.messenger.fooon.com"
      - "v1.{{scenario}}.messenger.foomobile.com"
      - "get.v1.{{scenario}}.messenger.foomobile.com"
      {% endif %}
      - "{{scenario}}.messenger.foomobile.com"
      - "{{scenario}}.messenger.fooon.com"
    paas_tweaks:
      dokku-docker-options:
        - "run:-m 128m"
      openshift-template: "python:2.7~{repofullpath} --name={appname}{suffixfromlabel} -l app={appname}{suffixfromlabel} -e PORT=8080 -e PROCFILE_TARGET={procfilelabel}"
    envs:
      {% if system|string() == "openshift" %}
      EXEC_CMD: "gunicorn -c gunicorn_config.py -w $WEB_WORKER_COUNT -k gevent --threads 50 --worker-connections $GUNICORN_WORKER_CONNECTIONS --timeout 29 --keep-alive 1 --backlog $GUNICORN_BACKLOG --log-syslog --log-syslog-prefix GUNICORN --log-level $LOGLEVEL --log-file=- --access-logfile=- restserver:application"
      PORT: 8080
      {% endif %}
      BUILDPACK_URL: "https://github.com/heroku/heroku-buildpack-python.git#v57"
      CORE_SERVER_URL: "http://core-{{ scenario }}-{{ area }}.{{ exposehost }}"
      ANDROID_API_KEY: "sfdsdfdsfsdfds"
      ANDROID_SENDER_ID: "sfdsdfdsfsdfdsfdsfsdfdsf"
      DATASTORE: "datastore.s3pure"
      ENGINE_CALLBACKS_USE_THREADS: "True"
      #Next: note that we need access to the Redis instance owned by the core-server. REDIS_FOR_CORE_SERVER_URL must be injected.
      GENERICCOUNTERS_REDIS: "%REDIS_FOR_CORE_SERVER_URL/11"
      LANG: "pt_BR.UTF-8"
      LOGLEVEL: "DEBUG"
      {% if scenario|string() == "dev" %}
      MESSAGE_TTL: 3
      {% endif %}
      {% if scenario|string() == "staging" %}
      MESSAGE_TTL: 3
      {% endif %}
      {% if scenario|string() == "live" %}
      MESSAGE_TTL: 180
      {% endif %}
      MYCELERY_BROKER_URL: "%REDIS_URL/13"
      foo_AUTH_CHECK_URL: "%CORE_SERVER_URL/api/ddddd/check/stealth"
      foo_NOTIFICATION_PROFILE_URL: "%CORE_SERVER_URL/api/wewewew/fullnotifications"
      NEW_RELIC_APP_NAME: "messenger-{{ scenario }}-{{ area }}"
      NEW_RELIC_LOG_LEVEL: "info"
      NEW_RELIC_SSL: "false"
      NOTIFICATION_PROFILE_PATH: "cert/foo-prod.pem:cert/fooPlus-prod.pem"
      PROFILE_REDIS_CACHE_URL: "%REDIS_URL/1"
      PUSHPROFILE_CACHE_TTL: 15
      PUSHPROFILE_REDIS_CACHE_URL: "%REDIS_URL/2"
      PUSH_USE_THREADS: "False"
      REDIS_TIMEOUT: 0.8
      {% if scenario|string() == "dev" %}
      S3_ACCESS_KEY: "qweqeqweqweqwe"
      S3_BUCKET: "std.staging.messenger.foomobile.com"
      S3_SECRET_KEY: "qeqweqwewqeqw/qewqweqwe"
      S3_TOP_DIR: "s"
      {% endif %}
      {% if scenario|string() == "staging" %}
      S3_ACCESS_KEY: "qweqweqwewqeqweqwe"
      S3_BUCKET: "std.staging.messenger.foomobile.com"
      S3_SECRET_KEY: "qeqweqwe/qeqwewq"
      S3_TOP_DIR: "s"
      {% endif %}
      {% if scenario|string() == "live" %}
      S3_ACCESS_KEY: "qeqweqweqweqweqwe"
      S3_BUCKET: "std.live.messenger.foomobile.com"
      S3_SECRET_KEY: "qeweqweqwe/qeqweqweqew+"
      S3_TOP_DIR: "L"
      {% endif %}
      S3_REDIS_CACHE_URL: "%REDIS_URL/3"
      S3_TIMEOUT: 0.4
      S3_ASYNC_WRITES: "True"
      S3_USE_HTTPS: "False"
      S3_USE_THREADS: "True"
      {% if scenario|string() == "dev" %}
      WEB_WORKER_COUNT: 1
      {% endif %}
      {% if scenario|string() == "staging" %}
      WEB_WORKER_COUNT: 2
      {% endif %}
      {% if scenario|string() == "live" %}
      WEB_WORKER_COUNT: 4
      {% endif %}
shared_services:
  {% if scenario|string() == "dev" or scenario|string() == "staging" %} # do not create redis for live, use manually created ones (OpenRedis, see env vars)
  redis:
    - "redis-for-core-server"
    - "redis-for-messenger-server"
  {% endif %}
  {% if scenario|string() == "dev" %} # do not create postgres for live or staging, use manually created ones (RDS - see env vars)
  postgres:
    - "pg-for-core-server"
    - "pg-for-messenger-server"
  {% endif %}



```

# How to Deploy
===============

```
ndeploy --deployhost=dokku.me --cfgfile=/my/solution/ndeploy.toml deploy
```
In the case of openshift, you may have exposed URLs using a different hostname. In these cases, use exposehost:
```
ndeploy --deployhost=10.2.2.2 --exposehost=my.domain.com --cloud=nd.openshift --cfgfile=/my/solution/ndeploy.toml deploy
```
You may want to "ifdef" dev/staging/live in your configuration file. This can be done using jinja2 syntax:
```
{% if scenario|string() == "debug"%}
...
{% endif %}
```
Obviously, for this to work you need to pass scenario=debug to ndeploy:
```
ndeploy --deployhost=dokku-vagrant.sglebs.com --cloud=nd.dokku --scenario=debug --cfgfile=/my/solution/ndeploy.toml deploy
```
If you need to template based on the target PaaS ("cloud" parameter, which can be passed in) or the deployhost, it can also be done, like this:
```
{% if cloud|string() == "nd.dokku" or deployhost|string() == "openshift.sglebs.com"%}
{% endif %}
```

# Related Projects
=================

   * dpl: https://github.com/travis-ci/dpl 
   * https://github.com/nexxera/ndeploy is a descendant of "our" ndeploy. It adds support to build and promote docker images in a build pipeline, which saves CPU resources since you don't need a full clean build every time.
   
# Special Thanks
==============
We would like to thank [Nexxera](http://www.nexxera.com) for their partial support of the development of ndeploy.  




