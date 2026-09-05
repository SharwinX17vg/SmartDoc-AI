The popup is the SmartDoc extension client. It calls the batch document endpoint for multi-PDF ingestion, lists and scopes indexed documents, and calls `/api/v1/query` for casual conversation, grounded questions, summaries, comparisons, and `/keywords`, `/find`, and `/explain` commands.

Answer actions use the Web Clipboard API, Web Share API when available, and a text download fallback. Share links are created by the backend and contain only the selected answer/source payload.
