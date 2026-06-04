# Authentication & Database Implementation Guide

## 🎉 What's Been Implemented

### Backend Authentication System
- ✅ MongoDB Atlas integration with connection pooling
- ✅ JWT token generation and validation (120-minute expiry)
- ✅ Bcrypt password hashing (12 rounds)
- ✅ User registration (POST `/auth/signup`)
- ✅ User login (POST `/auth/login`)
- ✅ Profile retrieval (GET `/auth/me`)
- ✅ Logout endpoint (POST `/auth/logout`)

### Frontend Authentication UI
- ✅ Login page with email/password form
- ✅ Signup page with full name, email, password, confirm password
- ✅ Auth gate component to protect routes
- ✅ Auth context for global auth state management
- ✅ User session persistence (localStorage)
- ✅ Logout button in sidebar with user email display
- ✅ Loading state during auth initialization
- ✅ Error handling and validation

### Database Schema (MongoDB Atlas)
```
resume_analyzer/
├── users/
│   ├── full_name (string)
│   ├── email (string, unique indexed)
│   ├── password_hash (string)
│   ├── role (string: "user" | "admin")
│   ├── created_at (timestamp)
│   └── is_active (boolean)
│
└── analysis_history/ (For future: storing analysis results)
    ├── user_id (ObjectId, indexed)
    ├── user_email (string)
    ├── domain (string)
    ├── resume_file_name (string)
    ├── jd_source_type (string)
    ├── result_json (object)
    ├── summary (object)
    └── created_at (timestamp, indexed DESC)
```

---

## 🚀 How to Run

### 1. Start the Backend Server
```bash
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The server will:
- Connect to MongoDB Atlas automatically
- Load environment variables from `.env`
- Initialize all routes including `/auth/signup`, `/auth/login`, `/auth/me`, `/auth/logout`
- Display: "✓ Successfully connected to MongoDB"

### 2. Start the Frontend Development Server
```bash
cd frontend
npm run dev
```

The frontend will:
- Start on http://localhost:5173
- Show Login/Signup page first
- Redirect to workspace after authentication
- Store auth token in localStorage
- Display logged-in user email in sidebar

---

## 📋 Environment Variables (Already Set)

File: `backend/.env`

```env
# MongoDB Configuration
MONGODB_URI=mongodb+srv://vivekminipuri_db_user:na#ni&;4@resumeanalyzer.hpz0ynd.mongodb.net/resume_analyzer?appName=ResumeAnalyzer

# JWT Configuration
JWT_SECRET_KEY=<your-generated-secret-key>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

# Bcrypt Configuration
BCRYPT_ROUNDS=12

# CORS Configuration
FRONTEND_ORIGIN=http://localhost:5173

# Application Configuration
DATABASE_NAME=resume_analyzer
```

---

## 🔌 API Endpoints

### Authentication Routes

#### 1. **Sign Up**
```
POST /auth/signup
Content-Type: application/json

{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "SecurePass123"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "full_name": "John Doe",
    "email": "john@example.com",
    "role": "user"
  }
}
```

#### 2. **Log In**
```
POST /auth/login
Content-Type: application/json

{
  "email": "john@example.com",
  "password": "SecurePass123"
}

Response: Same as signup
```

#### 3. **Get Current User Profile**
```
GET /auth/me
Authorization: Bearer <token>

Response:
{
  "id": "507f1f77bcf86cd799439011",
  "full_name": "John Doe",
  "email": "john@example.com",
  "role": "user",
  "created_at": "2026-04-03T23:21:00Z"
}
```

#### 4. **Logout**
```
POST /auth/logout
Authorization: Bearer <token>

