# ndeploy
scripts to deploy N microservices (a "solution") to N PaaS, with a focus on development. 
Using a config file as input (yaml, json or toml) you define all shared services (redis, etc) 
and your microsrvices to be dployed.

It is basic and fragile for now. Start-up use.

# PaaS supported

  * dokku
  * openshift origin
  * heroku (under construction)
  
# Pre-requisites

You need the CLI versions of each PaaS already installed:

 * dokku : https://github.com/dokku/dokku
 
  * redis plugin: https://github.com/dokku/dokku-redis
  * postgres single container plugin: https://github.com/Flink/dokku-psql-single-container
  * rabbitmq plugin: https://github.com/dokku/dokku-rabbitmq
  * mongo plugin: https://github.com/dokku/dokku-mongo
   
 * oc in the case of openshift origin (see https://blog.openshift.com/using-openshift-3-on-your-local-environment/
)
 
You need the PaaS already installed. You probably want to start with them under Vagrant on your PC. For each one of them, you want the plugins installed (PostgreSQL, RabbitMQ, etc).

# How to install

 * pip3 install git+https://github.com/sglebs/ndeploy

# How to configure your project

You need to build a config file describing your solution. It can be yaml, json or toml.
This file can be templated, with values passed in at the command-line.

Here is a simplified solution file in .yaml format for a real deploy based on 2 microservices
in python which use celery, redis and postgres. For the live deploy, an existing AMAZON RDS 
database is used, whereas for dev deploys a new one is created on-the-fly (PaaS add-on).

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
      APP_NAME: "{{ appname }}"
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
      NEW_RELIC_APP_NAME: "{{ appname }}"
      NEW_RELIC_LOG_LEVEL: "info"
      NEW_RELIC_LOG: "stdout"
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
      NEW_RELIC_APP_NAME: "{{ appname }}"
      NEW_RELIC_LOG_LEVEL: "info"
      NEW_RELIC_LOG: "stdout"
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

```
ndeploy --deployhost=dokku.me /my/solution/ndeploy.toml
```
In the case of openshift, you may have exposed URLs using a different hostname. In these cases, use exposehost:
```
ndeploy deployhost=10.2.2.2 exposehost=my.domain.com /my/solution/ndeploy.toml
```
You may want to "ifdef" dev/staging/live. This can be done using jinja2 syntax in the .toml file. Example:
```
{% if scenario|string() == "debug"%}
...
{% endif %}
```
Obviously, for this to work you need to pass scenario=debug to ndeploy:
```
ndeploy --deployhost=dokku-vagrant.sglebs.com --scenario=debug /my/solution/ndeploy.toml
```
If you need to template based on the target PaaS ("cloud" parameter, which can be passed in) or the deployhost, it can also be done, like this:
```
{% if system|string() == "dokku" or deployhost|string() == "openshift.sglebs.com"%}
{% endif %}
```







