import { useToastStore } from '../hooks/useToast.js';

export default function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>{t.message}</div>
      ))}
    </div>
  );
}
