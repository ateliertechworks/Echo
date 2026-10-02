import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './store/authStore.js';
import AuthPage from './pages/AuthPage.jsx';
import ProfileSetupPage from './pages/ProfileSetupPage.jsx';
import TeamsPage from './pages/TeamsPage.jsx';
import TeamWorkspaceLayout from './pages/TeamWorkspace/TeamWorkspaceLayout.jsx';
import TodaysReportPage from './pages/TeamWorkspace/TodaysReportPage.jsx';
import PastReportsPage from './pages/TeamWorkspace/PastReportsPage.jsx';
import TeamDetailsPage from './pages/TeamWorkspace/TeamDetailsPage.jsx';
import Toaster from './components/Toaster.jsx';

function Protected({ children }) {
  const { token, user } = useAuth();
  if (!token) return <Navigate to="/auth" replace />;
  if (user && user.profile_completed === false && !location.pathname.startsWith('/profile-setup'))
    return <Navigate to="/profile-setup" replace />;
  return children;
}

export default function App() {
  const { token, user } = useAuth();
  return (
    <>
      <Routes>
        <Route path="/auth" element={token ? <Navigate to={user?.profile_completed ? '/teams' : '/profile-setup'} replace /> : <AuthPage />} />
        <Route path="/profile-setup" element={<Protected><ProfileSetupPage /></Protected>} />
        <Route path="/teams" element={<Protected><TeamsPage /></Protected>} />
        <Route path="/teams/:teamId" element={<Protected><TeamWorkspaceLayout /></Protected>}>
          <Route index element={<TodaysReportPage />} />
          <Route path="past" element={<PastReportsPage />} />
          <Route path="details" element={<TeamDetailsPage />} />
        </Route>
        <Route path="*" element={<Navigate to={token ? '/teams' : '/auth'} replace />} />
      </Routes>
      <Toaster />
    </>
  );
}
