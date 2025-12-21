# 🧙‍♂️ ContextWizard: LLM-Powered Code Review Orchestrator

**ContextWizard** is an advanced AI-driven GitHub App built to streamline and enhance the Pull Request (PR) review process. Using a dual-service architecture and Large Language Models (LLMs), it helps reviewers and contributors by classifying review intent, clarifying ambiguous feedback, and generating actionable code suggestions directly within GitHub.

The system is designed to **reduce back-and-forth in PR discussions**, improve review clarity, and accelerate merge times without disrupting existing workflows.

---

## 👥 Authors (Bilkent University – CS453)

- **Mert Terkuran** (22101645)  
- **Ahmet Faik Utku** (22103582)  
- **Guillaume-Alain PRISO TOTTO** (22501093)  
- **Hamza CHAABA** (22501096)  

---

## 🏗️ System Architecture

ContextWizard is composed of two main components:

- **Backend Service**
  - FastAPI-based REST API
  - Handles intent classification and code suggestion generation
  - Powered by Google Gemini LLMs
  - Maintains lightweight state using SQLite

- **GitHub App (Probot)**
  - Listens to GitHub webhook events
  - Extracts PR context and review comments
  - Communicates with the backend
  - Posts responses back to pull requests

---

## 📁 Project Structure

.
├── backend/
│ ├── main.py
│ ├── requirements.txt
│ ├── pending_comments.db
│ └── .env
│
├── probot-app/
│ ├── index.js
│ ├── package.json
│ └── .env

## ⚙️ Environment Variables

### Backend (`backend/.env`)
GEMINI_API_KEY="AIxxxxx"
GEMINI_MODEL="gemini-2.5-flash-lite"
PENDING_COMMENTS_DB=./pending_comments.db

APP_ID=2453186
PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA2mMR0gIy0pdvENobMEQ37SMquuM95kt59AsxbE8D1jIOb3Ik
gvr+LHKnhltZ9osCCi87w7Ui2OPrv29IgDs+qrtKwITMebZ/sQrpKhB8CIr7NFNN
gGgT0/HThpkfN/gL6TnmB283e4/OMgwvK695bPZSBSmN0yoI3t/BND9LAi6PvoCa
8Wc6U4I8Y4qF5omxR+WA8hDg0yk36j2gwiDEEWuDhFPcVuVOoIvkTywkf0LkWMpS
5QGr4cohCPrX2lnz848mS6AQbDqCokl6smPVubUNf/PS8fxEVNXxj1CUPnmsqxW/
G3ddtt66/Mvo2qF/dV5qsK3Zsa0AqmNF4ytPOwIDAQABAoIBABrdYQ3Sk2nwkwsh
qYKQgci8ML94wN6ZnlD1J4lJVxF8auYuxmsOcUIKgK04g6Keiwuxr8ptd/HyZ8fO
6r5Li3P5QkLYk0bNunuO+gvgp0Ftx2UycjA/nWDPONQv9fUuoFh6dN+pQMwEbrsd
YJghJ/DNhF16NSYq35h7Mgs5VgLYeTV/65GNwjRMoFdLZgIYeDzPbKsuNBfJPZ19
VvAvRY19MQG16Vy8GSgGu0fW8Bj32geIVKA5YOrqJ3Ny+BP43U9N0P6217qyqRMV
9X+mA3PH9lgSNwDgV01R2blxj0FpIuJKTPacrdP8Smqal94l+tV7xA7GPSZArjLA
pFvaDaECgYEA+l9uYYWKTmxJcSXIzsWpl3YOxJHacAz+/UpC2k+mvedSn6D9vlxq
At0119nLF9YDcB7dCOGMuDUf89CfuofWtLo4EAlWID/jfXn4xPEQWcb3ivZT1TxP
vEpGVpUX4trPJqaGXJiucxuvUD4Fc3HOkq3FwJrY84uwRse7szALJbMCgYEA30ua
GNvI/NujFe3PArgCQep9lmECtGkFKNHNi0XjM4xiOdlWJYPt/pjaW4HyW3owsEK+
OYwgIfZdAMb7K1PhQubvTkGIKWiIb7tNlFzPCRGv6k7tDi/iQNwZo2IEFhT3rRfk
cgqTbcrP87QCpijwnYn5h0QOUAAUFSoCvCeV/FkCgYEAg1TVqLAMyXBB4eko+VVz
zTAvNOsxAr++bYyrnqpTU5/oljUzhMwjC5ePq8bhooIvUXvPA96UGvg654DSmFyy
wiBAUiEjnU0F/oaheGTe58jXhnwJo3u8c48ecEJKwkN2j9af+ihYsaafAl9WKqVS
71vZtFtFXBM1Bxu0GJ0l68MCgYBq4Dy5eTkSDe5ZKKHUo04xTpMdzwEEaN/XUdQX
vTOqEJ9TIPtiqWrYWUDqW6AsuKdlNgzmbnNSziBlptfBPTysUOxpgGQzrZzgHb5c
LK/Ln3Obqns8Nx8L/E0pLljWWOLTLoRhMT6vZktyUc6SyTWhsdCFNcXD9MWn+5uj
gy7+wQKBgEr7QTFPpj9B3cz39ILz8UoFxxaL4UhHutnvDW0oYWqxjz+qfywGYzLk
IQ6AzWT+Yo484ayql9tVmHfvEYONBCLc+cdPu6CwSBDA3n0rGXVNjLT9ympN9qYe
L+wf+s0oF7ymYTxyjT7s/9YLcgME1JaKdMrGyTH1cQdMoYM+6G6A
-----END RSA PRIVATE KEY-----"
WEBHOOK_SECRET=draingang
BACKEND_URL=http://localhost:8000
PORT=3000

##🧩 Dependencies##
Backend (backend/requirements.txt)
fastapi >= 0.115.0
pydantic >= 2.0.0
uvicorn >= 0.30.0
python-dotenv >= 1.0.0
google-genai >= 0.3.0
anyio >= 4.0.0

##🚀 Running the System ##

###Terminal 1 – Backend API###
source venv/bin/activate   # Windows: venv\Scripts\activate
cd backend
uvicorn main:app --reload --port 8000

Backend will run at: http://localhost:8000


###Terminal 2 – Probot GitHub App###
cd probot-app
npm install
npm run dev

This starts the GitHub App server on port 3000.

###Terminal 3 – Webhook Forwarding (Smee)###
npx smee-client \
  --url https://smee.io/y6inAjkDY0kzhR7f \
  --target http://localhost:3000/api/github/webhooks

This forwards GitHub webhook events to your local Probot instance.

