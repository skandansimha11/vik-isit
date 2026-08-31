import ChatWidget from "../components/chat/ChatWidget";

export default function ChatbotPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-white">Ask Tarka AI</h1>
        <p className="mt-1 text-sm text-base-400">
          Tarka is the dashboard&rsquo;s analytical policy assistant. Ask about any ministry&rsquo;s KPIs, trends, or how they
          compare, and get framework-grounded answers with evidence and caveats.
        </p>
      </div>
      <ChatWidget
        suggestions={[
          "Which ministry is improving the fastest?",
          "Compare Finance and Railways performance.",
          "What's driving the Ethanol Programme numbers?",
        ]}
      />
    </div>
  );
}
