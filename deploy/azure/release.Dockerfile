# The release bundle: this folder (compose file, Caddyfile, prod.env, VM scripts and timers) as an
# image tagged with the release's git SHA. The VM extracts it on deploy (vm/fluidbuddha-deploy), so
# configuration rolls back together with the code.
FROM busybox:1.37
COPY . /bundle
# Executable and LF-only, whatever the checkout did to them.
RUN cd /bundle/vm && sed -i 's/\r$//' fluidbuddha fluidbuddha-deploy bin/*.sh systemd/* \
 && chmod 0755 fluidbuddha fluidbuddha-deploy bin/*.sh
