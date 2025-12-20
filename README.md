# 🧙‍♂️ ContextWizard: LLM-Powered Code Review Orchestrator

**ContextWizard** is an advanced AI-driven GitHub App built to revolutionize the Pull Request review cycle. By leveraging a dual-service architecture and state-of-the-art Large Language Models (LLMs), it acts as a proactive technical partner that classifies feedback, clarifies ambiguity, and performs autonomous security audits.

## 👥 Authors (Bilkent University - CS453)

* **Mert Terkuran** (22101645)
* **Ahmet Faik Utku** (22103582)
* **Guillaume-Alain PRISO TOTTO** (22501093)
* **Hamza CHAABA** (22501096)

---

## 🏗 System Architecture

The project is architected as a decoupled system to ensure scalability and model agnosticism.

1. **Event Gateway (Probot/Node.js)**: Acts as the primary interface with GitHub. It listens to webhooks, manages the GitHub App’s security handshake, and translates GitHub-specific payloads into a unified format for the backend.
2. **LLM Orchestrator (FastAPI/Python)**: The "brain" of the operation. It handles prompt engineering, context management (clipping/truncating), and communicates with AI providers via an asynchronous, thread-safe implementation.

---

## 🌟 Advanced Features & Functional Requirements

### 1. Multi-Provider Provider Switching (The Switcher)

Unlike hardcoded integrations, ContextWizard features a centralized orchestrator. By changing the `LLM_PROVIDER` environment variable, you can switch between:

* **Google Gemini 2.0 Flash**: Optimized for structured data extraction and rapid classification.
* **Perplexity Sonar**: Utilized for deep technical reasoning and complex code clarification.

### 2. Autonomous "Wizard Review" (FR5.1)

Triggered by a manual command, the AI performs a comprehensive audit of the entire PR diff. It identifies:

* **Bugs & Logic Errors**: Potential null pointers, race conditions, or off-by-one errors.
* **Security Vulnerabilities**: Hardcoded secrets, injection risks, or weak cryptographic patterns.
* **Best Practices**: Alignment with language-specific style guides and performance optimizations.

### 3. Intelligent Classification & Clarification (FR3.1 & FR4.1)

The bot monitors all review comments and classifies them into:
`PRAISE`, `GOOD_CHANGE`, `BAD_CHANGE`, `GOOD_QUESTION`, `BAD_QUESTION`.

* **Action**: If a comment is flagged as `BAD` (ambiguous), the bot automatically generates a **Clarified Version** to assist the developer in understanding the feedback.

---

## 🎮 Command Reference

| Command | Context | Effect |
| --- | --- | --- |
| `/wizard-review` | PR Comment | Performs a full-diff scan and posts a technical audit report. |
| *(Auto-trigger)* | On Review Post | Analyzes clarity and posts a clarified version if ambiguity is detected. |

---

## 🛠 Technical Implementation Details

### Backend Logic

* **Structured Output Enforcement**: Uses Pydantic to validate LLM JSON responses. If a model "hallucinates" a field, the backend catches the error before it reaches the user.
* **Context Clipping**: Intelligent truncation logic ensures that large diffs are "clipped" to fit within LLM token limits while retaining critical code context.
* **Resilience**: Implements exponential backoff and jittered retries to handle transient 503 errors and rate limits from Google/Perplexity APIs.

### Deployment Configuration

The system is fully containerized and deployable via the included `render.yaml` Blueprint.

* **Networking**: Services communicate via Render's internal private network on port `8000`.
* **Security**: Uses RSA Private Keys for GitHub App authentication and encrypted environment variables for LLM API keys.

---

## 🚀 Getting Started

### Local Setup

1. **Clone the Repository**:
```bash
git clone https://github.com/fikulasyon/contextwizard.git

```


2. **Environment Setup**:
Configure `.env` files in both `/backend` and `/probot-app` using the provided templates.
3. **Launch with Docker**:
```bash
docker-compose up --build

```



### Deployment on Render

1. Connect your GitHub repository to Render.
2. Render will automatically detect the `render.yaml` file.
3. Fill in the `PRIVATE_KEY` (copy-paste the full `.pem` file content) and API keys in the Render Dashboard.

---

### 📄 License & Course Info

This project was developed for the **CS453 - Advanced Software Engineering** course at **Bilkent University**.
