# CORS 500 Error Fix

## Problem

When a server error (500) occurs, the response doesn't include CORS headers, causing the browser to block the response with:
```
Origin http://localhost:3001 is not allowed by Access-Control-Allow-Origin. Status code: 500
```

## Root Cause

1. **Error responses missing CORS headers**: When exceptions occur, FastAPI's exception handlers return responses without CORS headers
2. **Wildcard origin issue**: Using `"*"` with `allow_credentials=True` is not allowed by browsers
3. **Exception handlers not configured**: Default exception handlers don't include CORS headers

## Solution

### 1. Fixed CORS Configuration

- **Removed wildcard origins**: Changed from `["*"]` to specific origins list
- **Added localhost:3001**: Explicitly included in allowed origins
- **Maintained credentials**: Can now use `allow_credentials=True` with specific origins

### 2. Added CORS Headers to Error Handlers

All exception handlers now include CORS headers:

- `404 Not Found` handler
- `500 Internal Server Error` handler  
- `HTTPException` handler (for all HTTP exceptions)
- `Exception` handler (for unhandled exceptions)

### 3. Dynamic Origin Handling

The `get_cors_headers()` function:
- Checks the request's `Origin` header
- Verifies it's in the allowed origins list
- Returns appropriate CORS headers
- Handles edge cases gracefully

## Allowed Origins

Default allowed origins (development):
- `http://localhost:3000`
- `http://localhost:3001` ✅ (now included)
- `http://localhost:8501`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:3001`
- `http://127.0.0.1:8501`

## Configuration

### Environment Variable

Set `CORS_ORIGINS` to override defaults:

```env
CORS_ORIGINS=http://localhost:3001,https://yourdomain.com
```

### Production

For production, set specific origins:

```env
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
ENV=production
```

## Testing

### 1. Verify CORS Headers in Error Responses

```bash
# Trigger a 500 error and check headers
curl -X POST http://localhost:8000/analyze \
  -H "Origin: http://localhost:3001" \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}' \
  -v
```

Look for:
```
Access-Control-Allow-Origin: http://localhost:3001
Access-Control-Allow-Credentials: true
```

### 2. Test from Browser

1. Open browser DevTools → Network tab
2. Make a request that triggers an error
3. Check response headers include CORS headers
4. Verify no CORS errors in console

### 3. Check Backend Logs

On startup, you should see:
```
🌐 CORS Configuration: Allowing origins: ['http://localhost:3000', 'http://localhost:3001', ...]
```

## Files Modified

- `backend/app/main.py`:
  - Fixed CORS origins configuration
  - Added `get_cors_headers()` function
  - Updated all exception handlers to include CORS headers
  - Added startup log for CORS configuration

## Verification Checklist

- ✅ `localhost:3001` is in allowed origins
- ✅ Error responses include CORS headers
- ✅ Credentials are allowed (for JWT auth)
- ✅ All exception handlers configured
- ✅ Startup log shows correct origins

## Common Issues

### Still Getting CORS Errors?

1. **Check backend logs** for CORS configuration on startup
2. **Verify origin** matches exactly (including http/https and port)
3. **Clear browser cache** and hard refresh
4. **Check Network tab** for actual request/response headers
5. **Restart backend** after configuration changes

### 500 Errors Still Not Showing CORS Headers?

1. Check that exception handlers are registered (they should be at the end of `main.py`)
2. Verify `get_cors_headers()` function is working
3. Check backend logs for the actual error
4. Ensure FastAPI is using the latest version

## Next Steps

If issues persist:

1. Check backend error logs for the actual 500 error
2. The CORS error is a symptom - fix the underlying 500 error
3. Once the 500 error is fixed, CORS headers will be properly included
