import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import AppToaster from "./components/AppToaster";
import "./i18n";
import "./index.css";
import "./styles/dropdowns.css";
import App from "./App";

createRoot(
  document.getElementById("root")!
).render(
  <StrictMode>
    <App />

    <AppToaster />
  </StrictMode>
);