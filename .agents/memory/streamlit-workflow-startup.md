---
name: Streamlit workflow startup
description: Replit-specific Streamlit startup behavior for configured webview workflows.
---

Use headless mode and disable usage statistics in the Streamlit workflow command.

**Why:** Without headless mode, Streamlit can wait for its optional first-run email prompt on workflow stdin, so the app never opens its configured port.

**How to apply:** For a Replit Streamlit webview on port 5000, include `--server.headless=true --browser.gatherUsageStats=false`, then verify the workflow log reports the server listening on `0.0.0.0:5000`.
