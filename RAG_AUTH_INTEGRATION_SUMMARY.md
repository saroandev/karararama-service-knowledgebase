# RAG Service - Authentication Integration Summary

## ✅ Implementation Completed

Authentication integration has been successfully implemented for the OneDocs RAG service following the standard `auth-integration.md` specification.

---

## 📋 What Was Implemented

### 1. Core Infrastructure

#### Configuration (`app/config/settings.py`)
Added authentication settings:
```python
JWT_SECRET_KEY - Secret key for JWT validation (must match auth service)
JWT_ALGORITHM - JWT algorithm (HS256)
REQUIRE_AUTH - Enable/disable authentication (true/false)
AUTH_SERVICE_URL - OneDocs Auth Service URL
AUTH_SERVICE_TIMEOUT - Request timeout in seconds
```

#### Custom Exceptions (`app/core/exceptions.py`)
- `AuthenticationError` (401) - Authentication failures
- `InsufficientCreditsError` (403) - Low credits
- `AuthServiceError` (503) - Auth service unavailable
- `QuotaExceededError` (429) - Rate limiting
- Exception handlers for FastAPI

#### Authentication Module (`app/core/auth.py`)
- `UserContext` - User information from JWT
- `decode_jwt_token()` - JWT validation and decoding
- `get_current_user()` - FastAPI dependency for authentication
- `require_permission(resource, action)` - Permission checking
- HTTPBearer security for Swagger UI 🔒 button

#### Auth Service Client (`app/services/auth_service.py`)
- `AuthServiceClient` - Communication with auth service
- `consume_usage()` - Report usage and consume credits
- `check_health()` - Health check
- Retry logic with exponential backoff
- Singleton pattern

---

### 2. Endpoint Protection

#### Query Endpoint (`api/endpoints/query.py`)
- **Permission**: `rag:query`
- **Service Type**: `rag_query`
- **Usage Tracking**:
  - Tokens from OpenAI response
  - Processing time
  - Metadata (question length, sources count, model)
- **Response**: Added `tokens_used` and `remaining_credits`

#### Ingest Endpoint (`api/endpoints/ingest.py`)
- **Permission**: `rag:ingest`
- **Service Type**: `rag_ingest`
- **Usage Tracking**:
  - Embedding tokens
  - Processing time
  - Metadata (filename, chunks, pages, file size, document type)
- **Response**: Added `tokens_used` and `remaining_credits`

#### Batch Ingest Endpoint
- **Permission**: `rag:ingest`
- Protected with same authentication

#### Documents List (`api/endpoints/documents.py`)
- **Permission**: `rag:read`
- No usage consumption (read-only)

#### Document Delete
- **Permission**: `rag:delete`
- **Service Type**: `rag_delete`
- **Usage Tracking**: Metadata only (no tokens)

---

### 3. Permission Mapping

| Endpoint | HTTP Method | Permission | Service Type |
|----------|------------|------------|--------------|
| `/query` | POST | `research:query` | `rag_query` |
| `/ingest` | POST | `research:ingest` | `rag_ingest` |
| `/batch-ingest` | POST | `research:ingest` | `rag_batch_ingest` |
| `/documents` | GET | `documents:read` | - |
| `/documents/{id}` | DELETE | `documents:delete` | `rag_delete` |
| `/health` | GET | None (public) | - |

**Special Permissions:**
- `admin:*` - Grants access to ALL endpoints (super admin)
- `research:*` - Grants access to query and ingest endpoints
- `documents:*` - Grants access to document management endpoints

---

### 4. Usage Metrics

#### Query Endpoint
```json
{
  "user_id": "user-123",
  "service_type": "rag_query",
  "tokens_used": 450,
  "processing_time": 1.23,
  "metadata": {
    "question_length": 50,
    "sources_count": 5,
    "model": "gpt-4o-mini",
    "top_k": 5
  }
}
```

#### Ingest Endpoint
```json
{
  "user_id": "user-123",
  "service_type": "rag_ingest",
  "tokens_used": 15360,
  "processing_time": 5.67,
  "metadata": {
    "filename": "document.pdf",
    "chunks_created": 45,
    "pages_count": 10,
    "file_size_bytes": 524288,
    "document_type": "pdf"
  }
}
```

#### Delete Endpoint
```json
{
  "user_id": "user-123",
  "service_type": "rag_delete",
  "tokens_used": 0,
  "processing_time": 0,
  "metadata": {
    "document_id": "doc_abc123",
    "document_title": "Sample Document",
    "chunks_deleted": 45
  }
}
```

---

### 5. Testing

Created comprehensive unit tests (`tests/unit/test_auth.py`):
- JWT token decoding (valid, expired, invalid)
- UserContext creation and validation
- Permission checking (exact match, wildcards, dict format)
- Development mode behavior
- Error scenarios

---

## 🔧 Configuration

### Environment Variables (.env)

