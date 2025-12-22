// builders/payload-builder.js
const { getPrFiles } = require('../services/github-api');

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

async function buildWizardReviewPayload(context, pr, repo) {
  const owner = repo.owner.login;
  const repoName = repo.name;
  const prNumber = pr.number;
  
  const files = await getPrFiles(context, owner, repoName, prNumber);
  
  return {
    kind: "wizard_review_command",
    review_body: null,
    review_state: null,
    comment_body: "/wizard-review",
    comment_path: null,
    comment_diff_hunk: null,
    comment_position: null,
    comment_id: null,
    reviewer_login: context.payload.sender?.login,
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

module.exports = {
  buildReviewCommentPayload,
  buildReviewPayload,
  buildIssueCommentPayload,
  buildWizardReviewPayload
};