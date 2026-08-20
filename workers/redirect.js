/**
 * redirect.js — host canonicalisation for the carsite Worker.
 * Any request on a *.workers.dev hostname is permanently redirected to the
 * canonical https://motorjury.com equivalent; everything else falls through
 * to the static assets. Keeps the old hostname's links and search entries
 * flowing to the real domain instead of splitting authority across two hosts.
 */
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.hostname.endsWith(".workers.dev") || url.hostname === "www.motorjury.com") {
      url.hostname = "motorjury.com";
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(req);
  },
};
