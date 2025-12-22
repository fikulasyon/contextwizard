// services/github-api.js
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

module.exports = {
  getPrFiles,
  replyToInlineComment,
  replyToPrThread,
  deleteInlineComment,
  deleteThreadComment
};