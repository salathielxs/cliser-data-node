from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import app


OUTPUT = ROOT / "docs/openapi/cliser-data-node.openapi.current.json"


def example(value, summary=None, description=None):
    item = {"value": value}

    if summary:
        item["summary"] = summary

    if description:
        item["description"] = description

    return item


def main() -> None:
    spec = app.openapi()

    # ============================================================
    # METADATA
    # ============================================================

    spec["info"] = {
        "title": "CLISER DATA NODE API",
        "version": "1.0.0",
        "description": (
            "HTTP API do CLISER DATA NODE.\n\n"
            "API Version: v1\n"
            "Base Path: /api/v1"
        ),
    }

    spec["x-api-version"] = "v1"
    spec["x-base-path"] = "/api/v1"

    # ============================================================
    # TAGS
    # ============================================================

    spec["tags"] = [
        {
            "name": "health",
            "description": "Health, liveness e readiness do node.",
        },
        {
            "name": "metrics",
            "description": "Métricas operacionais do node.",
        },
        {
            "name": "lifecycle",
            "description": "Operações de manutenção e ciclo de vida.",
        },
        {
            "name": "authentication",
            "description": "Autenticação e identidade.",
        },
        {
            "name": "namespaces",
            "description": "Gerenciamento de namespaces.",
        },
        {
            "name": "objects",
            "description": (
                "Criação, consulta, verificação e exclusão de objetos."
            ),
        },
        {
            "name": "uploads",
            "description": "Upload de objetos.",
        },
        {
            "name": "download",
            "description": "Download de conteúdo binário.",
        },
        {
            "name": "metadata",
            "description": "Metadados dos objetos.",
        },
        {
            "name": "manifests",
            "description": "Manifestos e blocos.",
        },
        {
            "name": "transactions",
            "description": "Consulta de transações.",
        },
        {
            "name": "quotas",
            "description": "Gerenciamento de quotas.",
        },
    ]

    # ============================================================
    # COMPONENTS
    # ============================================================

    components = spec.setdefault("components", {})

    components["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "credential",
            "description": (
                "Credencial de API enviada no cabeçalho "
                "Authorization como Bearer <credential>."
            ),
        }
    }

    schemas = components.setdefault("schemas", {})

    schemas["APIError"] = {
        "title": "APIError",
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": [
                    "code",
                    "message",
                    "request_id",
                ],
                "properties": {
                    "code": {
                        "type": "string",
                        "example": "OBJECT_NOT_FOUND",
                    },
                    "message": {
                        "type": "string",
                        "example": "Objeto não encontrado",
                    },
                    "request_id": {
                        "type": ["string", "null"],
                        "example": "req_01JEXAMPLE",
                    },
                    "details": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
            }
        },
    }

    # ============================================================
    # REUSABLE EXAMPLES
    # ============================================================

    components["examples"] = {
        "NamespaceCreateRequest": example(
            {
                "namespace": "documents",
                "quota_bytes": 10737418240,
            },
            "Criação de namespace",
        ),

        "NamespaceResponse": example(
            {
                "namespace": "documents",
                "status": "ACTIVE",
                "quota_bytes": 10737418240,
                "created_at": "2026-09-15T15:00:00Z",
                "updated_at": "2026-09-15T15:00:00Z",
            },
            "Namespace ativo",
        ),

        "NamespaceListResponse": example(
            {
                "items": [
                    {
                        "namespace": "documents",
                        "status": "ACTIVE",
                        "quota_bytes": 10737418240,
                        "created_at": "2026-09-15T15:00:00Z",
                        "updated_at": "2026-09-15T15:00:00Z",
                    }
                ],
                "total": 1,
            },
            "Lista de namespaces",
        ),

        "ObjectCreateRequest": example(
            {
                "data": "Q0xJU0VSIERBVEEgTk9ERQ==",
            },
            "Objeto em Base64",
            "O campo data deve conter Base64 válido.",
        ),

        "ObjectCreateResponse": example(
            {
                "object_id": "obj_01JEXAMPLE",
                "namespace": "documents",
                "size": 16,
                "content_hash": "sha256:01JEXAMPLE",
                "status": "ACTIVE",
            },
            "Objeto criado",
        ),

        "ObjectListResponse": example(
            {
                "namespace": "documents",
                "objects": [
                    {
                        "object_id": "obj_01JEXAMPLE",
                        "namespace": "documents",
                        "size": 16,
                        "created_at": "2026-09-14T12:00:00Z",
                        "status": "ACTIVE",
                    }
                ],
                "count": 1,
            },
            "Lista de objetos",
        ),

        "ObjectMetadataResponse": example(
            {
                "object_id": "obj_01JEXAMPLE",
                "namespace": "documents",
                "size": 16,
                "content_hash": "sha256:01JEXAMPLE",
                "created_at": "2026-09-15T15:00:00Z",
                "status": "ACTIVE",
            },
            "Metadados do objeto",
        ),

        "ObjectVerifyResponse": example(
            {
                "object_id": "obj_01JEXAMPLE",
                "valid": True,
                "status": "VALID",
                "message": "VALID",
            },
            "Objeto válido",
        ),

        "ObjectDeleteResponse": example(
            {
                "object_id": "obj_01JEXAMPLE",
                "deleted": True,
                "status": "DELETED",
            },
            "Objeto removido",
        ),

        "UploadResponse": example(
            {
                "object_id": "obj_01JEXAMPLE",
                "namespace": "documents",
                "filename": "documento.pdf",
                "size": 245760,
                "content_hash": "sha256:01JEXAMPLE",
                "status": "ACTIVE",
            },
            "Upload concluído",
        ),

        "ManifestResponse": example(
            {
                "object_id": "obj_01JEXAMPLE",
                "namespace": "documents",
                "total_size": 524288,
                "block_size": 262144,
                "block_count": 2,
                "created_at": "2026-09-15T15:00:00Z",
                "status": "ACTIVE",
                "blocks": [
                    {
                        "index": 0,
                        "block_id": "blk_01JEXAMPLE0",
                        "size": 262144,
                    },
                    {
                        "index": 1,
                        "block_id": "blk_01JEXAMPLE1",
                        "size": 262144,
                    },
                ],
            },
            "Manifesto do objeto",
        ),

        "TransactionResponse": example(
            {
                "transaction_id": "tx_01JEXAMPLE",
                "object_id": "obj_01JEXAMPLE",
                "namespace": "documents",
                "operation": "OBJECT_CREATE",
                "state": "COMMITTED",
                "created_at": "2026-09-15T15:00:00Z",
                "updated_at": "2026-09-15T15:00:01Z",
            },
            "Transação concluída",
        ),

        "TransactionListResponse": example(
            {
                "transactions": [
                    {
                        "transaction_id": "tx_01JEXAMPLE",
                        "object_id": "obj_01JEXAMPLE",
                        "namespace": "documents",
                        "operation": "OBJECT_CREATE",
                        "state": "COMMITTED",
                        "created_at": "2026-09-15T15:00:00Z",
                        "updated_at": "2026-09-15T15:00:01Z",
                    }
                ],
                "count": 1,
            },
            "Lista de transações",
        ),

        "QuotaUpdateRequest": example(
            {
                "quota_bytes": 10737418240,
                "mode": "LOGICAL",
            },
            "Atualização de quota",
        ),

        "QuotaResponse": example(
            {
                "namespace": "documents",
                "quota_bytes": 10737418240,
                "used_bytes": 245760,
                "available_bytes": 10737172480,
            },
            "Quota do namespace",
        ),

        "AuthMeResponse": example(
            {
                "authenticated": True,
                "identity_id": "identity_01JEXAMPLE",
                "role": "admin",
                "namespace": "documents",
                "credential_id": "cred_01JEXAMPLE",
            },
            "Identidade autenticada",
        ),

        "HealthResponse": example(
            {
                "service": "cliser-data-node",
                "status": "OK",
                "checks": {},
            },
            "Health do node",
        ),

        "HealthLiveResponse": example(
            {
                "status": "ok",
                "service": "cliser-data-node",
                "api_version": "v1",
            },
            "Liveness",
        ),

        "HealthReadyResponse": example(
            {
                "service": "cliser-data-node",
                "status": "READY",
                "checks": {},
            },
            "Node pronto",
        ),

        "HealthNotReadyResponse": example(
            {
                "service": "cliser-data-node",
                "status": "NOT_READY",
                "checks": {},
            },
            "Node não pronto",
        ),

        "ErrorUnauthorized": example(
            {
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Authorization header required",
                    "request_id": "req_01JEXAMPLE",
                }
            },
            "Autenticação obrigatória",
        ),

        "ErrorForbidden": example(
            {
                "error": {
                    "code": "AUTHZ_DENIED",
                    "message": "Access denied",
                    "request_id": "req_01JEXAMPLE",
                    "details": {
                        "permission": "object.read",
                    },
                }
            },
            "Acesso negado",
        ),

        "ErrorNotFound": example(
            {
                "error": {
                    "code": "OBJECT_NOT_FOUND",
                    "message": "Objeto não encontrado",
                    "request_id": "req_01JEXAMPLE",
                }
            },
            "Objeto não encontrado",
        ),

        "ErrorConflict": example(
            {
                "error": {
                    "code": "IDEMPOTENCY_KEY_CONFLICT",
                    "message": "Idempotency-Key conflict",
                    "request_id": "req_01JEXAMPLE",
                }
            },
            "Conflito de idempotência",
        ),

        "ErrorValidation": example(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "request_id": "req_01JEXAMPLE",
                    "details": {
                        "errors": [
                            {
                                "type": "value_error",
                                "loc": [
                                    "body",
                                    "namespace",
                                ],
                                "msg": "field required",
                            }
                        ]
                    },
                }
            },
            "Erro de validação",
        ),

        "ErrorRateLimit": example(
            {
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Limite de requisições excedido.",
                    "details": {
                        "operation": "object.create",
                        "limit": 60,
                        "remaining": 0,
                        "retry_after": 60,
                    },
                }
            },
            "Rate limit excedido",
        ),
    }

    # ============================================================
    # SECURITY
    # ============================================================

    public_paths = {
        "/api/v1/health",
        "/api/v1/health/live",
        "/api/v1/health/ready",
    }

    documentation_paths = {
        "/api/v1/openapi.json",
        "/api/v1/docs",
        "/api/v1/redoc",
    }

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue

            if path in public_paths or path in documentation_paths:
                operation["security"] = []
            else:
                operation["security"] = [{"bearerAuth": []}]

    # ============================================================
    # DOWNLOAD
    # ============================================================

    download_path = (
        "/api/v1/namespaces/{namespace}/objects/{object_id}/download"
    )

    download = spec["paths"][download_path]["get"]

    download["summary"] = "Download de objeto"
    download["description"] = (
        "Recupera o conteúdo binário de um objeto armazenado "
        "no namespace informado."
    )

    download["responses"]["200"] = {
        "description": "Conteúdo binário do objeto.",
        "headers": {
            "Content-Length": {
                "description": "Tamanho do conteúdo em bytes.",
                "schema": {
                    "type": "integer",
                },
            },
            "X-Object-ID": {
                "description": "Identificador do objeto.",
                "schema": {
                    "type": "string",
                },
            },
            "X-Content-Hash": {
                "description": "Hash SHA-256 do conteúdo.",
                "schema": {
                    "type": "string",
                },
            },
        },
        "content": {
            "application/octet-stream": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                }
            }
        },
    }

    # ============================================================
    # REQUEST EXAMPLES
    # ============================================================

    paths = spec["paths"]

    ns_create = paths["/api/v1/namespaces"]["post"]
    ns_create["requestBody"]["content"]["application/json"]["examples"] = {
        "NamespaceCreate": {
            "$ref": "#/components/examples/NamespaceCreateRequest"
        }
    }

    object_create_path = (
        "/api/v1/namespaces/{namespace}/objects"
    )

    object_create = paths[object_create_path]["post"]

    object_create["requestBody"]["content"][
        "application/json"
    ]["examples"] = {
        "ObjectCreate": {
            "$ref": "#/components/examples/ObjectCreateRequest"
        }
    }

    quota_path = "/api/v1/namespaces/{namespace}/quota"

    quota_update = paths[quota_path]["put"]

    quota_update["requestBody"]["content"][
        "application/json"
    ]["examples"] = {
        "QuotaUpdate": {
            "$ref": "#/components/examples/QuotaUpdateRequest"
        }
    }

    # ============================================================
    # RESPONSE EXAMPLES
    # ============================================================

    def response_example(path, method, status, schema_name):
        response = paths[path][method]["responses"][status]

        content = response.setdefault(
            "content",
            {
                "application/json": {
                    "schema": {}
                }
            },
        )

        if "application/json" in content:
            content["application/json"]["examples"] = {
                schema_name: {
                    "$ref": f"#/components/examples/{schema_name}"
                }
            }

    response_example(
        "/api/v1/namespaces",
        "post",
        "201",
        "NamespaceResponse",
    )

    response_example(
        "/api/v1/namespaces",
        "get",
        "200",
        "NamespaceListResponse",
    )

    response_example(
        object_create_path,
        "post",
        "201",
        "ObjectCreateResponse",
    )

    response_example(
        "/api/v1/namespaces/{namespace}/objects",
        "get",
        "200",
        "ObjectListResponse",
    )

    response_example(
        "/api/v1/namespaces/{namespace}/objects/{object_id}",
        "get",
        "200",
        "ObjectMetadataResponse",
    )

    response_example(
        "/api/v1/namespaces/{namespace}/objects/{object_id}/verify",
        "get",
        "200",
        "ObjectVerifyResponse",
    )

    response_example(
        "/api/v1/namespaces/{namespace}/objects/{object_id}",
        "delete",
        "200",
        "ObjectDeleteResponse",
    )

    response_example(
        "/api/v1/namespaces/{namespace}/objects/{object_id}/metadata",
        "get",
        "200",
        "ObjectMetadataResponse",
    )

    response_example(
        "/api/v1/namespaces/{namespace}/objects/{object_id}/manifest",
        "get",
        "200",
        "ManifestResponse",
    )

    response_example(
        "/api/v1/transactions",
        "get",
        "200",
        "TransactionListResponse",
    )

    response_example(
        "/api/v1/transactions/{transaction_id}",
        "get",
        "200",
        "TransactionResponse",
    )

    response_example(
        quota_path,
        "get",
        "200",
        "QuotaResponse",
    )

    response_example(
        quota_path,
        "put",
        "200",
        "QuotaResponse",
    )

    response_example(
        "/api/v1/auth/me",
        "get",
        "200",
        "AuthMeResponse",
    )

    response_example(
        "/api/v1/health",
        "get",
        "200",
        "HealthResponse",
    )

    response_example(
        "/api/v1/health/live",
        "get",
        "200",
        "HealthLiveResponse",
    )

    response_example(
        "/api/v1/health/ready",
        "get",
        "200",
        "HealthReadyResponse",
    )

    # Upload example.
    upload_path = (
        "/api/v1/namespaces/{namespace}/uploads"
    )

    upload = paths[upload_path]["post"]

    upload_response = upload["responses"]["201"]

    upload_response.setdefault(
        "content",
        {"application/json": {"schema": {}}},
    )

    upload_response["content"][
        "application/json"
    ]["examples"] = {
        "UploadResponse": {
            "$ref": "#/components/examples/UploadResponse"
        }
    }

    # ============================================================
    # ERROR EXAMPLES
    # ============================================================

    error_examples = {
        "401": "ErrorUnauthorized",
        "403": "ErrorForbidden",
        "404": "ErrorNotFound",
        "409": "ErrorConflict",
        "422": "ErrorValidation",
        "429": "ErrorRateLimit",
    }

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                continue

            for status, example_name in error_examples.items():
                if status not in operation.get("responses", {}):
                    continue

                response = operation["responses"][status]

                response.setdefault(
                    "content",
                    {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/APIError"
                            }
                        }
                    },
                )

                json_content = response["content"].setdefault(
                    "application/json",
                    {
                        "schema": {
                            "$ref": "#/components/schemas/APIError"
                        }
                    },
                )

                json_content["schema"] = {
                    "$ref": "#/components/schemas/APIError"
                }

                json_content["examples"] = {
                    example_name: {
                        "$ref": (
                            "#/components/examples/"
                            + example_name
                        )
                    }
                }

    # ============================================================
    # WRITE
    # ============================================================

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            spec,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Generated: {OUTPUT}")
    print(f"Paths: {len(spec['paths'])}")
    print(
        "Schemas:",
        len(spec.get("components", {}).get("schemas", {})),
    )
    print(
        "Examples:",
        len(spec.get("components", {}).get("examples", {})),
    )
    print(
        "Security schemes:",
        list(
            spec.get("components", {})
            .get("securitySchemes", {})
            .keys()
        ),
    )


if __name__ == "__main__":
    main()
