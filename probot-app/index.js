const axios = require("axios");

async function callBackend(context, payloadForBackend) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    context.log.error("BACKEND_URL is not set in environment variables");
    return null;
  }

  context.log.info("Sending payload to backend", payloadForBackend);

  try {
    const res = await axios.post(backendUrl, payloadForBackend);
    const data = res.data;
    const commentBody = data.comment;
    if (!commentBody || !commentBody.trim()) {
      context.log("Backend returned empty comment, skipping.");
      return null;
    }
    return commentBody;
  } catch (err) {
    context.log.error("Error calling backend", err);
    return null;
  }
}

// helper for files (we keep it; see next section)
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
        patch: f.patch // unified diff (contains before & after)
      });
    }
    if (res.data.length < 100) break;
    page += 1;
  }
  return files;
}

module.exports = (app) => {
  // 1) Full review submitted (Approve / Request changes / Comment)
  app.on("pull_request_review.submitted", async (context) => {
    const review = context.payload.review;
    const pr = context.payload.pull_request;
    const repo = context.payload.repository;

    const reviewBody = review.body || "";
    if (!reviewBody.trim()) {
      context.log("Review body empty, skipping.");
      return;
    }

    const owner = repo.owner.login;
    const repoName = repo.name;
    const prNumber = pr.number;
    const files = await getPrFiles(context, owner, repoName, prNumber);

    const payloadForBackend = {
      kind: "review",
      review_body: reviewBody,
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
      files
    };

    const commentBody = await callBackend(context, payloadForBackend);
    if (!commentBody) return;

    // “Reply” in conversation = normal issue comment on the PR
    await context.octokit.issues.createComment({
      owner,
      repo: repoName,
      issue_number: prNumber,
      body: commentBody
    });
  });

  // 2) Single inline comment on “Files changed”
  app.on("pull_request_review_comment.created", async (context) => {
    const comment = context.payload.comment;
    const pr = context.payload.pull_request;
    const repo = context.payload.repository;

    const commentBodyOriginal = comment.body || "";
    if (!commentBodyOriginal.trim()) {
      context.log("Inline comment body empty, skipping.");
      return;
    }

    const owner = repo.owner.login;
    const repoName = repo.name;
    const prNumber = pr.number;
    const files = await getPrFiles(context, owner, repoName, prNumber);

    const payloadForBackend = {
      kind: "review_comment",
      review_body: null,
      review_state: null,
      comment_body: commentBodyOriginal,
      comment_path: comment.path,
      comment_diff_hunk: comment.diff_hunk,
      comment_position: comment.position,
      comment_id: comment.id, // important for reply
      reviewer_login: comment.user && comment.user.login,
      pr_number: prNumber,
      pr_title: pr.title,
      pr_body: pr.body,
      pr_author_login: pr.user && pr.user.login,
      repo_full_name: repo.full_name,
      repo_owner: owner,
      repo_name: repoName,
      files
    };

    const replyBody = await callBackend(context, payloadForBackend);
    if (!replyBody) return;

    // 🔥 This is the “reply to that specific comment” part:
    await context.octokit.pulls.createReplyForReviewComment({
      owner,
      repo: repoName,
      pull_number: prNumber,
      comment_id: comment.id,
      body: replyBody
    });

    context.log.info("Replied to inline review comment.");
  });
};
