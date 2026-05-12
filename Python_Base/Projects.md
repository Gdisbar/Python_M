

# 🔹 Project 1: Speech Analytics for ASR & Transcript Clean-up

### **Core Concepts**

* **Mel-Spectrogram vs MFCC**

  * *Mel Spectrogram* → Time–frequency content mapped on human-auditory Mel scale.
  * *MFCCs* → Compressed, decorrelated representation derived from Mel Spectrogram using DCT.

### **Pipeline**

1. **Audio Preprocessing**

   * Split audio into **10s frames** with **1s overlap** (pydub).
   * Detect **long pauses** for speech segmentation.

2. **Speaker Diarization**

   * Used for **mood classification** & **topic detection**.

3. **Feature Extraction**

   * **Filler spotting** → MFCC fingerprints vs 25-entry filler lexicon (Spacy tagging of technical terms).
   * **Pitch analysis** (librosa) → sudden jumps >20Hz → stress indicator.
   * **Spacy + rule-based filters** → identify technical terms, elevated pitch, long pauses → `spacy_tag`.

4. **Modeling**

   * **Mistral-7B** → Topic detection (Problem-Solving, Small Talk, Reference) + timestamp from Whisper → `whisper_tag`.
   * **Roberta-base** → Mood classification (Focused, Frustrated, Idle) + timestamp + tags.

### **Metrics**

* **Word Error Rate (WER)** → weekly 1h sample evaluation.
* **Avg Pause Rate** → pauses during problem solving.
* **Off-task small-talk** → % small-talk per individual.
* **On-task attention** → % problem-solving vs total speech.
* **Topic Accuracy** → F1 score vs human evaluation.

---

# 🔹 Project 2: Customer Segmentation via RMF + ML

### **Problem**

Segment customers based on **Recency, Frequency, Monetary (RFM)** for payment behavior & route confidence-based actions.

### **Approaches**

* **Supervised Classification**

  * **Random Forest** →

    * Finds feature importance.
    * Handles mixed data.
    * Probabilistic scores for confidence-based routing.
    * Each leaf node = distinct payment pattern.
    * Robust to overfitting.

* **Unsupervised Clustering**

  * **k-Means (hard cluster)** → works well for regular payment clients.
  * **DBSCAN (hard cluster + outlier detection)** → identifies irregular patterns.
  * **Gaussian Mixture Model (soft clustering)** →

    * Clients can belong to multiple clusters.
    * Use RF prediction probability for routing.

---

# 🔹 Project 3: AI-Driven Ticket Classification & Routing

### **Problem**

* SOP templates vary but **not updated across teams**.
* **Manual routing issues** → single team lacks full knowledge.
* **Cross-team collaboration** needed for many issues.
* **Escalation not followed** properly at L1.
* **Chatbot underutilized** (business decision for customer experience).

### **Target**

* Remove **dependency on L0**, automate **30% of L1 tasks**.
* Maintain **human-style responses** with **RHLF alignment**.

### **Metrics**

* Classification accuracy.
* First contact resolution rate.
* Avg. time to correct team assignment.
* Reduction in back-and-forth exchanges.

### **Data Preparation**

* **Source**: ServiceNow history → cleaned & structured.
* **Training**:

  * Match description (1st, 2nd levels).
  * Assignment teams order (`int_2nd_multiple`).
* **Evaluation**:

  * Accuracy, resolution time, error analysis (issue, primary/secondary/collab teams).

### **System Workflow**

1. **Rule-based** assignment → if clear match → assign directly.
2. **Model-based** search if no match:

   * Search issue/description.
   * Extract clarifying questions.
   * Analyze answers → narrow to single/multiple teams.
   * Auto-troubleshoot via SOP.
3. **Assignment**:

   * If single team → assign.
   * If multiple → assign to primary + notify secondary teams.

