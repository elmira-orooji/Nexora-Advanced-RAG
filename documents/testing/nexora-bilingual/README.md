# Nexora bilingual synthetic test data

All organizations, people, policies and figures are fictional. These are independent datasets, not translations; keep them in separate knowledge sets to avoid conflicting answers.

Each language contains five UTF-8 TXT documents and ten reference questions: five factual lookups, two combination/counting questions, one cross-document question, and two unanswerable questions. Only upload the five TXT documents. Do not upload questions.json: it contains reference answers and would contaminate retrieval.

Create one knowledge set per language, upload its TXT files, wait until all are indexed, then ask the questions in questions.json. Check factual accuracy, correct document citations, cross-document retrieval, numeric reasoning and refusal for missing information. Expected document IDs are the TXT filename stems. They are not Nexora database IDs. Accept equivalent wording for supported answers. For missing answers, the interface language determines the displayed message. This small smoke-test dataset is not a validated benchmark or a measure of production quality.
