// probot-app/index.js
const axios = require("axios");

// ----------------------------
// Configuration
// ----------------------------
const COMMENT_EXPIRY_MINUTES = 2; // Demo: 2 minutes for quick testing
const CLEANUP_INTERVAL_MS = 60 * 1000; // Check every 60 seconds

// ----------------------------
// Env
// ----------------------------
function getBackendUrl(context) {
  const url = process.env.BACKEND_URL;
  if (!url) {
    context.log.error("BACKEND_URL is not set in environment variables");
    return null;
  }
  return url;
}

// ----------------------------
// Bot detection
// ----------------------------
function isFromBot(context) {
  const sender = context.payload.sender;
  if (!sender) return false;
  if (sender.type === "Bot") return true;
  if (sender.login && sender.login.endsWith("[bot]")) return true;
  return false;
}

// ----------------------------
// Message code generator
// ----------------------------
function generateMessageCode() {
  // Generate 6-character alphanumeric code (uppercase)
  return Math.random().toString(36).substring(2, 8).toUpperCase();
}

// ----------------------------
// Comment footer with message code
// ----------------------------
function addMessageCodeFooter(commentBody, messageCode) {
  return `${commentBody}\n\n---\n_Message ID: **${messageCode}** • Reply with \`/accept ${messageCode}\` or \`/reject ${messageCode}\` within ${COMMENT_EXPIRY_MINUTES} minutes_`;
}

