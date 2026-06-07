# Christduell

A Quizduell-style trivia duel app for playful Christian education — challenge friends, answer Bible and faith-themed questions, and climb the leaderboard.

## Project structure

- `backend/` — FastAPI backend (Python, managed with `uv`), deployed to Azure. Owns game logic, question banks, matchmaking, scoring, and push notification dispatch.
- `frontend/` — Expo / React Native (TypeScript) mobile app. Talks to the backend over REST and registers for push notifications.

## Getting started

### Backend

```sh
cd backend
uv sync
uv run fastapi dev app/main.py
```

### Frontend

```sh
cd frontend
npm install
npx expo start
```

## Stack

| Layer        | Choice                                   |
|--------------|------------------------------------------|
| Backend      | FastAPI + uv, deployed to Azure          |
| Frontend     | Expo / React Native (TypeScript)         |
| Push         | Expo Notifications / Azure Notification Hubs |
