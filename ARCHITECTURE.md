# Court Report — How It Works (Plain English)

## The Big Picture

Court Report is an app that lets you ask questions about NBA games and players in plain English, and get back a well-written, intelligent answer — like a sports reporter wrote it. Under the hood, several tools work together in a pipeline to make that happen. Here's what each one does and how they connect.

---

## The Tools

### 1. `nba_api` — The Data Fetcher
`nba_api` is a Python library that talks to the NBA's official stats website and pulls down real game data. Think of it as the app's researcher — it can fetch box scores, player stats, game schedules, shot charts, and more. Whenever the app needs raw NBA data (like "how many points did LeBron score last night?"), `nba_api` goes and gets it.

### 2. Chroma — The Memory Bank
Once we fetch data from `nba_api`, we don't want to re-fetch it every time someone asks a similar question. Instead, we store it in **Chroma**, which is a vector database. A vector database is a special kind of storage that saves information in a way that makes it easy to search by *meaning*, not just exact words. So if you ask "how did the Lakers do?", Chroma can find stored data about the Lakers even if it wasn't labeled exactly that way. Think of it as the app's long-term memory.

### 3. LangChain — The Pipeline Builder
LangChain is a framework that connects all the pieces together. It handles the flow of data from one step to the next — fetching from Chroma, formatting the context, sending it to Claude, and returning the result. Think of LangChain as the assembly line manager: it doesn't do the heavy lifting itself, but it makes sure every tool gets called in the right order with the right inputs.

### 4. Claude API — The Writer and Reasoner
Claude is Anthropic's AI model, and it's the brain of the app. Once LangChain has pulled the relevant NBA data out of Chroma, it hands that data to Claude along with the user's question. Claude reads the stats, understands the question, and writes a clear, natural-language answer — like a short game recap or player analysis. Claude doesn't fetch data on its own; it only works with what it's given.

### 5. FastAPI — The Web Server
FastAPI is what makes the app accessible over the internet. It creates an API endpoint — basically a URL you can send a question to — and returns the answer. When a user (or a front-end app) sends a question like "Who led the Celtics in assists last game?", FastAPI receives that request, kicks off the pipeline, and sends the final answer back.

---

## How They Connect — Step by Step

```
User sends a question
        ↓
[FastAPI] receives the request
        ↓
[LangChain] orchestrates the pipeline
        ↓
[Chroma] is searched for relevant NBA data
    → If data isn't there yet, [nba_api] fetches it and stores it in Chroma
        ↓
[LangChain] packages the data + the original question into a prompt
        ↓
[Claude API] reads the prompt and writes a natural-language answer
        ↓
[FastAPI] sends the answer back to the user
```

---

## A Simple Analogy

Imagine you walk into a sports newsroom and ask a reporter a question.

- The **intern** (`nba_api`) runs to the stats archive and grabs the raw numbers.
- The **filing cabinet** (Chroma) stores those stats so the intern doesn't have to run every single time.
- The **editor** (LangChain) organizes everything and puts it on the reporter's desk in a clear format.
- The **reporter** (Claude) reads the stats and writes the actual story.
- The **front desk** (FastAPI) takes your question when you walk in and hands you the finished story on your way out.

Each piece has one job, and together they turn a raw question into a polished answer.
