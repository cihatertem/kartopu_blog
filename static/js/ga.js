const currentScript = document.currentScript;
const GA_ID = currentScript?.dataset?.gaId;

window.dataLayer = window.dataLayer || [];
function gtag() {
    dataLayer.push(arguments);
}

gtag("js", new Date());
if (GA_ID) gtag("config", GA_ID);
