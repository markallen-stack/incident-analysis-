# Authentication and History Integration Guide

This document describes the complete end-to-end integration of authentication, user management, analysis history, and audit logs.

---

## Backend Implementation

### Authentication Module (`backend/core/auth.py`)

**Features:**
- JWT token generation and validation
- Password hashing with bcrypt
- FastAPI dependencies for protected routes
- Optional authentication for backward compatibility

**Key Functions:**
- `get_current_user()` - Required authentication dependency
- `get_optional_user()` - Optional authentication (for backward compat)
- `create_access_token()` - Generate JWT tokens
- `verify_password()` / `get_password_hash()` - Password management

**Environment Variables:**
```env
JWT_SECRET_KEY=your-secret-key-here  # Required in production
JWT_EXPIRE_MINUTES=10080  # 7 days (default)
```

### API Endpoints

#### Authentication (`/auth/*`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/auth/signup` | Create new user account | No |
| `POST` | `/auth/login` | Login and get JWT token | No |
| `GET` | `/auth/me` | Get current user profile | Yes |
| `PUT` | `/auth/me` | Update user profile | Yes |

**Request/Response Examples:**

```json
// POST /auth/signup
{
  "email": "user@example.com",
  "password": "securepassword123",
  "name": "John Doe"
}

// Response
{
  "user_id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "access_token": "jwt-token-here",
  "token_type": "bearer"
}
```

#### History (`/history/*`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/history` | List user's analyses (paginated) | Yes |
| `GET` | `/history/{id}` | Get full analysis details | Yes |
| `DELETE` | `/history/{id}` | Delete an analysis | Yes |

**Query Parameters:**
- `limit` (default: 100, max: 1000)
- `offset` (default: 0)
- `status` (optional: "answer", "refuse", "request_more_data")

#### Audit Logs (`/audit/*`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/audit` | List audit logs | Yes |

**Query Parameters:**
- `limit`, `offset`, `action` (optional filter)

**Access Control:**
- Regular users: See only their own logs
- Admins: See all logs

#### Updated Endpoints

**`POST /analyze`**
- Now saves to database automatically
- Associates analysis with authenticated user
- Creates audit log entry

**`GET /analysis/{id}`**
- Checks database first
- Enforces access control (users can only see their own)
- Falls back to cache for anonymous (backward compat)

**`GET /settings`** and **`PUT /settings`**
- If authenticated: Per-user settings in database
- If anonymous: System-wide settings in file (backward compat)

**`GET /stats`**
- Includes `user_analyses` count if authenticated
- Shows `authenticated: true/false`

---

## Frontend Implementation

### Authentication (`frontend/lib/auth.ts`)

**Functions:**
- `setAuthToken()` / `getAuthToken()` - Token management
- `setUser()` / `getUser()` - User info storage
- `isAuthenticated()` - Check auth status
- `getAuthHeader()` - Get Authorization header value

### API Client (`frontend/lib/api.ts`)

**Updates:**
- Axios interceptor adds `Authorization: Bearer <token>` to all requests
- 401 handler clears auth and redirects (optional)
- New functions: `signup()`, `login()`, `getProfile()`, `updateProfile()`
- New functions: `getAnalysisHistory()`, `getAnalysisDetail()`, `deleteAnalysis()`
- New functions: `getAuditLogs()`

### React Hooks

#### `useAuth()` (`frontend/lib/hooks/useAuth.ts`)
- Get current user profile
- Check authentication status
- Auto-fetches profile if authenticated

#### `useLogin()` / `useSignup()`
- Handle login/signup mutations
- Store token and user info on success
- Show toast notifications

#### `useLogout()`
- Clear auth data
- Clear React Query cache

#### `useAnalysisHistory()` (`frontend/lib/hooks/useHistory.ts`)
- Fetch paginated analysis list
- Supports status filtering
- Auto-refresh on mutations

#### `useAnalysisDetail()`
- Fetch full analysis details
- Lazy loading support

#### `useDeleteAnalysis()`
- Delete analysis mutation
- Invalidates history cache on success

### Components

#### `Login.tsx`
- Login/signup form with tabs
- Email/password validation
- Password strength (min 8 chars)
- Loading states

#### `History.tsx`
- Analysis history list with pagination
- Status filtering (All, Answered, Refused, Need More Data)
- View and delete actions
- Responsive design

#### Updated `page.tsx`
- Shows `Login` component if not authenticated
- Shows main app if authenticated
- Header shows user info and logout button
- Replaced old `AnalysisHistory` with new `History` component

---

## Database Schema

### `users`
- Stores user accounts
- Password hashed with bcrypt
- `is_active` and `is_admin` flags

### `user_settings`
- Per-user configuration
- Key-value pairs with type information
- Unique constraint: `(user_id, key)`

