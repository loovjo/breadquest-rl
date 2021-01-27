FROM node:latest

WORKDIR /etc/breadquest
COPY breadquest/package.json /etc/breadquest-pkginstall/package.json
RUN cd /etc/breadquest-pkginstall ; npm install

ENV NODE_ENV=production

CMD echo ni li seme > sessionSecret.txt ; node breadQuest.js
