# AgentForge Clinical Co-Pilot — OpenEMR fork deployment image.
#
# This Dockerfile builds the deployable OpenEMR runtime for the fork.
# OpenEMR's PHP/Apache server source is identical to upstream at the
# pinned flex tag; this fork adds planning docs and a separate Co-Pilot
# scaffold under copilot/ that runs as its own services (not part of
# this image). The fork is identified inside the deployed image via a
# small agentforge/ marker directory served by OpenEMR's webroot.
#
# Required runtime environment (set via Railway variables / docker -e):
#   MYSQL_HOST            host of the MariaDB service
#   MYSQL_ROOT_PASS       MariaDB root password
#   MYSQL_USER            OpenEMR DB user (default: openemr)
#   MYSQL_PASS            OpenEMR DB password
#   OE_USER               OpenEMR admin username (default: admin)
#   OE_PASS               OpenEMR admin password (set a strong value)
#
# Health endpoint: GET /meta/health/readyz (HTTPS).
# Initial boot runs OpenEMR setup; expect ~2-3 minutes before ready.

FROM openemr/openemr:flex@sha256:e4562b0c7d3f222ec8f72122ce00d10ffa93f559c38c00ab12c1355394c35d1c

# Mark the deployed image as the AgentForge fork build.
RUN mkdir -p /var/www/localhost/htdocs/openemr/interface/agentforge

COPY interface/agentforge/copilot.php \
     /var/www/localhost/htdocs/openemr/interface/agentforge/copilot.php
COPY interface/main/tabs/menu/menus/standard.json \
     /var/www/localhost/htdocs/openemr/interface/main/tabs/menu/menus/standard.json
COPY interface/main/tabs/menu/menus/front_office.json \
     /var/www/localhost/htdocs/openemr/interface/main/tabs/menu/menus/front_office.json
COPY interface/main/tabs/menu/menus/chart_review.json \
     /var/www/localhost/htdocs/openemr/interface/main/tabs/menu/menus/chart_review.json
COPY interface/main/tabs/menu/menus/answering_service.json \
     /var/www/localhost/htdocs/openemr/interface/main/tabs/menu/menus/answering_service.json
COPY interface/main/tabs/menu/menus/patient_menus/standard.json \
     /var/www/localhost/htdocs/openemr/interface/main/tabs/menu/menus/patient_menus/standard.json
COPY interface/patient_tracker/patient_tracker.php \
     /var/www/localhost/htdocs/openemr/interface/patient_tracker/patient_tracker.php
COPY library/globals.inc.php \
     /var/www/localhost/htdocs/openemr/library/globals.inc.php
COPY src/Services/Globals/GlobalConnectorsEnum.php \
     /var/www/localhost/htdocs/openemr/src/Services/Globals/GlobalConnectorsEnum.php

COPY AUDIT.md ARCHITECTURE.md USERS.md USER.md PRESEARCH.md \
     DEPLOYMENT_RUNBOOK.md DEMO_PLAN.md EVAL_PLAN.md \
     MVP_AUTH_SCOPE.md MVP_STATUS.md OPENEMR_VERSION_PIN.md \
     /var/www/localhost/htdocs/openemr/agentforge/

RUN printf '%s\n' \
    'AgentForge Clinical Co-Pilot — fork build.' \
    'Source: https://github.com/mtm1671-crypto/moran-openemr' \
    'See agentforge/ARCHITECTURE.md for the agent integration plan.' \
    > /var/www/localhost/htdocs/openemr/agentforge/FORK_INFO.txt
