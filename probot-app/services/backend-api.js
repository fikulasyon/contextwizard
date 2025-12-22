// services/backend-api.js
const axios = require("axios");
const { getBackendUrl } = require('../config/constants');

async function callBackend(context, payloadForBackend) {
  const backendUrl = getBackendUrl();
  if (!backendUrl) {
    context.log.error("BACKEND_URL is not set in environment variables");
    return null;
  }

  context.log.info(
    { kind: payloadForBackend.kind, pr: payloadForBackend.pr_number },
    "Sending payload to backend"
  );

  try {
    const res = await axios.post(`${backendUrl}/analyze-review`, payloadForBackend, {
      headers: { "Content-Type": "application/json" },
      timeout: 30_000
    });

    const commentBody = res?.data?.comment;
    if (!commentBody || !commentBody.trim()) {
      context.log.info("Backend returned empty comment, skipping.");
      return null;
    }

    return commentBody;
  } catch (err) {
    context.log.error({ err }, "Error calling backend");
    return null;
  }
}

async function storePendingComment(context, data) {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return false;

  try {
    await axios.post(`${backendUrl}/pending-comments`, data, {
      headers: { "Content-Type": "application/json" },
      timeout: 5_000
    });
    context.log.info({ code: data.code }, "Stored pending comment");
    return true;
  } catch (err) {
    context.log.error({ err, code: data.code }, "Error storing pending comment");
    return false;
  }
}

async function lookupPendingComment(context, code) {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return null;

  try {
    const res = await axios.get(`${backendUrl}/pending-comments/${code}`, {
      timeout: 5_000
    });
    return res.data;
  } catch (err) {
    if (err.response && err.response.status === 404) {
      return null; // Code not found
    }
    context.log.error({ err, code }, "Error looking up pending comment");
    return null;
  }
}

async function deletePendingComment(context, code) {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return false;

  try {
    await axios.delete(`${backendUrl}/pending-comments/${code}`, {
      timeout: 5_000
    });
    context.log.info({ code }, "Deleted pending comment from storage");
    return true;
  } catch (err) {
    context.log.error({ err, code }, "Error deleting pending comment");
    return false;
  }
}

async function getExpiredComments() {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return [];

  try {
    const res = await axios.get(`${backendUrl}/pending-comments/expired/list`, {
      timeout: 10_000
    });
    return res.data.expired_comments || [];
  } catch (err) {
    console.error("[backend-api] Error fetching expired comments:", err.message);
    return [];
  }
}

module.exports = {
  callBackend,
  storePendingComment,
  lookupPendingComment,
  deletePendingComment,
  getExpiredComments
};