import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/axiosClient.js';
import { useToast } from '../hooks/useToast.js';
import './ChatPanel.css';

const READY = '[READY_TO_SUMMARIZE]';
const MODEL_TIMEOUT = 120000;

const FIELD_LABELS = {
  project: 'Project',
  discussion: 'Team discussion',
  event: 'Event / meeting',
  work_done: 'Work done',
  outcome: 'Outcome',
  blockers: 'Blockers',
  pending_next: 'Pending / next',
};
const FIELD_ICONS = {
  project: '📁', discussion: '💬', event: '📅', work_done: '🛠️', outcome: '🎯', blockers: '🚧', pending_next: '⏭️',
};
const QUESTIONS = {
  project: 'What project are you reporting on today?',
  discussion: 'What did the team discuss or decide today?',
  event: 'Was there any event, meeting, or activity today?',
  work_done: 'What work did you complete today?',
  outcome: 'What was the outcome of that work?',
  blockers: 'Did anything block or slow you down?',
  pending_next: 'What work is still pending or planned next?',
};
const fieldsFor = (role) => (role === 'leader'
  ? ['project', 'discussion', 'event', 'work_done', 'outcome', 'blockers', 'pending_next']
  : ['project', 'work_done', 'outcome', 'blockers', 'pending_next']);

function todayIso() { return new Date().toISOString().slice(0, 10); }

function greeting(name) {
  const h = new Date().getHours();
  const part = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  return `${part}${name ? `, ${name}` : ''}! 👋 I'm Echo. I'll ask a few quick questions and turn your answers into a clean report. Answer in your own words — typos are fine, I'll tidy them up.`;
}

const READY_LINES = [
  "That's everything! ✨ Here's your report preview — tweak anything you like, then hit Save Report.",
  'All set! 🎉 Review the draft below. You can click any field to edit it, or just tell me what to change.',
];

const loadState = (key) => { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; } };
const storeState = (key, v) => { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* ignore */ } };
const dropState = (key) => { try { localStorage.removeItem(key); } catch { /* ignore */ } };

