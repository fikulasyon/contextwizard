// config/constants.js
module.exports = {
  COMMENT_EXPIRY_MINUTES: 2,
  CLEANUP_INTERVAL_MS: 60 * 1000,

  getBackendUrl: () => {
    let baseUrl = process.env.BACKEND_URL;

    if (!baseUrl) {
      console.error("BACKEND_URL is not set in environment variables");
      return null;
    }

    if (!baseUrl.startsWith('http')) {
      baseUrl = `https://${baseUrl}`;
    }

    if (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.slice(0, -1);
    }

    return baseUrl;
  }
};