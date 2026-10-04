"use client";

import { useEffect } from "react";

const WARNING = [
  "%cSTOP!%c",
  "",
  "This browser feature is intended for developers.",
  "",
  "Do not paste or run code here if someone told you to do so.",
  "Code run in this console can act with the permissions of your signed-in COMPASS session and may expose data available to your account.",
  "",
  "COMPASS will never ask you to paste code into Developer Tools.",
  "",
  "University of Camarines Norte",
  "Guidance and Counseling Office",
  "COMPASS",
  "",
  "Opened this intentionally? Hello, developer.",
].join("\n");

// Console styles cannot resolve page CSS tokens; use the canonical brand maroon.
const HEADING_STYLE = "color: #6b1f2a; font-size: 40px; font-weight: 800;";
const BODY_STYLE = "font-size: 13px; font-weight: normal;";
let hasEmitted = false;

// Self-XSS awareness only; this is not a DevTools restriction or a security boundary.
export function DeveloperConsoleSafetyWarning() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || hasEmitted) return;
    // Retain this guard across remounts/effect replays, but never across page loads.
    hasEmitted = true;
    try {
      console.log(WARNING, HEADING_STYLE, BODY_STYLE);
    } catch {
      // Informational output must never interfere with application startup.
    }
  }, []);

  return null;
}
