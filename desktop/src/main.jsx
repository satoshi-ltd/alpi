import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/tokens.css";
import "./styles/reset.css";
import "./styles/design-system.css";
import App from "./App.jsx";
import ErrorBoundary from "./primitives/ErrorBoundary.jsx";
import { NotificationProvider } from "./primitives/Notification.jsx";
import { applyStored as applyStoredTheme } from "./lib/theme.js";
import { installZoomShortcuts } from "./lib/zoom.js";

applyStoredTheme();
installZoomShortcuts();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <NotificationProvider>
        <App />
      </NotificationProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
