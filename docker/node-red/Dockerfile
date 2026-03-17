FROM nodered/node-red:4.1.7-debian

USER root
RUN apt-get update     && apt-get install -y --no-install-recommends python3 make g++     && rm -rf /var/lib/apt/lists/*

USER node-red
RUN npm install --unsafe-perm --no-update-notifier --no-fund     node-red-contrib-telegrambot@~17.1.0     node-red-node-serialport@~2.0.3