// ----------------------------
// Backend API calls
// ----------------------------
async function callBackend(context, payloadForBackend) {
  const backendUrl = getBackendUrl(context);
  if (!backendUrl) return null;

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
  const backendUrl = getBackendUrl(context);
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
  const backendUrl = getBackendUrl(context);
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
  const backendUrl = getBackendUrl(context);
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

async function getExpiredComments(context) {
  const backendUrl = getBackendUrl(context);
  if (!backendUrl) return [];

  try {
    const res = await axios.get(`${backendUrl}/pending-comments/expired/list`, {
      timeout: 10_000
    });
    return res.data.expired_comments || [];
  } catch (err) {
    context.log.error({ err }, "Error fetching expired comments");
    return [];
  }
}

// ----------------------------
// GitHub operations
// ----------------------------
async function getPrFiles(context, owner, repo, prNumber) {
  const files = [];
  let page = 1;

  while (true) {
    const res = await context.octokit.pulls.listFiles({
      owner,
      repo,
      pull_number: prNumber,
      per_page: 100,
      page
    });

    if (!res.data.length) break;

    for (const f of res.data) {
      files.push({
        filename: f.filename,
        status: f.status,
        additions: f.additions,
        deletions: f.deletions,
        changes: f.changes,
        patch: f.patch
      });
    }

    if (res.data.length < 100) break;
    page += 1;
  }

  return files;
}

async function replyToInlineComment(context, owner, repoName, prNumber, commentId, body) {
  const response = await context.octokit.pulls.createReplyForReviewComment({
    owner,
    repo: repoName,
    pull_number: prNumber,
    comment_id: commentId,
    body
  });
  return response.data;
}

async function replyToPrThread(context, owner, repoName, prNumber, body) {
  const response = await context.octokit.issues.createComment({
    owner,
    repo: repoName,
    issue_number: prNumber,
    body
  });
  return response.data;
}

async function deleteInlineComment(context, owner, repo, commentId) {
  try {
    await context.octokit.pulls.deleteReviewComment({
      owner,
      repo,
      comment_id: commentId
    });
    context.log.info({ commentId }, "Deleted inline comment");
    return true;
  } catch (err) {
    context.log.error({ err, commentId }, "Error deleting inline comment");
    return false;
  }
}

async function deleteThreadComment(context, owner, repo, commentId) {
  try {
    await context.octokit.issues.deleteComment({
      owner,
      repo,
      comment_id: commentId
    });
    context.log.info({ commentId }, "Deleted thread comment");
    return true;
  } catch (err) {
    context.log.error({ err, commentId }, "Error deleting thread comment");
    return false;
  }
}

// ----------------------------
// Payload builders
// ----------------------------
async function buildReviewCommentPayload(context) {
  const comment = context.payload.comment;
  const pr = context.payload.pull_request;
  const repo = context.payload.repository;

  const commentBodyOriginal = (comment.body || "").trim();
  if (!commentBodyOriginal) return null;

  const owner = repo.owner.login;
  const repoName = repo.name;
  const prNumber = pr.number;

  const files = await getPrFiles(context, owner, repoName, prNumber);

  return {
    kind: "review_comment",
    review_body: null,
    review_state: null,
    comment_body: commentBodyOriginal,
    comment_path: comment.path,
    comment_diff_hunk: comment.diff_hunk,
    comment_position: comment.position,
    comment_id: comment.id,
    reviewer_login: comment.user && comment.user.login,
    pr_number: prNumber,
    pr_title: pr.title,
    pr_body: pr.body,
    pr_author_login: pr.user && pr.user.login,
    repo_full_name: repo.full_name,
    repo_owner: owner,
    repo_name: repoName,
    files,
    review_comments: null,
    inline_comment_count: 0
  };
}

async function buildReviewPayload(context) {
  const review = context.payload.review;
  const pr = context.payload.pull_request;
  const repo = context.payload.repository;

  const reviewBodyOriginal = (review.body || "").trim();
  if (!reviewBodyOriginal) return null;

  const owner = repo.owner.login;
  const repoName = repo.name;
  const prNumber = pr.number;

  // Fetch all review comments for this review to count inline comments
  let inlineCommentCount = 0;
  try {
    const reviewCommentsResponse = await context.octokit.pulls.listCommentsForReview({
      owner,
      repo: repoName,
      pull_number: prNumber,
      review_id: review.id
    });
    inlineCommentCount = reviewCommentsResponse.data.length;
    context.log.info({ review_id: review.id, inline_count: inlineCommentCount }, "Fetched inline comment count for review");
  } catch (err) {
    context.log.error({ err, review_id: review.id }, "Error fetching review comments count");
    // Continue with 0 if we can't fetch
  }

  const files = await getPrFiles(context, owner, repoName, prNumber);

  return {
    kind: "review",
    review_body: reviewBodyOriginal,
    review_state: review.state,
    comment_body: null,
    comment_path: null,
    comment_diff_hunk: null,
    comment_position: null,
    comment_id: null,
    reviewer_login: review.user && review.user.login,
    pr_number: prNumber,
    pr_title: pr.title,
    pr_body: pr.body,
    pr_author_login: pr.user && pr.user.login,
    repo_full_name: repo.full_name,
    repo_owner: owner,
    repo_name: repoName,
    files,
    review_comments: null,
    inline_comment_count: inlineCommentCount
  };
}

async function buildIssueCommentPayload(context) {
  const comment = context.payload.comment;
  const issue = context.payload.issue;
  const repo = context.payload.repository;

  const commentBodyOriginal = (comment.body || "").trim();
  if (!commentBodyOriginal) return null;

  // Check if this is a PR (issues and PRs share the same endpoint)
  if (!issue.pull_request) {
    context.log.info("Issue comment is not on a PR, skipping");
    return null;
  }

  const owner = repo.owner.login;
  const repoName = repo.name;
  const prNumber = issue.number;

  // Fetch PR details
  const prResponse = await context.octokit.pulls.get({
    owner,
    repo: repoName,
    pull_number: prNumber
  });
  const pr = prResponse.data;

  const files = await getPrFiles(context, owner, repoName, prNumber);

  return {
    kind: "issue_comment",
    review_body: null,
    review_state: null,
    comment_body: commentBodyOriginal,
    comment_path: null,
    comment_diff_hunk: null,
    comment_position: null,
    comment_id: comment.id,
    reviewer_login: comment.user && comment.user.login,
    pr_number: prNumber,
    pr_title: pr.title,
    pr_body: pr.body,
    pr_author_login: pr.user && pr.user.login,
    repo_full_name: repo.full_name,
    repo_owner: owner,
    repo_name: repoName,
    files,
    review_comments: null,
    inline_comment_count: 0
  };
}

// ----------------------------
// Command parser
// ----------------------------
function parseCommand(commentBody) {
  const trimmed = (commentBody || "").trim();
  
  // Match /accept CODE or /reject CODE
  const acceptMatch = trimmed.match(/^\/accept\s+([A-Z0-9]{6})$/i);
  if (acceptMatch) {
    return { command: "accept", code: acceptMatch[1].toUpperCase() };
  }

  const rejectMatch = trimmed.match(/^\/reject\s+([A-Z0-9]{6})$/i);
  if (rejectMatch) {
    return { command: "reject", code: rejectMatch[1].toUpperCase() };
  }

  return null;
}

// ----------------------------
// Background cleanup job
// ----------------------------
async function cleanupExpiredComments(app) {
  try {
    console.log("[cleanup] Running cleanup job...");
    
    const backendUrl = process.env.BACKEND_URL;
    if (!backendUrl) {
      console.error("[cleanup] BACKEND_URL not set");
      return;
    }

    const res = await axios.get(`${backendUrl}/pending-comments/expired/list`, {
      timeout: 10_000
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

// ----------------------------
// Main Probot app
// ----------------------------
module.exports = (app) => {
  // Start background cleanup job
  startCleanupJob(app);

  // ----------------------------
  // 1. Handle inline review comment
  // ----------------------------
  app.on("pull_request_review_comment.created", async (context) => {
    try {
      console.log("Received pull_request_review_comment.created event");
      
      if (isFromBot(context)) return;

      const commentBody = (context.payload.comment.body || "").trim();
      const isWizardCmd = commentBody.startsWith("/wizard-review");

      const payloadForBackend = await buildReviewCommentPayload(context);
      if (!payloadForBackend) return;

      if (isWizardCmd) {
        console.log("Detected /wizard-review command in inline comment");
        payloadForBackend.kind = "wizard_review_command";
      }

      const replyBody = await callBackend(context, payloadForBackend);
      if (!replyBody) return;

      const messageCode = generateMessageCode();
      const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);

      const owner = payloadForBackend.repo_owner;
      const repoName = payloadForBackend.repo_name;
      const prNumber = payloadForBackend.pr_number;

      const postedComment = await replyToInlineComment(
        context,
        owner,
        repoName,
        prNumber,
        context.payload.comment.id,
        fullReplyBody
      );

      const expiresAt = Math.floor(Date.now() / 1000) + (COMMENT_EXPIRY_MINUTES * 60);
      await storePendingComment(context, {
        code: messageCode,
        comment_id: postedComment.id,
        comment_type: "inline",
        owner,
        repo: repoName,
        pr_number: prNumber,
        installation_id: context.payload.installation.id,
        expires_at: expiresAt
      });

      context.log.info({ messageCode, commentId: postedComment.id }, "Posted inline comment with message code");
    } catch (err) {
      context.log.error({ err }, "Error in pull_request_review_comment.created");
    }
  });

  // ----------------------------
  // 2. Handle submitted review
  // ----------------------------
  app.on("pull_request_review.submitted", async (context) => {
    try {
      if (isFromBot(context)) {
        context.log.info("Skipping event from bot sender.");
        return;
      }

      const reviewBody = context.payload.review.body;
      if (!reviewBody || reviewBody.trim() === "") {
        context.log.info("Skipping review with empty body.");
        return;
      }

      const payloadForBackend = await buildReviewPayload(context);
      if (!payloadForBackend) {
        context.log.info("Review payload construction failed, skipping.");
        return;
      }

      // Skip if review has inline comments
      if (payloadForBackend.inline_comment_count > 0) {
        context.log.info(
          { 
            review_id: context.payload.review.id, 
            inline_count: payloadForBackend.inline_comment_count 
          }, 
          "Skipping review with inline comments - inline comments will be handled separately"
        );
        return;
      }

      const replyBody = await callBackend(context, payloadForBackend);
      if (!replyBody) return;

      const messageCode = generateMessageCode();
      const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);

      const repo = context.payload.repository;
      const pr = context.payload.pull_request;
      const owner = repo.owner.login;
      const repoName = repo.name;
      const prNumber = pr.number;

      const postedComment = await replyToPrThread(
        context,
        owner,
        repoName,
        prNumber,
        fullReplyBody
      );

      const expiresAt = Math.floor(Date.now() / 1000) + (COMMENT_EXPIRY_MINUTES * 60);
      await storePendingComment(context, {
        code: messageCode,
        comment_id: postedComment.id,
        comment_type: "thread",
        owner,
        repo: repoName,
        pr_number: prNumber,
        installation_id: context.payload.installation.id,
        expires_at: expiresAt
      });

      context.log.info(
        { pr: prNumber, review_id: context.payload.review.id, messageCode },
        "Replied to submitted review with message code"
      );
    } catch (err) {
      context.log.error({ err }, "Error while handling pull_request_review.submitted");
    }
  });

  // ----------------------------
  // 3. Handle issue/PR conversation comments
  // ----------------------------
  app.on("issue_comment.created", async (context) => {
    try {
      console.log("=== Received issue_comment.created event ===");
      console.log("Comment body:", context.payload.comment.body);
      console.log("Sender:", context.payload.sender?.login);
      
      if (isFromBot(context)) {
        console.log("Skipping: comment is from bot");
        return;
      }

      const commentBody = context.payload.comment.body;
      const parsed = parseCommand(commentBody);

      console.log("Parsed command:", parsed);

      // Check if it's a command first
      if (parsed) {
        // Handle /accept and /reject commands
        context.log.info({ command: parsed.command, code: parsed.code }, "Received command");

        const pendingComment = await lookupPendingComment(context, parsed.code);
        
        console.log("Lookup result:", pendingComment);
        
        if (!pendingComment) {
          context.log.info({ code: parsed.code }, "Code not found or already processed");
          console.log("❌ Code not found in database");
          return;
        }

        const { comment_id, comment_type, owner, repo, pr_number } = pendingComment;
        console.log(`Found comment: id=${comment_id}, type=${comment_type}`);

        const commandCommentId = context.payload.comment.id;

        if (parsed.command === "accept") {
          await deletePendingComment(context, parsed.code);
          context.log.info({ code: parsed.code, commentId: comment_id }, "Accepted - comment kept");
          console.log("✅ ACCEPTED - Comment kept, removed from tracking");
          
          await deleteThreadComment(context, owner, repo, commandCommentId);
          console.log(`🗑️ Deleted command comment ${commandCommentId}`);
          
        } else if (parsed.command === "reject") {
          console.log(`Attempting to delete ${comment_type} comment ${comment_id}...`);
          let deleted = false;
          if (comment_type === "inline") {
            deleted = await deleteInlineComment(context, owner, repo, comment_id);
          } else {
            deleted = await deleteThreadComment(context, owner, repo, comment_id);
          }

          await deletePendingComment(context, parsed.code);
          
          if (deleted) {
            context.log.info({ code: parsed.code, commentId: comment_id }, "Rejected - comment deleted");
            console.log("✅ REJECTED - Comment deleted successfully");
          } else {
            context.log.warn({ code: parsed.code, commentId: comment_id }, "Rejected but deletion failed");
            console.log("⚠️ REJECTED - Deletion failed (might be already deleted)");
          }
          
          await deleteThreadComment(context, owner, repo, commandCommentId);
          console.log(`🗑️ Deleted command comment ${commandCommentId}`);
        }
        return; // Exit after handling command
      }

      // Not a command - treat as regular conversation comment
      console.log("Not a command - processing as regular conversation comment");

      // Check for /wizard-review command
      const isWizardCmd = commentBody.trim().startsWith("/wizard-review");

      const payloadForBackend = await buildIssueCommentPayload(context);
      if (!payloadForBackend) return;

      if (isWizardCmd) {
        console.log("Detected /wizard-review command in conversation comment");
        payloadForBackend.kind = "wizard_review_command";
      }

      const replyBody = await callBackend(context, payloadForBackend);
      if (!replyBody) return;

      const messageCode = generateMessageCode();
      const fullReplyBody = addMessageCodeFooter(replyBody, messageCode);

      const owner = payloadForBackend.repo_owner;
      const repoName = payloadForBackend.repo_name;
      const prNumber = payloadForBackend.pr_number;

      const postedComment = await replyToPrThread(
        context,
        owner,
        repoName,
        prNumber,
        fullReplyBody
      );

      const expiresAt = Math.floor(Date.now() / 1000) + (COMMENT_EXPIRY_MINUTES * 60);
      await storePendingComment(context, {
        code: messageCode,
        comment_id: postedComment.id,
        comment_type: "thread",
        owner,
        repo: repoName,
        pr_number: prNumber,
        installation_id: context.payload.installation.id,
        expires_at: expiresAt
      });

      context.log.info({ messageCode, commentId: postedComment.id, prNumber }, "Posted conversation comment reply with message code");
      console.log(`✅ Posted reply to conversation comment with code ${messageCode}`);

    } catch (err) {
      context.log.error({ err }, "Error handling issue_comment.created");
      console.error("❌ ERROR in issue_comment handler:", err);
    }
  });
};