### `analyses`
- Full analysis history
- Stores request and response as JSONB
- Indexed on `user_id`, `analysis_id`, `created_at`, `status`

### `audit_logs`
- Audit trail for all user actions
- Includes IP address and user agent
- Indexed for efficient querying

---

## Setup Instructions

### 1. Backend Setup

**Install dependencies:**
```bash
cd backend
pip install -r requirements.txt
```

**Set environment variables:**
```env
# Database
DATABASE_URL=postgresql+asyncpg://...
DB_USER=postgres
DB_PASSWORD=...
DB_HOST=...
DB_PORT=5432
DB_NAME=incident_rag

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_EXPIRE_MINUTES=10080
```

**Initialize database:**
```bash
python scripts/init_db.py
```

**Start backend:**
```bash
python run.py
```

### 2. Frontend Setup

**Install dependencies:**
```bash
cd frontend
npm install

# Install missing package if needed:
npm install @radix-ui/react-label
```

**Set environment variables:**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Start frontend:**
```bash
npm run dev
```

---

## Usage Flow

### 1. User Signup/Login

1. User visits app → sees `Login` component
2. User signs up or logs in
3. Token stored in `localStorage`
4. User profile fetched and cached
5. App shows main interface

### 2. Running Analysis

1. User fills out analysis form
2. `POST /analyze` includes `Authorization: Bearer <token>`
3. Backend saves analysis to database with `user_id`
4. Audit log entry created
5. Frontend shows results

### 3. Viewing History

1. User clicks "History" tab
2. `GET /history` fetches user's analyses
3. List shows with pagination and filters
4. User can view details or delete

### 4. Managing Settings

1. User clicks "Settings" tab
2. `GET /settings` returns per-user settings
3. User updates values
4. `PUT /settings` saves to database
5. Audit log entry created

---

## Security Considerations

### Backend

1. **JWT Secret Key**: Must be strong and unique in production
2. **Password Hashing**: Uses bcrypt (secure)
3. **Access Control**: Users can only access their own data
4. **Token Expiration**: 7 days default (configurable)
5. **HTTPS**: Required in production

### Frontend

1. **Token Storage**: `localStorage` (consider httpOnly cookies for production)
2. **XSS Protection**: Sanitize user inputs
3. **CSRF**: Consider CSRF tokens for state-changing operations
4. **Token Refresh**: Consider implementing refresh tokens

---

## Testing

### Backend

```bash
# Test signup
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test1234","name":"Test User"}'

# Test login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test1234"}'

# Test protected endpoint
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer <token>"

# Test history
curl -X GET "http://localhost:8000/history?limit=10&offset=0" \
  -H "Authorization: Bearer <token>"
```

### Frontend

1. Open app → should show login
2. Sign up → should redirect to main app
3. Run analysis → should save to database
4. View history → should show your analyses
5. Logout → should return to login

---

## Troubleshooting

### "Invalid authentication credentials"

- Check token is being sent in `Authorization` header
- Verify token hasn't expired
- Check `JWT_SECRET_KEY` matches between restarts

### "User not found" after login

- Check database connection
- Verify user exists in `users` table
- Check `is_active` flag

### History shows empty

- Verify user is authenticated
- Check `analyses` table has entries with correct `user_id`
- Check database connection

### Settings not saving

- Verify authentication
- Check database connection
- Check `user_settings` table permissions

---

## Next Steps

1. **Refresh Tokens**: Implement refresh token rotation
2. **Email Verification**: Add email verification on signup
3. **Password Reset**: Implement password reset flow
4. **Role-Based Access**: Expand admin capabilities
5. **API Rate Limiting**: Add rate limiting per user
6. **Analytics Dashboard**: Show user-specific analytics
7. **Export History**: Allow exporting analysis history as JSON/CSV

---

## Files Created/Modified

### Backend
- `backend/core/auth.py` - Authentication utilities
- `backend/app/routers/auth.py` - Auth endpoints
- `backend/app/routers/history.py` - History endpoints
- `backend/app/routers/audit.py` - Audit log endpoints
- `backend/app/main.py` - Updated to use auth

### Frontend
- `frontend/lib/auth.ts` - Auth utilities
- `frontend/lib/hooks/useAuth.ts` - Auth hooks
- `frontend/lib/hooks/useHistory.ts` - History hooks
- `frontend/components/Login.tsx` - Login/signup component
- `frontend/components/History.tsx` - History component
- `frontend/components/ui/label.tsx` - Label component
- `frontend/app/page.tsx` - Updated with auth integration
- `frontend/lib/api.ts` - Updated with new endpoints

---

## Summary

✅ **Complete end-to-end integration** of:
- User authentication (signup, login, JWT)
- Per-user settings in database
- Analysis history with pagination and filtering
- Audit logging for all operations
- Frontend components and hooks
- Protected routes and access control

The system now supports **multi-user** operation with full data isolation and history tracking!
