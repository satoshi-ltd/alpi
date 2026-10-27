import React from "react";
import ReactDOM from "react-dom/client";
import "../styles/fonts.css";
import "../styles/tokens.css";
import "../styles/reset.css";
import "../styles/design-system.css";
import { applyStored } from "../lib/theme.js";
import TrayApp from "./TrayApp.jsx";

applyStored();
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <TrayApp />
  </React.StrictMode>,
);
