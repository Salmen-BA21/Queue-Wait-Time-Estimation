import { BrowserRouter, Routes, Route } from 'react-router-dom';
import {
  LandingPage,
  DashboardPage,
  AnalyticsPage,
  ZoneEditorPage,
  HeatmapPage,
  SettingsPage,
  LoginPage,
} from './pages';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/zone-editor" element={<ZoneEditorPage />} />
        <Route path="/heatmap" element={<HeatmapPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
