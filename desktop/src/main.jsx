import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/tokens.css";
import "./styles/reset.css";
import "./styles/design-system.css";
import App from "./App.jsx";
import { NotificationProvider } from "./primitives/Notification.jsx";
import { applyStored as applyStoredTheme } from "./lib/theme.js";

applyStoredTheme();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <NotificationProvider>
      <App />
    </NotificationProvider>
  </React.StrictMode>,
);
