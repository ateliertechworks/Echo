import { create } from 'zustand';

export const useToastStore = create((set, get) => ({
  toasts: [],
  push(message, kind = 'success') {
    const id = Math.random().toString(36).slice(2);
    set({ toasts: [...get().toasts, { id, message, kind }] });
    setTimeout(() => {
      set({ toasts: get().toasts.filter((t) => t.id !== id) });
    }, 3500);
  },
  remove(id) { set({ toasts: get().toasts.filter((t) => t.id !== id) }); },
}));

export function useToast() {
  return useToastStore((s) => s.push);
}
