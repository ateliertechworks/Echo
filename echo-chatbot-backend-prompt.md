# Echo — Chatbot Backend Logic (Scoped Change)

Add chatbot backend logic for the Echo daily team report app. **Scope: backend chatbot logic only.**

**Do not change:**
- Frontend UI (unless strictly required for API compatibility)
- Past Reports feature
- Authentication / team logic

---

## Context

Echo is a daily team reporting app. Leader and members use a chatbot inside **Today's Report**. The chatbot should:
- Ask one question at a time
- Understand the user's natural/messy answer
- Map it to the correct report fields
- Remember previous report context (e.g. "same project")
- Correct spelling and basic grammar in the user's answer before storing it
- Ask follow-up questions when an answer is vague
- Give a final report preview

The report is saved **only** when the user clicks **Save Report**. Excel export is a separate concern and must not be touched.

---

## Model Requirement

Use a local Ollama model — it is not bundled in the project; the backend calls the local Ollama API.

```
OLLAMA_MODEL=qwen3:1.7b
OLLAMA_URL=http://localhost:11434/api/generate
```

---

## Pipeline

```
Frontend message
  → backend chat route
  → load current draft + previous memory
  → call Qwen3 model through Ollama
  → model returns JSON
  → backend validates JSON
  → backend updates draft
  → backend decides next question
  → return next bot message to frontend
```

---

## Report Fields

**Member:**
`project`, `work_done`, `outcome`, `blockers`, `pending_next`

**Leader:**
`project`, `discussion`, `event`, `work_done`, `outcome`, `blockers`, `pending_next`

---

## Files to Create or Update

First, inspect the existing backend structure and reuse existing routes/services if they already exist. Only create the files below if they're missing, and modify carefully without breaking existing code if they already exist:

- `src/routes/chat.routes.js`
- `src/services/chatFlow.service.js`
- `src/services/model.service.js`
- `src/services/memory.service.js`
- `src/utils/questions.js`
- `src/utils/validateModelOutput.js`

### 1. `questions.js`
Question text per field:
- `project`: "What project are you reporting on today?"
- `discussion`: "What did the team discuss or decide today?"
- `event`: "Was there any event, meeting, or activity today?"
- `work_done`: "What work did you complete today?"
- `outcome`: "What was the outcome of that work?"
- `blockers`: "Did anything block or slow you down?"
- `pending_next`: "What work is still pending or planned next?"

### 2. `chat.routes.js`
`POST /chat/message`

Request:
```json
{
  "userId": "...",
  "teamId": "...",
  "role": "leader/member",
  "message": "...",
  "currentField": "...",
  "draft": {}
}
```

Response:
```json
{
  "draft": {},
  "currentField": "...",
  "botMessage": "...",
  "done": false,
  "needsFollowUp": false,
  "preview": null
}
```

### 3. `chatFlow.service.js` — main logic
- If draft is missing, create an empty draft.
- If `currentField` is missing, choose the first empty field based on role.
- If the user says "skip", skip the current field and move to the next — **do not call the model**.
- Load memory via `memory.service.js`.
- Call `analyzeUserMessage` from `model.service.js`.
- Validate model output.
- Apply `modelOutput.updates` to the draft.
- Support multiple fields being filled from one answer.
- If `needs_follow_up` is true, return the follow-up question instead of advancing.
- Otherwise, find the next missing field.
- If no missing field remains, return `done=true` and `botMessage="[READY_TO_SUMMARIZE]"`.
- **Never save the report here.**

### 4. `memory.service.js`
`getChatMemory(userId, teamId)`:
- Try to fetch the latest previous daily report for that user/team.
- Reuse the existing DB helper/pool if one exists.
- If DB isn't ready, return a safe mock:
```json
{ "lastProject": "", "lastWorkDone": "", "lastPending": "" }
```
- Used to resolve phrases like: "same project", "same work", "that task", "previous work", "yesterday project".

### 5. `model.service.js`
Call the local Ollama API using:
```js
process.env.OLLAMA_URL || "http://localhost:11434/api/generate"
process.env.OLLAMA_MODEL || "qwen3:1.7b"
```

Prompt must instruct the model to:
- Act as the Echo daily report assistant.
- Return only valid JSON, no markdown, no explanation.
- Resolve context words (e.g. "same project") only when memory clearly supports it — use `memory.lastProject` etc. only if available.
- Extract multiple fields if present in one answer.
- Ask a follow-up if the answer is vague.
- Never invent facts or dates.
- Never add fields outside the allowed field list.
- Produce clean, professional, complete text.
- If the answer is clear and unambiguous, confidence should be above 0.8.

If the raw Ollama response includes extra text around the JSON, extract the first JSON object from the response safely rather than failing to parse.

Expected JSON shape:
```json
{
  "updates": {
    "project": "clean text",
    "work_done": "clean text",
    "discussion": "clean text",
    "event": "clean text",
    "outcome": "clean text",
    "blockers": "clean text",
    "pending_next": "clean text"
  },
  "needs_follow_up": false,
  "follow_up_question": "",
  "confidence": 0.9
}
```

On JSON parse failure, return:
```json
{
  "updates": {},
  "needs_follow_up": true,
  "follow_up_question": "I didn't catch that clearly. Can you explain it again?",
  "confidence": 0
}
```

### 6. `validateModelOutput.js`
Validate:
- Output exists.
- `updates` is an object.
- Only allowed fields are accepted (strip anything else).
- Field values must be non-empty strings.
- `confidence` must be a number.
- `confidence` must be `>= 0.55` unless `needs_follow_up` is true.
- If valid `updates` exist but `confidence` came back as 0, set it to 0.75.

Remove invalid fields before applying to the draft.

### 7. Environment Variables
```
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen3:1.7b
```

### 8. Server Wiring
```js
app.use("/chat", chatRoutes)
```

### 9. Final Preview
When `done=true`, return a readable preview object/message. **Do not write to the DB** — saving stays behind the separate Save Report action.

---

## Behavior Examples (must pass)

**1. Context resolution**
Current field: `project`, Memory: `{ lastProject: "Team Management App" }`, User: "same project"
→ `{ "project": "Team Management App" }`

**2. Multi-field extraction**
Current field: `work_done`, User: "completed login page but signup pending"
→
```json
{
  "work_done": "Completed the login page.",
  "pending_next": "Signup page is pending."
}
```

**3. Clear negative answer**
Current field: `blockers`, User: "no blockers"
→ `{ "blockers": "No blockers were reported." }`

**4. Vague answer triggers follow-up**
Current field: `work_done`, User: "backend work"
→ `needs_follow_up=true`, `follow_up_question="What backend work did you complete? Was it API, database, authentication, or Excel export?"`

**5. Skip**
User says "skip" → backend does **not** call the model; moves straight to the next field.

---

## Hard Constraints

- The model never controls saving.
- The model never writes to the database directly.
- The model never decides permissions.
- Backend owns question flow and validation at all times.
- The model is only for language understanding and clean text generation.
- Do not change unrelated files outside the chatbot backend scope.

---

## After Implementing, Report Back

- Files changed
- APIs added
- How to test with curl/Postman — cover at minimum these inputs:
  - "same project"
  - "completed login page but signup pending"
  - "no blockers"
  - "backend work"
  - "skip"
- Any assumptions made