Response:
{
  "message": "Logged out successfully"
}
```

---

## 🔐 Authentication Flow

### Signup Flow
1. User enters Full Name, Email, Password, Confirm Password
2. Frontend validates password strength (min 8 chars)
3. POST to `/auth/signup` with credentials
4. Backend hashes password with bcrypt
5. Creates user document in `users` collection
6. Generates JWT token
7. Token stored in localStorage `auth_token`
8. User data stored in localStorage `user_data`
9. Redirect to workspace

### Login Flow
1. User enters Email and Password
2. Frontend POST to `/auth/login`
3. Backend finds user by email
4. Verifies password against hash
5. Generates JWT token
6. Returns token + user info
7. Frontend stores in localStorage
8. Redirect to workspace

### Logout Flow
1 User clicks "Logout" button in sidebar
2. Frontend clears localStorage
3. Auth context updates to logged-out state
4. User redirected to Login page

---

## 🛡️ Security Features

- ✅ Passwords hashed with bcrypt (12 rounds)
- ✅ JWT tokens with 120-minute expiry
- ✅ CORS configured for localhost:5173
- ✅ Email validation on signup
- ✅ Duplicate email prevention (unique index)
- ✅ HTTP Bearer token authentication
- ✅ Token verification on protected routes
- ✅ Secure password toggle in forms

---

## 📱 Frontend Components

### LoginPage (`src/components/LoginPage.jsx`)
- Email and password inputs
- Password visibility toggle
- Error messages with icons
- Loading state with spinner
- Switch to signup link

### SignupPage (`src/components/SignupPage.jsx`)
- Full name input
- Email input
- Password with confirmation
- Password strength validation
- Loading state
- Switch to login link

### AuthGate (`src/components/AuthGate.jsx`)
- Wraps entire app
- Shows login/signup based on auth state
- Handles auth mode switching
- Loading screen during initialization

### useAuth Hook (`src/hooks/useAuth.js`)
- Access auth state from anywhere
- Methods: `login()`, `logout()`, `isAuthenticated`, `user`, `token`

### AuthContext (`src/context/AuthContext.jsx`)
- Global auth state management
- localStorage persistence
- Methods for login/logout
- Loading indicator

---

## 🎨 UI Styling

### Auth Pages (Responsive)
- Purple gradient background
- Centered card layout
- Mobile-friendly inputs (16px font size to prevent zoom)
- Smooth animations and transitions
- Error message with shake animation
- Loading spinner animation
- Input icons for better UX

### Sidebar Integration
- User email display in sidebar
- Red logout button with hover effect
- Positioned at bottom of sidebar
- Works on mobile drawer too

---

## 📊 Next Steps (Optional Features)

### 1. **Analysis History** (Future)
```
- Only admin users can view all results
- Regular users see their own results
- Filterable by date, domain, score
- Export results to CSV/PDF
```

### 2. **Role-Based Features** (Future)
```
- Admin dashboard with statistics
- User management (enable/disable accounts)
- Analysis audit logs
- API usage metrics
```

### 3. **Email Verification** (Future)
```
- Send confirmation link on signup
- Prevent account access until verified
- Resend email functionality
```

### 4. **Password Reset** (Future)
```
- Forgot password endpoint
- Email reset link
- Secure token validation
- Update password flow
```

---

## 🐛 Troubleshooting

### "Failed to connect to MongoDB"
- Check `.env` file has correct `MONGODB_URI`
- Verify MongoDB Atlas cluster is active
- Check network access rules (IP whitelist)
- Test connection string in MongoDB Atlas UI

### "Invalid token" error
- Token may have expired (120 minutes)
- User needs to login again
- Check localStorage for `auth_token`

### "CORS error" on frontend
- Verify backend is running on port 8000
- Check `FRONTEND_ORIGIN` in `.env`
- Browser console will show CORS errors

### Frontend won't show login page
- Clear browser localStorage: `localStorage.clear()`
- Hard refresh page (Ctrl+Shift+R)
- Check browser DevTools for errors

---

## 📝 File Structure

```
backend/
├── main.py (Updated with auth routes)
├── database.py (MongoDB connection)
├── auth_utils.py (JWT & password hashing)
├── auth_models.py (Pydantic models)
├── requirements.txt (Updated with motor, python-jose, passlib, bcrypt)
└── routes/
    └── auth.py (Authentication endpoints)

frontend/
├── src/
│   ├── App.jsx (Updated with AuthGate wrapper)
│   ├── main.jsx (Updated with AuthProvider)
│   ├── components/
│   │   ├── LoginPage.jsx (NEW)
│   │   ├── SignupPage.jsx (NEW)
│   │   └── AuthGate.jsx (NEW)
│   ├── context/
│   │   └── AuthContext.jsx (NEW)
│   ├── hooks/
│   │   └── useAuth.js (NEW)
│   └── styles/
│       ├── auth.css (NEW)
│       └── main.css (Updated with sidebar user info styles)
```

---

## ✨ What's Preserved

- All existing analysis features work as before
- Landing page still displays
- File upload and analysis unchanged
- BERT, visualization, multi-resume features all functional
- Sidebar navigation unchanged
- PDF export works as before
- No breaking changes to existing code

---

## 🎓 Code Examples

### Using Auth in Components
```javascript
import { useAuth } from '../hooks/useAuth';

function MyComponent() {
  const { user, token, logout, isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <div>Not logged in</div>;
  }
  
  return (
    <div>
      <p>Welcome, {user.full_name}!</p>
      <p>Email: {user.email}</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
}
```

### Making Authenticated API Calls
```javascript
const token = localStorage.getItem('auth_token');

const response = await fetch('http://localhost:8000/extract', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: formData
});
```

---

## 🎯 Summary

Your Resume Analyzer now has:
- ✅ Complete user authentication system
- ✅ MongoDB Atlas cloud database
- ✅ JWT token-based security
- ✅ Professional login/signup UI
- ✅ Session persistence
- ✅ Global auth state management
- ✅ Ready for analysis history tracking
- ✅ Prepared for admin dashboard

**All without breaking existing features!** 🚀
