"""
ContextWizard Backend - FastAPI application entry point.

A GitHub PR review assistant that uses Gemini AI to:
- Classify review comments
- Clarify unclear questions and change requests
- Generate code suggestions
- Perform autonomous code reviews
"""
from fastapi import FastAPI
from database.connection import init_db
from routes.analyze import router as analyze_router
from routes.pending_comments import router as pending_comments_router
import os
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="ContextWizard Backend",
    description="AI-powered GitHub PR review assistant",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "ContextWizard Backend is running"}

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()


# Register routers
app.include_router(analyze_router)
app.include_router(pending_comments_router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)