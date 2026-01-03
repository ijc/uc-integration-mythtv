# MythTV integration for Remote Two

A [MythTV][] integration for the [Unfolded Circle][] Remote Two
allowing control of a MythTV frontend via the [MythTV Frontend
Service][].

[Unfolded Circle]: https://www.unfoldedcircle.com/
[MythTV]: https://www.mythtv.org/
[MythTV Frontend Service]: https://www.mythtv.org/wiki/Frontend_Service

## Installation

### Setup

Setup a Python venv:

```console
$ make venv # or venv-test
$ source venv/bin/activate
```

Ensure you have the MythTV Python bindings too. There are not listed
in `requirements.txt`, they should be available wherever you got your
MythTV (packages or installed from source).

### Configuration

The integration is configured via environment variables:

| Variable name      | Default                     |
| ------------------ | --------------------------- |
| `INTG_MYTHTV_HOST` | `localhost`                 |
| `INTG_MYTHTV_NAME` | Inherits `INTG_MYTHTV_HOST` |
| `INTG_MYTHTV_PORT` | `6547`                      |

See also the [environment variables][] defined in the [Python
integration library][] to control certain runtime features like
listening interface.

[environment variables]: https://github.com/unfoldedcircle/integration-python-library#environment-variables
[Python integration library]: https://github.com/unfoldedcircle/integration-python-library

### Run

```shell
$ ./venv/bin/python3 ./intg-mythtv/driver.py
```

### Systemd

Copy [`integration-mythtv.service`][] to
`/etc/systemd/system/integration-mythtv.service` and edit to suit your
environment and where you have installed the integration. Then:

```console
# systemctl enable integration-mythtv.service
# systemctl start integration-mythtv.service
```

[`integration-mythtv.service`]: ./integration-mythtv.service

### Docker

```shell
$ docker build -t intg-mythtv . 
$ docker run -it -p 9090:9090 --rm intg-mythtv
```

or with compose:

```shell
$ docker compose build
$ docker compose up
```

### Add to Remote

Assuming locally running [core simulator][]:

```console
$ uuid=$(uuidgen)
$ curl --location 'http://localhost:8080/api/intg/drivers' \
   --user "web-configurator:1234" \
   --json '
{
 "driver_id": "$uuid",
  "name": {
    "en": "mythtv"
  },
  "driver_url": "ws://localhost:9090/ws",
  "icon": "uc:integration",
  "version": "0.1.0",
  "enabled": true
}'
```

Adjust to use your actual remote URL, PIN and the hostname of your
MythTV frontend.

[core simulator]: https://github.com/unfoldedcircle/core-simulator/
