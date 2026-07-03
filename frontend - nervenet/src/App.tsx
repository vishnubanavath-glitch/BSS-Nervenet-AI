import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Login } from "@/pages/Login";
import { Register } from "@/pages/Register";
import { Chat } from "@/pages/Chat";
import { Admin } from "@/pages/Admin";
import { RouteGuard } from "@/components/common/RouteGuard";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        
        {/* Protected Customer Routes */}
        <Route
          path="/"
          element={
            <RouteGuard>
              <Chat />
            </RouteGuard>
          }
        />
        
        {/* Protected Administrator Dashboard */}
        <Route
          path="/admin"
          element={
            <RouteGuard requireAdmin>
              <Admin />
            </RouteGuard>
          }
        />

        {/* Fallback redirection */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};
