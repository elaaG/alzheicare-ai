from fastapi import HTTPException


class AlzheiCareException(HTTPException):
    def __init__(self, status_code: int, detail: str, internal: str = ""):
        super().__init__(status_code=status_code, detail=detail)
        self.internal = internal  


class InvalidTokenError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=401,
            detail="Token d'authentification invalide ou expiré.",
            internal=internal,
        )

class InsufficientPermissionsError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=403,
            detail="Vous n'avez pas les permissions nécessaires.",
            internal=internal,
        )



class LLMUnavailableError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=503,
            detail="Le service IA est temporairement indisponible. Réessayez dans quelques secondes.",
            internal=internal,
        )

class LLMRateLimitError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=429,
            detail="Trop de requêtes. Veuillez patienter un moment.",
            internal=internal,
        )

class LLMTimeoutError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=504,
            detail="Le service IA met trop de temps à répondre. Réessayez.",
            internal=internal,
        )



class AudioTooLargeError(AlzheiCareException):
    def __init__(self, max_mb: int):
        super().__init__(
            status_code=413,
            detail=f"Fichier audio trop volumineux. Maximum autorisé: {max_mb}MB.",
        )

class InvalidAudioFormatError(AlzheiCareException):
    def __init__(self, received: str = ""):
        super().__init__(
            status_code=422,
            detail="Format audio non supporté. Utilisez: webm, mp3, wav, m4a, ogg.",
            internal=f"Received content_type: {received}",
        )

class TranscriptionError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=503,
            detail="Impossible de transcrire l'audio. Réessayez.",
            internal=internal,
        )



class TTSError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=503,
            detail="Impossible de générer l'audio. Réessayez.",
            internal=internal,
        )



class EmptyMessageError(AlzheiCareException):
    def __init__(self):
        super().__init__(
            status_code=422,
            detail="Le message ne peut pas être vide.",
        )

class InvalidStageError(AlzheiCareException):
    def __init__(self, stage: int):
        super().__init__(
            status_code=422,
            detail=f"Stade invalide: {stage}. Les valeurs acceptées sont 0, 1, ou 2.",
        )

class InvalidRoleError(AlzheiCareException):
    def __init__(self, role: str):
        super().__init__(
            status_code=422,
            detail=f"Rôle invalide: {role}. Les valeurs acceptées sont 'caregiver' ou 'doctor'.",
        )



class MemoryUnavailableError(AlzheiCareException):
    def __init__(self, internal: str = ""):
        super().__init__(
            status_code=503,
            detail="Service mémoire indisponible.",
            internal=internal,
        )