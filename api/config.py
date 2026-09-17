from __future__ import annotations

# =========================================================
# CLISER DATA NODE API
# FASE 14.18 - REQUEST LIMITS
# =========================================================

# Limite máximo do corpo HTTP recebido pela API.
MAX_REQUEST_BODY_BYTES = 12 * 1024 * 1024

# Limite lógico para criação de objetos.
MAX_OBJECT_SIZE_BYTES = 8 * 1024 * 1024

# Limite máximo para uploads multipart.
MAX_UPLOAD_SIZE_BYTES = 16 * 1024 * 1024

# Limite máximo de itens por página.
MAX_PAGE_SIZE = 100

# Limite máximo da query string.
MAX_QUERY_STRING_BYTES = 4 * 1024

# Limite máximo da Idempotency-Key.
MAX_IDEMPOTENCY_KEY_BYTES = 256

# Limite máximo do nome do arquivo.
MAX_FILENAME_BYTES = 255

# =========================================================
# FASE 14.19 - RATE LIMITING
# =========================================================

# Limite de requisições de leitura por janela.
RATE_LIMIT_READ_PER_MINUTE = 120

# Limite de requisições de escrita por janela.
RATE_LIMIT_WRITE_PER_MINUTE = 60

# Tamanho da janela do rate limiter.
RATE_LIMIT_WINDOW_SECONDS = 60

# Rotas consideradas operações de escrita.
RATE_LIMIT_WRITE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}
