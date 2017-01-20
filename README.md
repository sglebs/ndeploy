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

Here is a simplified solution file in .toml format for a real deploy based on 2 microservices
in python which use celery, redis and postgres. For the live deploy, an existing AMAZON RDS 
database is used, whereas for dev deploys a new one is created on-the-fly (PaaS add-on).

```
# Sample Deployment Descriptor, Templated by jinja2

[apps]
    [apps.core-{{ scenario }}]
    git = "git@bitbucket.org:zzz/core-server.git"
    branch = "master"
    services_used = ["redis-for-core-server", "pg-for-core-server"]
    domains = [
        #here you declare all the domains that the core-server can respond to
        {% if scenario|string() == "live" %}
        "v1.{{scenario}}.core.zzz.com",
        "get.v1.{{scenario}}.core.zzz.com",
        "v1.{{scenario}}.core.yyy.com",
        "get.v1.{{scenario}}.core.yyy.com",
        {% endif %}
        "{{scenario}}.core.zzz.com",
        "get.{{scenario}}.core.zzz.com",
        "{{scenario}}.core.yyy.com",
        "get.{{scenario}}.core.yyy.com"
    ]
    [apps.core-{{ scenario }}.paas_tweaks]
      dokku-docker-options =  ["run:-m 128m"]
      openshift-template =  "python:2.7~{repofullpath} --name={appname}{suffixfromlabel} -l app={appname}{suffixfromlabel} -e PORT=8080 -e PROCFILE_TARGET={procfilelabel}"
    [apps.core-{{ scenario }}.envs]
    {% if system|string() == "openshift" %}
    EXEC_CMD="gunicorn -c gunicorn_config.py -w $WEB_WORKER_COUNT -k gevent --threads 50 --worker-connections $GUNICORN_WORKER_CONNECTIONS --timeout 29 --keep-alive 1 --backlog $GUNICORN_BACKLOG --log-syslog --log-syslog-prefix GUNICORN --log-level $LOGLEVEL --log-file=- --access-logfile=- restserver:application"
    PORT=8080
    {% endif %}
    {% if scenario|string() == "dev" %}
    AD_MAX_DAYS_WITH_AD=9999
    AD_MAX_HOURS_NO_AD_FEMALE=1
    AD_MAX_HOURS_NO_AD_MALE=2
    AD_TIMEOUT_IN_SECONDS=10
    {% endif %}
    {% if scenario|string() == "staging" %}
    AD_MAX_DAYS_WITH_AD=9999
    AD_MAX_HOURS_NO_AD_FEMALE=1
    AD_MAX_HOURS_NO_AD_MALE=2
    AD_TIMEOUT_IN_SECONDS=10
    {% endif %}
    {% if scenario|string() == "live" %}
    AD_MAX_DAYS_WITH_AD=365
    AD_MAX_HOURS_NO_AD_FEMALE=24
    AD_MAX_HOURS_NO_AD_MALE=6
    {% endif %}
    APP_NAME="{{ appname }}"
    BASE_PATH="/api"
    BASE_URL="{{ exposehost }}"
    CELERY_ALWAYS_EAGER=0
    CELERY_BROKER_URL="%REDIS_URL/14"
    DISABLE_GEVENT=0
    ENABLE_STUNNEL_AMAZON_RDS_FIX=1
    GUNICORN_BACKLOG=2048
    GUNICORN_WORKER_CONNECTIONS=750
    {% if scenario|string() == "live" %}
    HEROKU_API_KEY="gjfhjffghfghfhjgfhj"
    {% endif %}
    LANG="pt_BR.UTF-8"
    LOGLEVEL="DEBUG"
    NEW_RELIC_APP_NAME="{{ appname }}"
    NEW_RELIC_LOG_LEVEL="info"
    NEW_RELIC_LOG="stdout"
    NEW_RELIC_SSL="false"
    NOAUTH_TOKEN="Q76787868jhghjgjhg"
    {% if scenario|string() == "dev" %}
    POSTGRES_READ="POSTGRESQL_URL"
    POSTGRES_WRITE="POSTGRESQL_URL"
    POSTGRES_SNAP001="POSTGRESQL_URL"
    POSTGRES_SNAP_FOR_SCRIPTS="POSTGRESQL_URL"
    {% endif %}
    {% if scenario|string() == "staging" %}
    AMAZON_RDS_URL="postgres://vvvvvv:xxxx@aaaaa.zzz.us-east-1.rds.amazonaws.com:5432/zzzstaging"
    POSTGRES_READ="AMAZON_RDS_URL"
    POSTGRES_WRITE="AMAZON_RDS_URL"
    POSTGRES_SNAP001="AMAZON_RDS_URL"
    POSTGRES_SNAP_FOR_SCRIPTS="AMAZON_RDS_URL"
    {% endif %}
    {% if scenario|string() == "live" %}
    AMAZON_RDS_URL="postgres://vvvvvv:xxxx@aaaaa.zzz.us-east-1.rds.amazonaws.com:5432/zzzlive"
    POSTGRES_READ="AMAZON_RDS_URL"
    POSTGRES_WRITE="AMAZON_RDS_URL"
    POSTGRES_SNAP001="AMAZON_RDS_URL"
    POSTGRES_SNAP_FOR_SCRIPTS="AMAZON_RDS_URL"
    {% endif %}
    REDIS_1="REDIS_URL"
    {% if scenario|string() == "dev" %}
    S3_SERVER_PROFILEPICTURE_BUCKET="dev.profilepicture.zzz.com"
    S3_SERVER_PROFILEPICTURE_ID="sfafadfdafdfa"
    S3_SERVER_PROFILEPICTURE_SECRET="5463456hdfghdfghgfhd"
    SQLALCHEMY_LOGLEVEL="WARNING"
    {% endif %}
    {% if scenario|string() == "staging" %}
    S3_SERVER_PROFILEPICTURE_BUCKET="staging.profilepicture.zzz.com"
    S3_SERVER_PROFILEPICTURE_ID="bvcxbvxcbxvcbvc"
    S3_SERVER_PROFILEPICTURE_SECRET="xcbvxcvbcvxbxcvbxvcbcvbvx"
    SQLALCHEMY_LOGLEVEL="WARNING"
    {% endif %}
    {% if scenario|string() == "live" %}
    S3_SERVER_PROFILEPICTURE_BUCKET="live.profilepicture.zzz.com"
    S3_SERVER_PROFILEPICTURE_ID="dfgdfgdfgfdgffg"
    S3_SERVER_PROFILEPICTURE_SECRET="fdgsdfgdsfgdsfgdfsgfdgsd"
    SQLALCHEMY_LOGLEVEL="ERROR"
    {% endif %}
    VERSION=1
    {% if scenario|string() == "dev" %}
    WEB_WORKER_COUNT=1
    {% endif %}
    {% if scenario|string() == "staging" %}
    WEB_WORKER_COUNT=2
    {% endif %}
    {% if scenario|string() == "live" %}
    WEB_WORKER_COUNT=4
    {% endif %}

    [apps.messenger-{{ scenario }}]
    git = "git@bitbucket.org:zzz/messenger-server.git"
    branch = "master"
    services_used = ["redis-for-messenger-server", "redis-for-core-server", "pg-for-messenger-server"]
    domains = [
        #here you declare all the domains that the messenger-server can respond to
        {% if scenario|string() == "live" %}
        "v1.{{scenario}}.messenger.zzz.com",
        "get.v1.{{scenario}}.messenger.zzz.com",
        "v1.{{scenario}}.messenger.yyy.com",
        "get.v1.{{scenario}}.messenger.yyy.com",
        {% endif %}
        "{{scenario}}.messenger.yyy.com",
        "{{scenario}}.messenger.yyy.com"
    ]
    [apps.messenger-{{ scenario }}.paas_tweaks]
      dokku-docker-options =  ["run:-m 128m"]
      openshift-template =  "python:2.7~{repofullpath} --name={appname}{suffixfromlabel} -l app={appname}{suffixfromlabel} -e PORT=8080 -e PROCFILE_TARGET={procfilelabel}"
    [apps.messenger-{{ scenario }}.envs]
    {% if system|string() == "openshift" %}
    EXEC_CMD="gunicorn -c gunicorn_config.py -w $WEB_WORKER_COUNT -k gevent --threads 50 --worker-connections $GUNICORN_WORKER_CONNECTIONS --timeout 29 --keep-alive 1 --backlog $GUNICORN_BACKLOG --log-syslog --log-syslog-prefix GUNICORN --log-level $LOGLEVEL --log-file=- --access-logfile=- restserver:application"
    PORT=8080
    {% endif %}
    ANDROID_API_KEY="dfgsdfgsdfgdfgf"
    ANDROID_SENDER_ID="dfgsdfgdfgdfgsfdg"
    DATASTORE="datastore.s3pure"
    ENGINE_CALLBACKS_USE_THREADS="True"
    GENERICCOUNTERS_REDIS="%REDIS_FOR_CORE_SERVER_URL/11"
    LANG="pt_BR.UTF-8"
    LOGLEVEL="DEBUG"
    {% if scenario|string() == "dev" %}
    MESSAGE_TTL=3
    {% endif %}
    {% if scenario|string() == "staging" %}
    MESSAGE_TTL=30
    {% endif %}
    {% if scenario|string() == "live" %}
    MESSAGE_TTL=180
    {% endif %}
    MESSENGER_PASSWORD_MD5="676547645gfhhfgjfhjfhgjhgjhgfj"
    MYCELERY_BROKER_URL="%REDIS_URL/13"
    AUTH_CHECK_URL="%CORE_SERVER_URL/stealth"
    NOTIFICATION_PROFILE_URL="%CORE_SERVER_URL/fullnotifications"
    NEW_RELIC_APP_NAME="{{ appname }}"
    NEW_RELIC_LOG_LEVEL="info"
    NEW_RELIC_LOG="stdout"
    NEW_RELIC_SSL="false"
    NOTIFICATION_PROFILE_PATH="cert/zzzz-prod.pem:cert/zzz-prod.pem"
    PROFILE_REDIS_CACHE_URL="%REDIS_URL/1"
    PUSHPROFILE_CACHE_TTL=15
    PUSHPROFILE_REDIS_CACHE_URL="%REDIS_URL/2"
    PUSH_USE_THREADS="False"
    REDIS_TIMEOUT=0.8
    {% if scenario|string() == "dev" %}
    S3_ACCESS_KEY="dfgfdgfdgfdg"
    S3_BUCKET="std.staging.messenger.zzz.com"
    S3_SECRET_KEY="563456546fghfghhggfh"
    S3_TOP_DIR="s"
    {% endif %}
    {% if scenario|string() == "staging" %}
    S3_ACCESS_KEY="fghdfghgdfhgfhghhgfhgfd"
    S3_BUCKET="std.staging.messenger.aaaa.com"
    S3_SECRET_KEY="fdhgsdhgshgfhdhgfhdgfhgdhg"
    S3_TOP_DIR="s"
    {% endif %}
    {% if scenario|string() == "live" %}
    S3_ACCESS_KEY="vvdnbvcncbvnbvbn"
    S3_BUCKET="std.live.messenger.zzz.com"
    S3_SECRET_KEY="fghgdfh45674676747645"
    S3_TOP_DIR="L"
    {% endif %}
    S3_REDIS_CACHE_URL="%REDIS_URL/3"
    S3_TIMEOUT=0.4
    S3_ASYNC_WRITES="True"
    S3_USE_HTTPS="False"
    S3_USE_THREADS="True"
    {% if scenario|string() == "dev" %}
    WEB_WORKER_COUNT=1
    {% endif %}
    {% if scenario|string() == "staging" %}
    WEB_WORKER_COUNT=2
    {% endif %}
    {% if scenario|string() == "live" %}
    WEB_WORKER_COUNT=4
    {% endif %}
[shared_services]
  {% if scenario|string() == "dev" or scenario|string() == "staging" %} # do not create redis for live, used manually created one
  redis = ["redis-for-core-server", "redis-for-messenger-server"]
  {% endif %}
  {% if scenario|string() == "dev" %} # do not create postgres for live or staging, used manually created ones
  postgres = ["pg-for-core-server", "pg-for-messenger-server"]
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







