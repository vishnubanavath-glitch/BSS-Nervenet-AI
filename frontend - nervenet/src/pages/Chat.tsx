import React, { useState } from "react";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { SettingsModal } from "@/components/settings/SettingsModal";

export const Chat: React.FC = () => {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Sidebar navigation */}
      <Sidebar onOpenSettings={() => setShowSettings(true)} />
      
      {/* Active Conversation Container */}
      <ChatContainer />

      {/* User Settings Overlay */}
      {showSettings && (
        <SettingsModal onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
};
