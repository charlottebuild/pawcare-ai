import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { PawCareApp } from "./PawCareApp";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <PawCareApp />
  </React.StrictMode>,
);
