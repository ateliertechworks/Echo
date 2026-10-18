import { create } from 'zustand';
import { api } from '../api/axiosClient.js';

const loadUser = () => {
  try {
    const raw = localStorage.getItem('tr_user');
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
};

export const useAuth = create((set, get) => ({
  user: loadUser(),
  token: localStorage.getItem('tr_token'),

  setSession(user, token) {
    localStorage.setItem('tr_user', JSON.stringify(user));
    localStorage.setItem('tr_token', token);
    set({ user, token });
  },

  updateUser(patch) {
    const next = { ...get().user, ...patch };
    localStorage.setItem('tr_user', JSON.stringify(next));
    set({ user: next });
  },

  async signin(email, password) {
    const { data } = await api.post('/auth/signin', { email, password });
    get().setSession(data.user, data.token);
    return data.user;
  },

  async signup(username, email, password) {
    const { data } = await api.post('/auth/signup', { username, email, password });
    get().setSession(data.user, data.token);
    return data.user;
  },

  signout() {
    localStorage.removeItem('tr_token');
    localStorage.removeItem('tr_user');
    set({ user: null, token: null });
  },
}));
