import { Route, Routes } from "react-router-dom";
import TopNav from "./components/TopNav";
import Footer from "./components/Footer";
import ErrorBoundary from "./components/ErrorBoundary";
import LandingPage from "./pages/LandingPage";
import SummaryPage from "./pages/SummaryPage";
import MinistryDetailPage from "./pages/MinistryDetailPage";
import ChatbotPage from "./pages/ChatbotPage";

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-base-900">
      <TopNav />
      <main className="flex-1">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/summary" element={<SummaryPage />} />
            <Route path="/ministries/:ministryId" element={<MinistryDetailPage />} />
            <Route path="/chatbot" element={<ChatbotPage />} />
            <Route path="*" element={<LandingPage />} />
          </Routes>
        </ErrorBoundary>
      </main>
      <Footer />
    </div>
  );
}
