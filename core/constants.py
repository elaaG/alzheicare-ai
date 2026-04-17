SUPPORTED_AUDIO_TYPES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/m4a",
    "audio/x-m4a",
    "video/webm",       
    "application/octet-stream",
}

SUPPORTED_AUDIO_EXTENSIONS = {".webm", ".mp4", ".mp3", ".wav", ".ogg", ".m4a"}

VALID_ROLES = {"caregiver", "doctor", "admin"}
VALID_STAGES = {0, 1, 2}
VALID_LANGUAGE_CODES = {"fr", "ar", "en", "es", "de", "it", "pt"}

REDIS_HISTORY_PREFIX = "assistant:history:"
REDIS_RATE_PREFIX    = "rate:assistant:"
REDIS_HISTORY_TTL    = 7 * 24 * 3600   # this means  7 days in seconds
REDIS_RATE_TTL       = 60              # a one minute window

SEARCH_TRIGGER_KEYWORDS = {
    "latest", "recent", "new treatment", "new study", "2024", "2025", "2026",
    "research", "clinical trial", "fda approved", "fda", "approved",
    "published", "journal", "evidence",

    "récent", "récente", "nouveau", "nouvelle", "traitement récent",
    "étude récente", "recherche", "essai clinique", "approuvé",
    "publié", "revue", "preuve",
}

SSE_DONE_SIGNAL  = "[DONE]"
SSE_ERROR_SIGNAL = "[ERROR]"

CORRELATION_ID_HEADER = "X-Correlation-ID"