# AgentForge Clinical Co-Pilot

This repository is a fork of [OpenEMR](https://github.com/openemr/openemr) with added planning documentation and a separate Clinical Co-Pilot scaffold under `copilot/`. The Co-Pilot is a standalone Next.js + FastAPI application that delegates authentication to OpenEMR via SMART-on-FHIR/OAuth2 and consumes patient data through OpenEMR's FHIR API.

## Deployed Application

| Environment | URL |
|---|---|
| OpenEMR fork (Railway) | _pending — recorded after first deploy_ |
| Local OpenEMR | `http://localhost:8300/` (see [DOCKER_README.md](DOCKER_README.md)) |
| Local Co-Pilot API | `http://127.0.0.1:8001/` |
| Local Co-Pilot Web | `http://127.0.0.1:3001/` |

## Project Documents

| Document | Purpose |
|---|---|
| [PRESEARCH.md](PRESEARCH.md) | Pre-code planning, constraints, and discovery notes |
| [AUDIT.md](AUDIT.md) | Security, performance, architecture, data quality, and compliance audit of the OpenEMR fork |
| [USERS.md](USERS.md) | Target user, workflow, and use cases ([USER.md](USER.md) is a compatibility pointer) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Standalone agent architecture, verification strategy, tradeoffs |
| [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) | Local and Railway deployment plan |
| [DEMO_PLAN.md](DEMO_PLAN.md) | 3-5 minute demo script |
| [EVAL_PLAN.md](EVAL_PLAN.md) | Deterministic eval plan and fixtures |
| [MVP_AUTH_SCOPE.md](MVP_AUTH_SCOPE.md) | MVP-night auth scope and explicit production-auth exclusions |
| [MVP_STATUS.md](MVP_STATUS.md) | Live build status |
| [OPENEMR_VERSION_PIN.md](OPENEMR_VERSION_PIN.md) | OpenEMR version and commit verified for planning |
| [eli5.md](eli5.md) | OpenEMR codebase orientation |

## Quickstart

### Local OpenEMR

```bash
cd docker/development-easy
docker compose up --detach --wait
```

Login: `admin` / `pass` at `http://localhost:8300/`.

### Local Co-Pilot

```bash
cd copilot/api
python -m venv .venv && . .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8001
```

```bash
cd copilot/web
npm install
npm run dev -- --port 3001
```

### Railway deploy of the OpenEMR fork

This repository ships with a Railway-ready [`Dockerfile`](Dockerfile), [`railway.toml`](railway.toml), and [`.dockerignore`](.dockerignore). The Dockerfile inherits the official `openemr/openemr:flex` image and identifies this build as the AgentForge fork.

End-to-end deploy from a clean machine:

```bash
npm install -g @railway/cli
railway login
railway init                          # create a new project linked to this repo
railway add --database mariadb        # provision managed MariaDB
railway link --service openemr        # or accept the prompt
# Set OpenEMR env vars (see DEPLOYMENT_RUNBOOK.md for the full list)
railway variables --set "MYSQL_HOST=${{MariaDB.MARIADB_PRIVATE_HOST}}" \
                  --set "MYSQL_ROOT_PASS=${{MariaDB.MARIADB_ROOT_PASSWORD}}" \
                  --set "MYSQL_USER=openemr" \
                  --set "MYSQL_PASS=$(openssl rand -hex 24)" \
                  --set "OE_USER=admin" \
                  --set "OE_PASS=$(openssl rand -hex 24)"
railway up                            # build and deploy from this Dockerfile
railway domain                        # generate a public URL
```

The first boot runs OpenEMR's `setup.php` against the empty MariaDB and takes 2-3 minutes. The readiness endpoint is `/meta/health/readyz` (HTTPS).

## License

This fork preserves OpenEMR's [GNU GPL v3](LICENSE) license. New files added by the AgentForge work are released under the same terms.

## Upstream OpenEMR

The remainder of this README is unchanged from the upstream OpenEMR project.

---

[![Syntax Status](https://github.com/openemr/openemr/actions/workflows/syntax.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/syntax.yml)
[![Styling Status](https://github.com/openemr/openemr/actions/workflows/styling.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/styling.yml)
[![Testing Status](https://github.com/openemr/openemr/actions/workflows/test.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/test.yml)
[![JS Unit Testing Status](https://github.com/openemr/openemr/actions/workflows/js-test.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/js-test.yml)
[![PHPStan](https://github.com/openemr/openemr/actions/workflows/phpstan.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/phpstan.yml)
[![Rector](https://github.com/openemr/openemr/actions/workflows/rector.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/rector.yml)
[![ShellCheck](https://github.com/openemr/openemr/actions/workflows/shellcheck.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/shellcheck.yml)
[![Docker Compose Linting](https://github.com/openemr/openemr/actions/workflows/docker-compose-lint.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/docker-compose-lint.yml)
[![Dockerfile Linting](https://github.com/openemr/openemr/actions/workflows/hadolint.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/hadolint.yml)
[![Isolated Tests](https://github.com/openemr/openemr/actions/workflows/isolated-tests.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/isolated-tests.yml)
[![Inferno Certification Test](https://github.com/openemr/openemr/actions/workflows/inferno-test.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/inferno-test.yml)
[![Composer Checks](https://github.com/openemr/openemr/actions/workflows/composer.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/composer.yml)
[![Composer Require Checker](https://github.com/openemr/openemr/actions/workflows/composer-require-checker.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/composer-require-checker.yml)
[![API Docs Freshness Checks](https://github.com/openemr/openemr/actions/workflows/api-docs.yml/badge.svg)](https://github.com/openemr/openemr/actions/workflows/api-docs.yml)
[![codecov](https://codecov.io/gh/openemr/openemr/graph/badge.svg?token=7Eu3U1Ozdq)](https://codecov.io/gh/openemr/openemr)

[![Backers on Open Collective](https://opencollective.com/openemr/backers/badge.svg)](#backers) [![Sponsors on Open Collective](https://opencollective.com/openemr/sponsors/badge.svg)](#sponsors)

# OpenEMR

[OpenEMR](https://open-emr.org) is a Free and Open Source electronic health records and medical practice management application. It features fully integrated electronic health records, practice management, scheduling, electronic billing, internationalization, free support, a vibrant community, and a whole lot more. It runs on Windows, Linux, Mac OS X, and many other platforms.

### Contributing

OpenEMR is a leader in healthcare open source software and comprises a large and diverse community of software developers, medical providers and educators with a very healthy mix of both volunteers and professionals. [Join us and learn how to start contributing today!](https://open-emr.org/wiki/index.php/FAQ#How_do_I_begin_to_volunteer_for_the_OpenEMR_project.3F)

> Already comfortable with git? Check out [CONTRIBUTING.md](CONTRIBUTING.md) for quick setup instructions and requirements for contributing to OpenEMR by resolving a bug or adding an awesome feature 😊.

### Support

Community and Professional support can be found [here](https://open-emr.org/wiki/index.php/OpenEMR_Support_Guide).

Extensive documentation and forums can be found on the [OpenEMR website](https://open-emr.org) that can help you to become more familiar about the project 📖.

### Reporting Issues and Bugs

Report these on the [Issue Tracker](https://github.com/openemr/openemr/issues). If you are unsure if it is an issue/bug, then always feel free to use the [Forum](https://community.open-emr.org/) and [Chat](https://www.open-emr.org/chat/) to discuss about the issue 🪲.

### Reporting Security Vulnerabilities

Check out [SECURITY.md](.github/SECURITY.md)

### API

Check out [API_README.md](API_README.md)

### Docker

Check out [DOCKER_README.md](DOCKER_README.md)

### FHIR

Check out [FHIR_README.md](FHIR_README.md)

### For Developers

If using OpenEMR directly from the code repository, then the following commands will build OpenEMR (Node.js version 24.* is required) :

```shell
composer install --no-dev
npm install
npm run build
composer dump-autoload -o
```

### Contributors

This project exists thanks to all the people who have contributed. [[Contribute]](CONTRIBUTING.md).
<a href="https://github.com/openemr/openemr/graphs/contributors"><img src="https://opencollective.com/openemr/contributors.svg?width=890" /></a>


### Sponsors

Thanks to our [ONC Certification Major Sponsors](https://www.open-emr.org/wiki/index.php/OpenEMR_Certification_Stage_III_Meaningful_Use#Major_sponsors)!


### License

[GNU GPL](LICENSE)
