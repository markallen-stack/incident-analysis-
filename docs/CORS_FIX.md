# CORS Configuration Fix

## Issues Fixed

### 1. Port Mismatch
- **Problem**: Frontend was configured to use port `8001` but backend runs on port `8000`
- **Fix**: Updated `frontend/lib/api.ts` to use port `8000` as default

### 2. CORS Configuration
- **Problem**: CORS middleware needed better configuration for credentials and headers
- **Fix**: Enhanced CORS middleware with:
  - Proper origin handling (development vs production)
  - Explicit allowed methods
  - Required headers for authentication
  - Credentials support
  - Preflight caching

## Configuration

### Backend CORS Settings

The backend now supports:

1. **Environment-based origins**:
   ```env
   CORS_ORIGINS=http://localhost:3000,http://localhost:3001,https://yourdomain.com
   ```

2. **Default development origins**:
   - `http://localhost:3000` (Next.js default)
   - `http://localhost:3001` (Alternative)
   - `http://localhost:8501` (Docker)
   - `127.0.0.1` variants

3. **Development mode**: Allows all origins (`*`) if `ENV=development`

### Allowed Methods
- GET, POST, PUT, DELETE, OPTIONS, PATCH

### Allowed Headers
- Content-Type
- Authorization (for JWT tokens)
- Accept
- Origin
- X-Requested-With
- Access-Control-Request-Method
- Access-Control-Request-Headers

### Credentials
- `allow_credentials: True` - Required for cookies and auth headers

## Testing CORS

### 1. Check Preflight Request
```bash
curl -X OPTIONS http://localhost:8000/analyze \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization" \
  -v
```

Expected response headers:
```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, PATCH
Access-Control-Allow-Headers: Content-Type, Authorization, ...
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 3600
```

### 2. Test Actual Request
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"query":"test","timestamp":"2024-01-15T14:32:00Z"}' \
  -v
```

### 3. Browser Console Check
Open browser DevTools → Network tab:
- Look for OPTIONS requests (preflight)
- Check response headers for CORS headers
- Verify no CORS errors in console

## Common CORS Errors and Solutions

### Error: "Access to fetch at '...' from origin '...' has been blocked by CORS policy"

**Solution:**
1. Check that frontend origin is in `ALLOWED_ORIGINS`
2. Verify backend is running on correct port (8000)
3. Check that `CORS_ORIGINS` env var includes your frontend URL

### Error: "Credentials flag is 'true', but 'Access-Control-Allow-Origin' is '*'"

**Solution:**
- When using credentials, cannot use `*` for origins
- Set specific origins in `CORS_ORIGINS` environment variable

### Error: "Request header field authorization is not allowed"

**Solution:**
- Already fixed - `Authorization` is in `allow_headers`
- Verify backend has latest code

## Production Configuration

For production, set specific origins:

```env
# .env or environment variables
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
ENV=production
```

This ensures:
- Only allowed origins can access the API
- Credentials work properly
- Security is maintained

## Frontend Configuration

### Environment Variables

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production:
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### API Client

The API client (`frontend/lib/api.ts`) now:
- Uses correct port (8000)
- Sends `Authorization` header with JWT tokens
- Handles 401 errors (clears auth on unauthorized)

## Verification

After fixes, verify:

1. ✅ Frontend can make requests to backend
2. ✅ No CORS errors in browser console
3. ✅ Authentication headers are sent
4. ✅ Preflight OPTIONS requests succeed
5. ✅ Credentials are included in requests

## Debugging

If CORS issues persist:

1. **Check backend logs** for CORS-related errors
2. **Check browser Network tab** for:
   - OPTIONS request status
   - Response headers
   - Request headers
3. **Verify ports** match between frontend and backend
4. **Test with curl** to isolate browser vs server issues
5. **Check environment variables** are set correctly

## Files Modified

- `backend/app/main.py` - Enhanced CORS middleware configuration
- `frontend/lib/api.ts` - Fixed default port (8000 instead of 8001)
