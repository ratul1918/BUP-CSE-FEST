# GridWise LLM — 3-Minute Video Production Guide & Voiceover Script (Google Vids Ready)

This guide is designed for creating the **3-Minute Architecture & Solution Video** (required tie-breaker) using **Google Vids** (or any video tool / screen recorder).

---

## 🚀 Quickstart: How to Produce the Video in Google Vids

1. **Open Google Vids**: Go to [vids.google.com](https://vids.google.com) and click **"Create New Video"**.
2. **Open the Slides**:
   - Double-click [`video_production_pack/slides.html`](file:///Users/rafiurrahman/Downloads/BUP_CSE_FEST/video_production_pack/slides.html) to open in your browser (Chrome/Safari).
   - Press **`f`** or click **"Fullscreen"** at the bottom.
   - Use the **Right Arrow key** ($\rightarrow$) to change slides.
3. **Capture / Import Slides into Google Vids**:
   - You can either take screenshots of each slide (Slide 1 to 5) and upload them as scenes in Google Vids, OR record your browser tab directly while advancing the slides.
4. **Add Voiceover**:
   - In Google Vids, for each scene, click **"Add voiceover"** $\to$ **"Text-to-speech"** (choose a professional voice like *Alloy*, *Nova*, or *Standard English*), or click **"Record your own voice"**.
   - Copy-paste the exact scripts below for each scene!

---

## ⏱️ Timeline & Scene Overview

| Scene | Slide | Title | Duration | Word Count |
|:-----:|:-----:|:------|:--------:|:----------:|
| **Scene 1** | Slide 1 | Introduction & Executive Overview | 0:00 – 0:35 (35s) | 80 words |
| **Scene 2** | Slide 2 | Problem Understanding & Microgrid Rules | 0:35 – 0:40 (35s) | 85 words |
| **Scene 3** | Slide 3 | 4-Stage Architecture Pipeline | 1:10 – 1:45 (35s) | 88 words |
| **Scene 4** | Slide 4 | 2-Stage LP Optimizer & Replay Invariants | 1:45 – 2:20 (35s) | 85 words |
| **Scene 5** | Slide 5 | Live Cloud Deployment, Verification & Conclusion | 2:20 – 2:50 (30s) | 72 words |
| **Total** | | | **~2 min 45 sec** | **~410 words** |

*(Leaves a 15-second safety buffer well below the 3:00 minute strict cap!)*

---

## 🎬 Scene-by-Scene Voiceover Scripts

### 📍 Scene 1: Introduction & Executive Overview
- **Duration**: `0:00 – 0:35` (35 seconds)
- **Visual**: **Slide 1** (*GridWise LLM Title Slide*)
- **Google Vids Voiceover Script (Copy & Paste)**:
> "Hello judges. Welcome to our presentation of GridWise LLM for the BUP CSE Fest 2026 Hackathon.
> 
> Our mission is to build an autonomous, reliable, and mathematically optimal energy scheduling API for the BUP smart campus.
> 
> Our system combines generative language models, deterministic safety guardrails, and two-stage linear programming to convert informal operator notes into globally cost-minimal 24-hour microgrid schedules in under four seconds."

---

### 📍 Scene 2: Problem Understanding & Microgrid Rules
- **Duration**: `0:35 – 1:10` (35 seconds)
- **Visual**: **Slide 2** (*The Smart Campus Energy Challenge*)
- **Google Vids Voiceover Script (Copy & Paste)**:
> "In a smart campus, electricity demand, solar generation, and grid tariffs fluctuate hourly. In addition, human campus operators issue informal natural-language notes—such as midday solar panel cleaning, temporary feeder import caps, or battery maintenance windows.
> 
> A key challenge is distinguishing actionable instructions from realistic distractors, like cafeteria notices, and converting time windows strictly with start-inclusive, end-exclusive hours.
> 
> Simultaneously, the dispatch schedule must never violate physical battery limits, hourly energy balance, or end-of-day battery neutrality."

---

### 📍 Scene 3: Four-Stage System Architecture
- **Duration**: `1:10 – 1:45` (35 seconds)
- **Visual**: **Slide 3** (*Four-Stage Decoupled Pipeline*)
- **Google Vids Voiceover Script (Copy & Paste)**:
> "To guarantee correctness without hallucinations, we designed a decoupled four-stage pipeline.
> 
> In stage one, a Google Gemini 2.5 Flash model parses operator notes into strict JSON directives with retry logic and deterministic NLP fallback.
> 
> In stage two, deterministic guardrails sanitize the output: sorting hours from 0 to 23, clamping solar factors, and enforcing no-op invariants.
> 
> In stage three, a two-stage HiGHS linear programming solver computes the optimal dispatches.
> 
> Finally, an independent replay validator verifies every physical constraint before returning the response."

---

### 📍 Scene 4: 2-Stage LP Optimizer & Replay Invariants
- **Duration**: `1:45 – 2:20` (35 seconds)
- **Visual**: **Slide 4** (*2-Stage Linear Program & Invariants*)
- **Google Vids Voiceover Script (Copy & Paste)**:
> "Our mathematical engine is built with SciPy's HiGHS linear programming solver, using 120 continuous decision variables.
> 
> Stage one minimizes total grid electricity cost against varying hourly tariffs.
> 
> Stage two locks that minimal cost and minimizes the maximum hourly grid import, effectively smoothing peak demand and protecting electrical transformers.
> 
> By utilizing mathematical optimization rather than generative models for energy numbers, we guarantee zero energy balance violations, mutual exclusivity of charging and discharging, and an ultra-fast execution time of under five milliseconds."

---

### 📍 Scene 5: Live Cloud Deployment, Verification & Conclusion
- **Duration**: `2:20 – 2:50` (30 seconds)
- **Visual**: **Slide 5** (*100% Verification & Live Cloud Deployment*)
- **Google Vids Voiceover Script (Copy & Paste)**:
> "Our system has been thoroughly validated against all ten official public sample cases, achieving a 100% pass rate with zero BDT difference.
> 
> The service is currently live and reachable on Render at `bup-cse-fest.onrender.com`, exposing GET health and POST optimize-energy.
> 
> Furthermore, a containerized fallback image is verified and pullable on Docker Hub as `ratul1918/gridwise-llm:v1.0`.
> 
> GridWise LLM delivers intelligence, mathematical precision, and production-grade reliability. Thank you."

---

## 📤 Submission Checklist for Video

- [ ] Video length is strictly **under 3 minutes** (the script above is ~2:45).
- [ ] Export as **MP4** or get a shareable **Google Drive / YouTube (Unlisted) link**.
- [ ] Ensure permissions are set to **"Anyone with the link can view"**.
- [ ] Paste the video link into the BUP CSE Fest submission form along with:
  - Base URL: `https://bup-cse-fest.onrender.com`
  - GitHub Repo: `https://github.com/ratul1918/BUP-CSE-FEST`
  - Docker Image: `ratul1918/gridwise-llm:v1.0`
