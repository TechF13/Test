FROM odoo:19.0

USER root
# Python packages needed by political_office (Claude API) and queue_job.
# The image's Python libraries come from Ubuntu packages that pip cannot upgrade
# in place, so anthropic and its dependencies are installed next to them.
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed anthropic \
    && pip3 install --no-cache-dir --break-system-packages openupgradelib
USER odoo