```env
# JWT Authentication
JWT_SECRET_KEY=your_jwt_secret_key_here_min_32_chars
JWT_ALGORITHM=HS256
REQUIRE_AUTH=true

# Auth Service Configuration
AUTH_SERVICE_URL=http://onedocs-auth:8001
AUTH_SERVICE_TIMEOUT=5
```

**Important Notes:**
- `JWT_SECRET_KEY` must be **identical** to OneDocs Auth Service
- Use `http://localhost:8001` for local development
- Use `http://onedocs-auth:8001` for Docker/production
- Set `REQUIRE_AUTH=false` only for local development

---

## 🚀 Development Mode

For local testing without authentication:

```env
REQUIRE_AUTH=false
```

Mock user credentials:
- `user_id`: `"dev-user"`
- `email`: `"dev@example.com"`
- `permissions`: `["*"]`
- `credits`: `999999`

---

## 📦 Dependencies

Added to `requirements.txt`:
```
pyjwt==2.8.0
```

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 🧪 Testing

### Run Authentication Tests
```bash
# All auth tests
pytest tests/unit/test_auth.py -v

# Specific test class
pytest tests/unit/test_auth.py::TestJWTDecoding -v

# With coverage
pytest tests/unit/test_auth.py --cov=app.core.auth --cov-report=html
```

### Manual Testing with Swagger UI

1. Start the API server:
   ```bash
   python -m api.main
   ```

2. Open Swagger UI: http://localhost:8080/docs

3. Click 🔒 **Authorize** button (top right)

4. Get JWT token from auth service:
   ```bash
   curl -X POST http://localhost:8001/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "password"}'
   ```

5. Enter token (without "Bearer" prefix) and click **Authorize**

6. All requests will now include the token

---

## 🔍 Error Responses

### Authentication Error (401)
```json
{
  "success": false,
  "error": "Missing authentication token",
  "error_type": "authentication_error"
}
```

### Permission Denied (403)
```json
{
  "success": false,
  "error": "Permission denied: rag:query",
  "error_type": "permission_denied"
}
```

### Insufficient Credits (403)
```json
{
  "success": false,
  "error": "Insufficient credits",
  "error_type": "insufficient_credits"
}
```

### Auth Service Error (503)
```json
{
  "success": false,
  "error": "Auth service unavailable",
  "error_type": "auth_service_error"
}
```

---

## 📝 Integration Checklist

- [x] Environment configuration (.env, settings.py)
- [x] Custom exceptions (app/core/exceptions.py)
- [x] Authentication module (app/core/auth.py)
- [x] Auth service client (app/services/auth_service.py)
- [x] Query endpoint protection
- [x] Ingest endpoint protection
- [x] Documents endpoint protection
- [x] Exception handlers registered
- [x] Response schemas updated (tokens_used, remaining_credits)
- [x] Unit tests created
- [x] Dependencies updated (pyjwt)
- [x] Swagger UI 🔒 Authorize button working

---

## 🎯 Key Features

✅ **JWT-based Authentication** - Secure token validation
✅ **Permission-based Authorization** - Granular access control
✅ **Usage Tracking** - Automatic credit consumption
✅ **Development Mode** - Easy local testing
✅ **Retry Logic** - Resilient auth service communication
✅ **Comprehensive Testing** - Unit tests for all scenarios
✅ **Swagger Integration** - Built-in API documentation with auth
✅ **Error Handling** - Consistent error responses

---

## 🔄 Next Steps

1. **Set JWT_SECRET_KEY** in your `.env` file (must match auth service)
2. **Start OneDocs Auth Service** (required for production)
3. **Test Authentication Flow**:
   - Get token from auth service
   - Use token in RAG API requests
   - Verify usage tracking
4. **Configure Permissions** in auth service for users
5. **Monitor Credit Consumption** via auth service logs

---

## 🆘 Troubleshooting

### "Missing authentication token"
- Ensure `Authorization: Bearer <token>` header is present
- Check token format (should start with "eyJ")

### "Invalid token" or "Token has expired"
- Get fresh token from auth service
- Verify JWT_SECRET_KEY matches auth service

### "Permission denied: rag:query"
- Check user permissions in auth service
- Verify permission format: `resource:action`
- Admin can add permissions via auth service API

### "Auth service unavailable"
- Check auth service is running: `curl http://localhost:8001/health`
- Verify AUTH_SERVICE_URL in .env
- Check Docker network if using containers

### JWT_SECRET_KEY Mismatch
- Ensure same secret in both services:
  ```bash
  # Auth Service .env
  JWT_SECRET_KEY=your_secret_key

  # RAG Service .env
  JWT_SECRET_KEY=your_secret_key  # Must match!
  ```

---

## 📚 References

- **OneDocs Auth Service**: Main authentication service
- **auth-integration.md**: Standard integration guide
- **JWT.io**: Debug and decode JWT tokens
- **FastAPI Security Docs**: https://fastapi.tiangolo.com/tutorial/security/

---

**Implementation Date**: 2025-10-04
**Version**: 1.0.0
**Based On**: OneDocs OCR Service Implementation
**Follows**: auth-integration.md Standard
