from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Database Configuration
DB_PATH = os.getenv("PENDING_COMMENTS_DB", "./pending_comments.db")

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_CODE_MODEL = os.getenv("GEMINI_CODE_MODEL", "gemini-2.5-flash")

# Retry Configuration
# not specified in env for now, using defaults
RETRY_INITIAL_DELAY_SEC = float(os.getenv("GEMINI_RETRY_INITIAL_DELAY", "0.35"))
RETRY_MAX_DELAY_SEC = float(os.getenv("GEMINI_RETRY_MAX_DELAY", "2.0"))
RETRY_MAX_ATTEMPTS = int(os.getenv("GEMINI_RETRY_MAX_ATTEMPTS", "12"))
RETRY_JITTER_SEC = float(os.getenv("GEMINI_RETRY_JITTER_SEC", "0.10"))

# Text Clipping Limits
MAX_PR_BODY_LENGTH = 1200
MAX_COMMENT_LENGTH = 1500
MAX_REVIEW_LENGTH = 2000
MAX_DIFF_HUNK_LENGTH = 1200
MAX_PATCH_LENGTH = 1200
MAX_INLINE_COMMENT_LENGTH = 400

# Classification Thresholds
GOOD_CHANGE_CONFIDENCE_THRESHOLD = 0.7
BAD_QUESTION_CONFIDENCE_THRESHOLD = 0.55
BAD_CHANGE_CONFIDENCE_THRESHOLD = 0.55