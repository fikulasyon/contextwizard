// config/constants.js
module.exports = {
  COMMENT_EXPIRY_MINUTES: 2, // Demo: 2 minutes for quick testing
  CLEANUP_INTERVAL_MS: 60 * 1000, // Check every 60 seconds

  getBackendUrl: () => {
    const rawUrl = process.env.BACKEND_URL;

    if (!rawUrl) {
      context.log.error("BACKEND_URL is not set in environment variables");
      return null;
    }
    const protocol = rawUrl.includes('onrender.com') ? 'https://' : 'http://';
    let baseUrl = rawUrl.startsWith('http') ? rawUrl : `${protocol}${rawUrl}`;
    if (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.slice(0, -1);
    }

    return baseUrl;
  }
};