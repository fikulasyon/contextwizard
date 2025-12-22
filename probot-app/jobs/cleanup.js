// jobs/cleanup.js
const axios = require("axios");
const { getBackendUrl, CLEANUP_INTERVAL_MS } = require('../config/constants');

async function cleanupExpiredComments(app) {
  try {
    console.log("[cleanup] Running cleanup job...");

    const backendUrl = getBackendUrl();
    if (!backendUrl) {
      console.error("[cleanup] BACKEND_URL not set");
      return;
    }

    const res = await axios.get(`${backendUrl}/pending-comments/expired/list`, {
      timeout: 30_000
    });
    const expired = res.data.expired_comments || [];

    if (expired.length === 0) {
      console.log("[cleanup] No expired comments found");
      return;
    }

    console.log(`[cleanup] Found ${expired.length} expired comments`);

    for (const item of expired) {
      console.log(`[cleanup] Processing expired comment: code=${item.code}, id=${item.comment_id}`);

      try {
        const octokit = await app.auth(item.installation_id);

        let deleted = false;
        if (item.comment_type === "inline") {
          try {
            await octokit.rest.pulls.deleteReviewComment({
              owner: item.owner,
              repo: item.repo,
              comment_id: item.comment_id
            });
            deleted = true;
            console.log(`[cleanup] Deleted inline comment ${item.comment_id}`);
          } catch (err) {
            console.error(`[cleanup] Error deleting inline comment ${item.comment_id}:`, err.message);
          }
        } else {
          try {
            await octokit.rest.issues.deleteComment({
              owner: item.owner,
              repo: item.repo,
              comment_id: item.comment_id
            });
            deleted = true;
            console.log(`[cleanup] Deleted thread comment ${item.comment_id}`);
          } catch (err) {
            console.error(`[cleanup] Error deleting thread comment ${item.comment_id}:`, err.message);
          }
        }

        try {
          await axios.delete(`${backendUrl}/pending-comments/${item.code}`, {
            timeout: 5_000
          });
          console.log(`[cleanup] Removed ${item.code} from storage`);
        } catch (err) {
          console.error(`[cleanup] Error removing ${item.code} from storage:`, err.message);
        }

        if (deleted) {
          console.log(`[cleanup] ✅ Successfully auto-deleted comment ${item.code}`);
        } else {
          console.log(`[cleanup] ⚠️ Comment ${item.code} may have been already deleted`);
        }
      } catch (err) {
        console.error(`[cleanup] Error processing ${item.code}:`, err.message);
      }
    }
  } catch (err) {
    console.error("[cleanup] Error in cleanup job:", err.message);
  }
}

function startCleanupJob(app) {
  setInterval(() => cleanupExpiredComments(app), CLEANUP_INTERVAL_MS);
  console.log(`[cleanup] Started cleanup job (runs every ${CLEANUP_INTERVAL_MS / 1000}s)`);
}

module.exports = { startCleanupJob };