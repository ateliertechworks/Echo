import { useOutletContext } from 'react-router-dom';
import ChatPanel from '../../components/ChatPanel.jsx';
import { useAuth } from '../../store/authStore.js';

export default function TodaysReportPage() {
  const { team } = useOutletContext();
  const { user } = useAuth();
  if (!team) return <div className="skeleton" style={{ height: 500 }} />;
  return <ChatPanel team={team} user={user} />;
}