export default function ChatPanel({ team, user }) {
  const reportDate = todayIso();
  const storageKey = `echo_chat_v1_${user?.id || 'me'}_${team?.id}_${reportDate}`;
  const toast = useToast();

  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState({});
  const [currentField, setCurrentField] = useState(null);
  const [role, setRole] = useState(team?.role || 'member');
  const [done, setDone] = useState(false);
  const [preview, setPreview] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [phase, setPhase] = useState('loading'); // loading | chat | saved | error
  const [busy, setBusy] = useState(false);
  const [thinkingFor, setThinkingFor] = useState(0);
  const [input, setInput] = useState('');
  const [flash, setFlash] = useState([]);
  const [model, setModel] = useState(null);
  const [showDraft, setShowDraft] = useState(false);
  const [listening, setListening] = useState(false);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);
  const fields = useMemo(() => fieldsFor(role), [role]);

  // Restore today's conversation or start a new one.
  useEffect(() => {
    if (!team) return;
    api.get('/chat/status').then(({ data }) => setModel(data.model || null)).catch(() => setModel(null));
    const saved = loadState(storageKey);
    if (saved?.messages?.length) {
      setMessages(saved.messages.map((m) => ({ ...m, animate: false })));
      setDraft(saved.draft || {});
      setCurrentField(saved.currentField || null);
      setRole(saved.role || team.role || 'member');
      setDone(!!saved.done);
      setPreview(saved.preview || null);
      setSuggestions(saved.suggestions || []);
      setPhase(saved.phase === 'saved' ? 'saved' : 'chat');
    } else {
      start();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [team?.id]);

  useEffect(() => {
    if (phase === 'loading' || phase === 'error') return;
    storeState(storageKey, {
      messages: messages.map(({ animate, ...m }) => m), draft, currentField, role, done, preview, suggestions, phase,
    });
  }, [messages, draft, currentField, role, done, preview, suggestions, phase, storageKey]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy, preview]);

  useEffect(() => {
    if (!busy) { setThinkingFor(0); return undefined; }
    const t0 = Date.now();
    const id = setInterval(() => setThinkingFor(Math.floor((Date.now() - t0) / 1000)), 500);
    return () => clearInterval(id);
  }, [busy]);

  useEffect(() => {
    if (!flash.length) return undefined;
    const id = setTimeout(() => setFlash([]), 1800);
    return () => clearTimeout(id);
  }, [flash]);

  const push = (msg) => setMessages((m) => [...m, { id: `${Date.now()}-${Math.random()}`, animate: true, ...msg }]);

  const applyResponse = (data, { quiet = false } = {}) => {
    if (data.role) setRole(data.role);
    setDraft(data.draft || {});
    setCurrentField(data.currentField || null);
    setSuggestions(data.suggestions || []);
    if (typeof data.modelOnline === 'boolean' && model) setModel((m) => ({ ...m, online: data.modelOnline }));
    if (data.captured?.length) setFlash(data.captured.map((c) => c.field));

    if (data.done) {
      setDone(true);
      setPreview(data.preview);
      if (data.botMessage === READY) {
        if (!quiet) {
          push({
            from: 'bot',
            content: data.captured?.length && done
              ? `Updated ${data.captured.map((c) => c.label).join(', ')}. ✅ The preview below is refreshed.`
              : READY_LINES[Math.floor(Math.random() * READY_LINES.length)],
            captured: done ? [] : data.captured,
          });
        }
      } else {
        push({ from: 'bot', content: data.botMessage, followUp: true });
      }
      return;
    }
    setDone(false);
    setPreview(null);
    push({
      from: 'bot',
      content: data.botMessage,
      captured: data.captured,
      followUp: data.needsFollowUp,
      field: data.currentField,
    });
  };

  const callChat = async (body) => {
    const { data } = await api.post('/chat/message', { teamId: team.id, ...body }, { timeout: MODEL_TIMEOUT });
    return data;
  };

  async function start() {
    setPhase('loading');
    setBusy(true);
    try {
      const data = await callChat({ message: '', draft: {}, currentField: null });
      setMessages([{ id: 'hello', from: 'bot', content: greeting(user?.username?.split(' ')[0]), animate: true }]);
      setPhase('chat');
      applyResponse(data);
    } catch (e) {
      toast(e.response?.data?.error || e.message, 'error');
      setPhase('error');
    } finally { setBusy(false); }
  }

  const send = async (text, { display } = {}) => {
    const message = (text ?? input).trim();
    if (!message || busy || phase !== 'chat') return;
    setInput('');
    push({ from: 'user', content: display || message, skipped: /^skip$/i.test(message) });
    setBusy(true);
    try {
      const data = await callChat({ message, draft, currentField: done ? null : currentField });
      applyResponse(data);
    } catch (e) {
      const msg = e.code === 'ECONNABORTED' ? 'The model took too long to answer. Please try again.' : (e.response?.data?.error || e.message);
      push({ from: 'bot', content: `⚠️ ${msg}`, error: true, retry: message });
    } finally {
      setBusy(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  };

  const skip = () => send('skip', { display: 'Skipped' });

  // Drop the failed exchange (user message + error) and send it again.
  const retry = (errorMsg) => {
    setMessages((all) => {
      const idx = all.findIndex((x) => x.id === errorMsg.id);
      return idx > 0 ? all.slice(0, idx - 1) : all;
    });
    send(errorMsg.retry);
  };

  // Jump back to any question from the progress bar.
  const revisit = (field) => {
    if (busy || phase !== 'chat') return;
    setCurrentField(field);
    setDone(false);
    setPreview(null);
    setSuggestions([]);
    push({
      from: 'bot',
      content: draft[field]
        ? `Sure, let's redo ${FIELD_LABELS[field].toLowerCase()}. Right now it says: “${draft[field]}”\n\n${QUESTIONS[field]}`
        : QUESTIONS[field],
      field,
    });
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  // Inline edit in the preview: the backend rebuilds the preview from the new draft.
  const saveInlineEdit = async (field, value) => {
    const next = { ...draft, [field]: value.trim(), _skipped: (draft._skipped || []).filter((f) => f !== field || !value.trim()) };
    if (!value.trim() && !next._skipped.includes(field)) next._skipped.push(field);
    setBusy(true);
    try {
      const data = await callChat({ message: '', draft: next, currentField: null });
      applyResponse(data, { quiet: true });
      setFlash([field]);
    } catch (e) {
      toast(e.response?.data?.error || e.message, 'error');
    } finally { setBusy(false); }
  };

  const saveReport = async () => {
    if (!preview?.structured) return;
    setBusy(true);
    try {
      const { data } = await api.post('/chat/save', { team_id: team.id, report_date: reportDate, structured: preview.structured });
      toast(data.updated ? "Today's report updated" : 'Report saved', 'success');
      setPhase('saved');
      push({ from: 'bot', content: "Saved! 🙌 Your report is now with the team. Have a great rest of your day." });
    } catch (e) { toast(e.response?.data?.error || e.message, 'error'); }
    finally { setBusy(false); }
  };

  const clearChat = async () => {
    if (!confirm("Clear today's conversation and start over? Your saved report stays unchanged until you click Save Report again.")) return;
    dropState(storageKey);
    setMessages([]); setDraft({}); setCurrentField(null); setDone(false); setPreview(null); setSuggestions([]);
    api.post('/chat/reset', { team_id: team.id, report_date: reportDate }).catch(() => {});
    await start();
  };

  const editAfterSave = () => {
    setPhase('chat');
    push({ from: 'bot', content: 'No problem — edit the preview or tell me what to change, then save again.' });
  };

  // Voice input via the browser's speech recognition, when available.
  const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
  const toggleMic = () => {
    if (!SpeechRecognition) return;
    if (listening) { recognitionRef.current?.stop(); return; }
    const rec = new SpeechRecognition();
    rec.lang = 'en-US';
    rec.interimResults = true;
    rec.onresult = (ev) => setInput(Array.from(ev.results).map((r) => r[0].transcript).join(' '));
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  };

  if (!team) return null;

  if (phase === 'error') {
    return (
      <div className="chat-panel">
        <div className="chat-empty">
          <div style={{ fontSize: 40 }}>⚠️</div>
          <h3>Couldn't start Echo</h3>
          <p style={{ color: 'var(--color-text-secondary)', maxWidth: 460 }}>
            The report assistant couldn't reach the server. Check that the backend is running, then retry.
          </p>
          <button className="btn btn-secondary" onClick={start}>Retry</button>
        </div>
      </div>
    );
  }

  const filledCount = fields.filter((f) => draft[f]).length;
  const answeredCount = fields.filter((f) => draft[f] || draft._skipped?.includes(f)).length;
  const pct = Math.round((answeredCount / fields.length) * 100);
  const lastBotIndex = messages.map((m) => m.from).lastIndexOf('bot');
  const placeholder = phase === 'saved' ? 'Report saved for today.'
    : done ? 'Tell me what to change, e.g. "blockers: waiting on API keys"'
    : currentField ? `${FIELD_LABELS[currentField]} — type your answer…` : 'Type your reply…';

  return (
    <div className="chat-panel echo">
      <div className="chat-header">
        <div className="chat-header-info">
          <div className={`chat-bot-avatar ${busy ? 'pulsing' : ''}`}>🤖</div>
          <div>
            <div className="echo-title">
              Echo <span className="echo-subtitle">· Today's Report</span>
            </div>
            <div className="echo-meta">
              <span className={`model-pill ${model?.online ? 'on' : model ? 'off' : ''}`}>
                <i />{model ? (model.online ? model.model : 'model offline') : 'checking…'}
              </span>
              <span>{role === 'leader' ? 'Leader flow' : 'Member flow'}</span>
              <span>{new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
            </div>
          </div>
        </div>
        <div className="echo-header-actions">
          <button className="btn btn-ghost draft-toggle" onClick={() => setShowDraft((s) => !s)}>
            📝 {filledCount}/{fields.length}
          </button>
          <button className="btn btn-ghost" onClick={clearChat} disabled={busy}>Start over</button>
        </div>
      </div>

      <div className="echo-progress">
        <div className="echo-progress-bar"><span style={{ width: `${pct}%` }} /></div>
        <div className="echo-steps">
          {fields.map((f) => {
            const status = draft[f] ? 'filled' : draft._skipped?.includes(f) ? 'skipped' : f === currentField && !done ? 'current' : 'pending';
            return (
              <button
                key={f}
                type="button"
                className={`echo-step ${status} ${flash.includes(f) ? 'flash' : ''}`}
                onClick={() => revisit(f)}
                disabled={busy || phase !== 'chat' || status === 'pending'}
                title={draft[f] || (status === 'skipped' ? 'Skipped — click to answer' : QUESTIONS[f])}
              >
                <span className="echo-step-icon">{status === 'filled' ? '✓' : status === 'skipped' ? '–' : FIELD_ICONS[f]}</span>
                {FIELD_LABELS[f]}
              </button>
            );
          })}
        </div>
      </div>

      <div className="echo-body">
        <div className="chat-messages">
          {phase === 'loading' && !messages.length && (
            <div className="msg-row bot">
              <div className="msg-avatar">🤖</div>
              <div className="msg bot typing"><span /><span /><span /></div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={m.id || i} className={`msg-row ${m.from}`}>
              {m.from === 'bot' && <div className="msg-avatar">🤖</div>}
              <div className={`msg ${m.from} ${m.skipped ? 'skipped' : ''} ${m.followUp ? 'follow-up' : ''} ${m.error ? 'error' : ''}`}>
                {m.followUp && m.from === 'bot' && <div className="msg-tag">Quick follow-up</div>}
                {m.captured?.length > 0 && (
                  <div className="captured">
                    {m.captured.map((c) => (
                      <span key={c.field} className="captured-chip" title={c.value}>✓ {c.label}</span>
                    ))}
                  </div>
                )}
                <div className="msg-content">
                  {m.from === 'bot' && m.animate && i === lastBotIndex ? <Typewriter text={m.content} onTick={() => bottomRef.current?.scrollIntoView({ block: 'end' })} /> : m.content}
                </div>
                {m.retry && (
                  <button className="chip-option small" onClick={() => retry(m)} disabled={busy}>
                    ↻ Retry
                  </button>
                )}
              </div>
            </div>
          ))}

          {busy && phase !== 'loading' && (
            <div className="msg-row bot">
              <div className="msg-avatar">🤖</div>
              <div className="msg bot typing">
                <span /><span /><span />
                {thinkingFor >= 2 && <em className="thinking-label">Echo is thinking… {thinkingFor}s</em>}
              </div>
            </div>
          )}

          {done && preview && (
            <PreviewCard
              preview={preview}
              flash={flash}
              busy={busy}
              saved={phase === 'saved'}
              onEdit={saveInlineEdit}
              onSave={saveReport}
              onEditAfterSave={editAfterSave}
            />
          )}

          <div ref={bottomRef} />
        </div>

        <aside className={`echo-draft ${showDraft ? 'open' : ''}`}>
          <div className="echo-draft-head">
            <span>Live draft</span>
            <button className="btn btn-ghost draft-close" onClick={() => setShowDraft(false)}>✕</button>
          </div>
          {fields.map((f) => (
            <div key={f} className={`echo-draft-item ${draft[f] ? 'filled' : ''} ${flash.includes(f) ? 'flash' : ''} ${f === currentField && !done ? 'current' : ''}`}>
              <div className="echo-draft-label">{FIELD_ICONS[f]} {FIELD_LABELS[f]}</div>
              <div className="echo-draft-value">
                {draft[f] || <span className="muted">{draft._skipped?.includes(f) ? 'Skipped' : f === currentField && !done ? 'Answering now…' : 'Waiting…'}</span>}
              </div>
            </div>
          ))}
        </aside>
      </div>

      {phase === 'chat' && !busy && suggestions.length > 0 && (
        <div className="echo-suggestions">
          {suggestions.map((s) => (
            <button key={s.value} className="chip-option" onClick={() => send(s.value, { display: s.label.replace(/^Same project · /, 'Same project') })}>
              {s.label}
            </button>
          ))}
        </div>
      )}

      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input
          ref={inputRef}
          className="input"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy || phase !== 'chat'}
          autoFocus
        />
        {SpeechRecognition && phase === 'chat' && (
          <button type="button" className={`btn btn-secondary mic ${listening ? 'live' : ''}`} onClick={toggleMic} disabled={busy} title="Speak your answer">
            🎙️
          </button>
        )}
        {phase === 'chat' && !done && (
          <button type="button" className="btn btn-secondary" onClick={skip} disabled={busy} title="Skip this question">
            Skip
          </button>
        )}
        <button className="btn btn-primary" type="submit" disabled={busy || phase !== 'chat' || !input.trim()}>
          {busy ? <span className="spinner" /> : 'Send'}
        </button>
      </form>
    </div>
  );
}

function Typewriter({ text, onTick }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const step = Math.max(1, Math.round(text.length / 60));
    const id = setInterval(() => {
      setN((v) => {
        const next = Math.min(text.length, v + step);
        if (next >= text.length) clearInterval(id);
        return next;
      });
      onTick?.();
    }, 16);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  return <>{text.slice(0, n)}{n < text.length && <span className="caret" />}</>;
}

function PreviewCard({ preview, flash, busy, saved, onEdit, onSave, onEditAfterSave }) {
  const [editing, setEditing] = useState(null);
  const [value, setValue] = useState('');

  const begin = (f) => { if (busy || saved) return; setEditing(f.field); setValue(f.value); };
  const commit = async () => { const field = editing; setEditing(null); await onEdit(field, value); };

  return (
    <div className="summary-card echo-preview">
      <div className="summary-title">📋 Report preview <span className="preview-hint">{saved ? 'Saved' : 'Click any field to edit'}</span></div>
      {preview.fields.map((f) => (
        <div key={f.field} className={`summary-row ${flash.includes(f.field) ? 'flash' : ''}`}>
          <div className="summary-label">{FIELD_ICONS[f.field]} {f.label}</div>
          {editing === f.field ? (
            <div className="inline-edit">
              <textarea
                className="input"
                value={value}
                autoFocus
                rows={Math.min(5, Math.max(2, Math.ceil(value.length / 60)))}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commit(); }
                  if (e.key === 'Escape') setEditing(null);
                }}
              />
              <div className="inline-edit-actions">
                <button className="btn btn-primary" onClick={commit} disabled={busy}>Save</button>
                <button className="btn btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
              </div>
            </div>
          ) : (
            <button type="button" className={`summary-value editable ${saved ? 'locked' : ''}`} onClick={() => begin(f)}>
              {f.value || <span className="muted">(skipped — click to add)</span>}
              {!saved && <span className="edit-pencil">✏️</span>}
            </button>
          )}
        </div>
      ))}
      <div className="summary-narrative">
        <div className="summary-narrative-label">Summary</div>
        <div>{preview.narrative || '—'}</div>
      </div>
      <div className="summary-actions">
        {saved ? (
          <button className="btn btn-secondary" onClick={onEditAfterSave}>✏️ Make changes</button>
        ) : (
          <button className="btn btn-primary" onClick={onSave} disabled={busy}>
            {busy ? <span className="spinner" /> : '💾 Save Report'}
          </button>
        )}
      </div>
    </div>
  );
}
